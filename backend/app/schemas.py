import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from .models import (
    NaturezaBeneficio,
    PerfilUsuario,
    StatusFolha,
    TipoBeneficio,
    TipoContrato,
    TipoEvento,
)

MesAno = Annotated[str, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
Valor = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Autenticação / usuários ----------

class LoginIn(BaseModel):
    email: str
    senha: str


class UsuarioOut(ORM):
    id: int
    nome: str
    email: str
    perfil: PerfilUsuario
    ativo: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class UsuarioCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=160)
    senha: str = Field(min_length=6, max_length=72)
    perfil: PerfilUsuario = PerfilUsuario.padrao
    ativo: bool = True

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower()


class UsuarioUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=2, max_length=120)
    email: Optional[str] = Field(default=None, min_length=3, max_length=160)
    senha: Optional[str] = Field(default=None, min_length=6, max_length=72)
    perfil: Optional[PerfilUsuario] = None
    ativo: Optional[bool] = None

    @field_validator("email")
    @classmethod
    def _email(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().lower() if v else v


# ---------- Trabalhadores ----------

def _validar_cpf(v: str) -> str:
    cpf = re.sub(r"\D", "", v or "")
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        raise ValueError("CPF inválido")
    for pos in (9, 10):
        soma = sum(int(cpf[i]) * (pos + 1 - i) for i in range(pos))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[pos]):
            raise ValueError("CPF inválido")
    return cpf


def _validar_dias_semana(v: str) -> str:
    dias = sorted(set(v or ""))
    if not dias or any(d not in "1234567" for d in dias):
        raise ValueError("Informe ao menos um dia da semana (1 = segunda ... 7 = domingo)")
    return "".join(dias)


class TrabalhadorBase(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    cpf: str
    tipo_contrato: TipoContrato
    salario_base: Valor
    data_admissao: date
    ativo: bool = True
    dias_semana_trabalho: str = "12345"

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v: str) -> str:
        return _validar_cpf(v)

    @field_validator("dias_semana_trabalho")
    @classmethod
    def _dias_semana(cls, v: str) -> str:
        return _validar_dias_semana(v)


class TrabalhadorCreate(TrabalhadorBase):
    pass


class TrabalhadorUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=2, max_length=120)
    cpf: Optional[str] = None
    tipo_contrato: Optional[TipoContrato] = None
    salario_base: Optional[Valor] = None
    data_admissao: Optional[date] = None
    ativo: Optional[bool] = None
    dias_semana_trabalho: Optional[str] = None

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v: Optional[str]) -> Optional[str]:
        return _validar_cpf(v) if v is not None else v

    @field_validator("dias_semana_trabalho")
    @classmethod
    def _dias_semana(cls, v: Optional[str]) -> Optional[str]:
        return _validar_dias_semana(v) if v is not None else v


class BeneficioIn(BaseModel):
    tipo: TipoBeneficio
    natureza: NaturezaBeneficio = NaturezaBeneficio.provento
    descricao: Optional[str] = Field(default=None, max_length=120)
    valor: Valor


class BeneficioOut(ORM):
    id: int
    trabalhador_id: int
    tipo: TipoBeneficio
    natureza: NaturezaBeneficio
    descricao: Optional[str]
    valor: Decimal


class TrabalhadorOut(ORM):
    id: int
    nome: str
    cpf: str
    tipo_contrato: TipoContrato
    salario_base: Decimal
    data_admissao: date
    ativo: bool
    dias_semana_trabalho: str


class TrabalhadorDetalheOut(TrabalhadorOut):
    beneficios: list[BeneficioOut] = []


# ---------- Empregador / contratante ----------

UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR",
       "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}


class ContratanteIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    cpf: Optional[str] = None
    telefone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=160)
    cep: Optional[str] = None
    logradouro: Optional[str] = Field(default=None, max_length=160)
    numero: Optional[str] = Field(default=None, max_length=20)
    complemento: Optional[str] = Field(default=None, max_length=80)
    bairro: Optional[str] = Field(default=None, max_length=80)
    cidade: Optional[str] = Field(default=None, max_length=80)
    uf: Optional[str] = None

    @field_validator("*", mode="before")
    @classmethod
    def _vazio_para_none(cls, v):
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v: Optional[str]) -> Optional[str]:
        return _validar_cpf(v) if v else None

    @field_validator("cep")
    @classmethod
    def _cep(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        cep = re.sub(r"\D", "", v)
        if len(cep) != 8:
            raise ValueError("CEP inválido")
        return cep

    @field_validator("uf")
    @classmethod
    def _uf(cls, v: Optional[str]) -> Optional[str]:
        if v and v.upper() not in UFS:
            raise ValueError("UF inválida")
        return v.upper() if v else None


class ContratanteOut(ORM):
    nome: str
    cpf: Optional[str]
    telefone: Optional[str]
    email: Optional[str]
    cep: Optional[str]
    logradouro: Optional[str]
    numero: Optional[str]
    complemento: Optional[str]
    bairro: Optional[str]
    cidade: Optional[str]
    uf: Optional[str]


# ---------- Eventos variáveis ----------

class EventoIn(BaseModel):
    trabalhador_id: int
    mes_ano: MesAno
    tipo: TipoEvento
    quantidade_horas: Optional[Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2)]] = None
    percentual_adicional: Optional[Annotated[Decimal, Field(ge=0, le=300)]] = None
    valor: Optional[Valor] = None  # se omitido em hora_extra/falta, é calculado pelas horas
    data_lancamento: Optional[date] = None
    descricao: Optional[str] = Field(default=None, max_length=255)


class EventoOut(ORM):
    id: int
    trabalhador_id: int
    mes_ano: str
    tipo: TipoEvento
    quantidade_horas: Optional[Decimal]
    percentual_adicional: Optional[Decimal]
    valor: Decimal
    data_lancamento: date
    descricao: Optional[str]


# ---------- Folha ----------

class CalcularFolhaIn(BaseModel):
    trabalhador_id: int
    mes_ano: MesAno
    dias_trabalhados: int = Field(ge=0, le=31)
    # Dias úteis para o vale-transporte; se omitido, calcula pelo calendário do trabalhador
    dias_uteis: Optional[int] = Field(default=None, ge=0, le=31)


class DiasUteisOut(BaseModel):
    trabalhador_id: int
    dias_uteis: int
    tem_vt_diario: bool


class FolhaOut(ORM):
    id: int
    trabalhador_id: int
    trabalhador_nome: str
    tipo_contrato: TipoContrato
    mes_ano: str
    dias_trabalhados: int
    dias_uteis: Optional[int]
    salario_base: Decimal
    salario_proporcional: Decimal
    total_horas_extras: Decimal
    total_bonus: Decimal
    total_faltas: Decimal
    total_descontos_vales: Decimal
    total_beneficios: Decimal
    total_descontos_beneficios: Decimal
    inss_empregado: Decimal
    salario_bruto: Decimal
    total_proventos: Decimal
    total_descontos: Decimal
    encargos_recolher_guardar: Decimal
    salario_liquido: Decimal
    status: StatusFolha
    detalhamento: Optional[dict] = None
    calculado_em: Optional[datetime]
    fechado_em: Optional[datetime]


# ---------- Férias ----------

class GozoIn(BaseModel):
    historico_ferias_id: Optional[int] = None  # se omitido, abate do período mais antigo com saldo
    data_inicio: date
    dias: int = Field(ge=1, le=30)
    observacao: Optional[str] = Field(default=None, max_length=255)


class GozoOut(ORM):
    id: int
    historico_ferias_id: int
    data_inicio: date
    data_fim: date
    dias: int
    observacao: Optional[str]


class PeriodoFeriasOut(ORM):
    id: int
    periodo_aquisitivo_inicio: date
    periodo_aquisitivo_fim: date
    dias_adquiridos: int
    dias_gozados: int
    saldo_dias: int
    completo: bool
    limite_concessivo: date
    situacao: str
    gozos: list[GozoOut] = []


class FeriasTrabalhadorOut(BaseModel):
    trabalhador_id: int
    trabalhador_nome: str
    data_admissao: date
    saldo_total: int
    saldo_vencido: int
    periodo_atual: Optional[PeriodoFeriasOut]
    alertas: list[str]
    periodos: list[PeriodoFeriasOut]
