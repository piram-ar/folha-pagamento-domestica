import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class PerfilUsuario(str, enum.Enum):
    admin = "admin"
    padrao = "padrao"


class TipoContrato(str, enum.Enum):
    com_registro = "com_registro"
    sem_registro = "sem_registro"


class TipoBeneficio(str, enum.Enum):
    vale_transporte = "vale_transporte"
    vale_mercado = "vale_mercado"
    vale_refeicao = "vale_refeicao"
    plano_saude = "plano_saude"
    outro = "outro"


class NaturezaBeneficio(str, enum.Enum):
    provento = "provento"        # pago junto com o salário (soma ao líquido)
    desconto = "desconto"        # descontado do salário (ex.: cota de 6% do VT)
    informativo = "informativo"  # pago por fora (cartão), só aparece no recibo


class TipoEvento(str, enum.Enum):
    vale_antecipacao = "vale_antecipacao"
    hora_extra = "hora_extra"
    falta = "falta"
    bonus = "bonus"


class StatusFolha(str, enum.Enum):
    rascunho = "rascunho"
    fechada = "fechada"


def _enum(enum_cls):
    # Armazenado como VARCHAR no SQLite; validação de valores feita pelo SQLAlchemy/Pydantic
    return Enum(enum_cls, native_enum=False, length=30, validate_strings=True)


Dinheiro = Numeric(12, 2)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    perfil: Mapped[PerfilUsuario] = mapped_column(_enum(PerfilUsuario), default=PerfilUsuario.padrao)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Contratante(Base):
    """Empregador (com registro) ou contratante (sem registro) e o local da prestação do serviço.

    Registro único (id = 1): os dados saem no recibo de todos os trabalhadores.
    """

    __tablename__ = "contratante"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    cpf: Mapped[Optional[str]] = mapped_column(String(11))
    telefone: Mapped[Optional[str]] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(160))
    # Local da prestação do serviço
    cep: Mapped[Optional[str]] = mapped_column(String(8))
    logradouro: Mapped[Optional[str]] = mapped_column(String(160))
    numero: Mapped[Optional[str]] = mapped_column(String(20))
    complemento: Mapped[Optional[str]] = mapped_column(String(80))
    bairro: Mapped[Optional[str]] = mapped_column(String(80))
    cidade: Mapped[Optional[str]] = mapped_column(String(80))
    uf: Mapped[Optional[str]] = mapped_column(String(2))


class Trabalhador(Base):
    __tablename__ = "trabalhadores"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    cpf: Mapped[str] = mapped_column(String(11), unique=True, index=True)
    tipo_contrato: Mapped[TipoContrato] = mapped_column(_enum(TipoContrato))
    salario_base: Mapped[Decimal] = mapped_column(Dinheiro)
    data_admissao: Mapped[date] = mapped_column(Date)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Dias da semana trabalhados (ISO: 1 = segunda ... 7 = domingo), base dos dias úteis do VT
    dias_semana_trabalho: Mapped[str] = mapped_column(String(7), default="12345", server_default="12345")
    # Datas de pagamento: "dia_util" = N-ésimo dia útil do mês; senão, dia N do mês (antecipado se cair em
    # domingo/feriado). Usadas nos avisos por e-mail e no calendário (.ics/.vcs).
    dia_pagamento_salario: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    salario_dia_util: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    adiantamento_acordado: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    dia_pagamento_adiantamento: Mapped[Optional[int]] = mapped_column(Integer)
    adiantamento_dia_util: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    funcao: Mapped[Optional[str]] = mapped_column(String(120))  # cargo impresso no holerite

    beneficios: Mapped[list["BeneficioFixo"]] = relationship(
        back_populates="trabalhador", cascade="all, delete-orphan"
    )
    eventos: Mapped[list["EventoFolha"]] = relationship(
        back_populates="trabalhador", cascade="all, delete-orphan"
    )
    historico_ferias: Mapped[list["HistoricoFerias"]] = relationship(
        back_populates="trabalhador",
        cascade="all, delete-orphan",
        order_by="HistoricoFerias.periodo_aquisitivo_inicio",
    )
    folhas: Mapped[list["FolhaPagamento"]] = relationship(
        back_populates="trabalhador", cascade="all, delete-orphan"
    )
    reajustes: Mapped[list["ReajusteSalarial"]] = relationship(
        back_populates="trabalhador", cascade="all, delete-orphan", order_by="ReajusteSalarial.vigencia"
    )


class BeneficioFixo(Base):
    __tablename__ = "beneficios_fixos"

    id: Mapped[int] = mapped_column(primary_key=True)
    trabalhador_id: Mapped[int] = mapped_column(ForeignKey("trabalhadores.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[TipoBeneficio] = mapped_column(_enum(TipoBeneficio))
    natureza: Mapped[NaturezaBeneficio] = mapped_column(
        _enum(NaturezaBeneficio), default=NaturezaBeneficio.provento
    )
    descricao: Mapped[Optional[str]] = mapped_column(String(120))
    valor: Mapped[Decimal] = mapped_column(Dinheiro)

    trabalhador: Mapped[Trabalhador] = relationship(back_populates="beneficios")


class EventoFolha(Base):
    __tablename__ = "eventos_folha"

    id: Mapped[int] = mapped_column(primary_key=True)
    trabalhador_id: Mapped[int] = mapped_column(ForeignKey("trabalhadores.id", ondelete="CASCADE"), index=True)
    mes_ano: Mapped[str] = mapped_column(String(7), index=True)  # formato AAAA-MM
    tipo: Mapped[TipoEvento] = mapped_column(_enum(TipoEvento))
    quantidade_horas: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    percentual_adicional: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))  # hora extra: 50, 100...
    valor: Mapped[Decimal] = mapped_column(Dinheiro)
    data_lancamento: Mapped[date] = mapped_column(Date)
    descricao: Mapped[Optional[str]] = mapped_column(String(255))

    trabalhador: Mapped[Trabalhador] = relationship(back_populates="eventos")


class HistoricoFerias(Base):
    __tablename__ = "historico_ferias"
    __table_args__ = (UniqueConstraint("trabalhador_id", "periodo_aquisitivo_inicio"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trabalhador_id: Mapped[int] = mapped_column(ForeignKey("trabalhadores.id", ondelete="CASCADE"), index=True)
    periodo_aquisitivo_inicio: Mapped[date] = mapped_column(Date)
    periodo_aquisitivo_fim: Mapped[date] = mapped_column(Date)
    dias_adquiridos: Mapped[int] = mapped_column(Integer, default=0)
    dias_gozados: Mapped[int] = mapped_column(Integer, default=0)
    saldo_dias: Mapped[int] = mapped_column(Integer, default=0)

    trabalhador: Mapped[Trabalhador] = relationship(back_populates="historico_ferias")
    gozos: Mapped[list["GozoFerias"]] = relationship(
        back_populates="periodo", cascade="all, delete-orphan", order_by="GozoFerias.data_inicio"
    )


class GozoFerias(Base):
    """Cada registro de férias efetivamente tiradas (gera o histórico)."""

    __tablename__ = "gozos_ferias"

    id: Mapped[int] = mapped_column(primary_key=True)
    historico_ferias_id: Mapped[int] = mapped_column(
        ForeignKey("historico_ferias.id", ondelete="CASCADE"), index=True
    )
    data_inicio: Mapped[date] = mapped_column(Date)
    data_fim: Mapped[date] = mapped_column(Date)
    dias: Mapped[int] = mapped_column(Integer)
    observacao: Mapped[Optional[str]] = mapped_column(String(255))
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    periodo: Mapped[HistoricoFerias] = relationship(back_populates="gozos")


class FolhaPagamento(Base):
    __tablename__ = "folha_pagamento"
    __table_args__ = (UniqueConstraint("trabalhador_id", "mes_ano"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trabalhador_id: Mapped[int] = mapped_column(ForeignKey("trabalhadores.id", ondelete="CASCADE"), index=True)
    mes_ano: Mapped[str] = mapped_column(String(7), index=True)
    dias_trabalhados: Mapped[int] = mapped_column(Integer)
    dias_uteis: Mapped[Optional[int]] = mapped_column(Integer)  # base do vale-transporte no mês
    salario_base: Mapped[Decimal] = mapped_column(Dinheiro)  # congelado no momento do cálculo
    salario_proporcional: Mapped[Decimal] = mapped_column(Dinheiro)
    total_horas_extras: Mapped[Decimal] = mapped_column(Dinheiro, default=0)
    total_bonus: Mapped[Decimal] = mapped_column(Dinheiro, default=0)
    total_faltas: Mapped[Decimal] = mapped_column(Dinheiro, default=0)
    total_descontos_vales: Mapped[Decimal] = mapped_column(Dinheiro, default=0)
    total_beneficios: Mapped[Decimal] = mapped_column(Dinheiro, default=0)  # benefícios pagos (proventos)
    total_descontos_beneficios: Mapped[Decimal] = mapped_column(Dinheiro, default=0)
    inss_empregado: Mapped[Decimal] = mapped_column(Dinheiro, default=0)
    salario_bruto: Mapped[Decimal] = mapped_column(Dinheiro, default=0)  # base de cálculo dos encargos
    total_proventos: Mapped[Decimal] = mapped_column(Dinheiro, default=0)
    total_descontos: Mapped[Decimal] = mapped_column(Dinheiro, default=0)
    encargos_recolher_guardar: Mapped[Decimal] = mapped_column(Dinheiro, default=0)
    salario_liquido: Mapped[Decimal] = mapped_column(Dinheiro)
    status: Mapped[StatusFolha] = mapped_column(_enum(StatusFolha), default=StatusFolha.rascunho)
    detalhamento: Mapped[Optional[str]] = mapped_column(Text)  # JSON com as linhas do recibo e encargos
    calculado_em: Mapped[Optional[datetime]] = mapped_column(DateTime)
    fechado_em: Mapped[Optional[datetime]] = mapped_column(DateTime)
    pago_em: Mapped[Optional[date]] = mapped_column(Date)  # vazio = líquido ainda em aberto

    trabalhador: Mapped[Trabalhador] = relationship(back_populates="folhas")


class TabelaInss(Base):
    """Tabela progressiva do INSS do empregado, válida a partir de `vigencia_inicio`.

    A folha de cada mês usa a tabela de vigência mais recente que já valia no 1º dia do mês.
    """

    __tablename__ = "tabelas_inss"

    id: Mapped[int] = mapped_column(primary_key=True)
    vigencia_inicio: Mapped[date] = mapped_column(Date, unique=True)
    descricao: Mapped[Optional[str]] = mapped_column(String(120))

    faixas: Mapped[list["FaixaInss"]] = relationship(
        back_populates="tabela", cascade="all, delete-orphan", order_by="FaixaInss.teto"
    )


class FaixaInss(Base):
    __tablename__ = "faixas_inss"

    id: Mapped[int] = mapped_column(primary_key=True)
    tabela_id: Mapped[int] = mapped_column(ForeignKey("tabelas_inss.id", ondelete="CASCADE"), index=True)
    teto: Mapped[Decimal] = mapped_column(Dinheiro)  # limite superior da faixa (salário de contribuição)
    aliquota: Mapped[Decimal] = mapped_column(Numeric(5, 2))  # em %, ex.: 7.50

    tabela: Mapped[TabelaInss] = relationship(back_populates="faixas")


class SegurancaSmtp(str, enum.Enum):
    starttls = "starttls"  # porta 587 (Gmail, Outlook)
    ssl = "ssl"            # porta 465
    nenhuma = "nenhuma"


class ConfigNotificacoes(Base):
    """Configuração única (id = 1) dos avisos de pagamento."""

    __tablename__ = "config_notificacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Dias de antecedência dos avisos, separados por vírgula (ex.: "3,1"); 0 = no próprio dia
    antecedencias: Mapped[str] = mapped_column(String(40), default="3,1")
    email_ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    destinatarios: Mapped[Optional[str]] = mapped_column(String(500))
    hora_envio: Mapped[int] = mapped_column(Integer, default=8)
    smtp_host: Mapped[Optional[str]] = mapped_column(String(160))
    smtp_porta: Mapped[int] = mapped_column(Integer, default=587)
    smtp_seguranca: Mapped[SegurancaSmtp] = mapped_column(_enum(SegurancaSmtp), default=SegurancaSmtp.starttls)
    smtp_usuario: Mapped[Optional[str]] = mapped_column(String(160))
    smtp_senha: Mapped[Optional[str]] = mapped_column(String(255))
    smtp_remetente: Mapped[Optional[str]] = mapped_column(String(160))
    # Token do link de assinatura do calendário (sem login); trocar o token invalida o link antigo
    token_calendario: Mapped[Optional[str]] = mapped_column(String(64))
    ultimo_envio_em: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ultimo_erro: Mapped[Optional[str]] = mapped_column(Text)


class TipoPagamento(str, enum.Enum):
    salario = "salario"
    adiantamento = "adiantamento"


class NotificacaoEnviada(Base):
    """Evita reenviar o mesmo aviso (inclusive após reiniciar o Pi)."""

    __tablename__ = "notificacoes_enviadas"
    __table_args__ = (UniqueConstraint("trabalhador_id", "tipo", "data_pagamento", "antecedencia"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trabalhador_id: Mapped[int] = mapped_column(ForeignKey("trabalhadores.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[TipoPagamento] = mapped_column(_enum(TipoPagamento))
    data_pagamento: Mapped[date] = mapped_column(Date)
    antecedencia: Mapped[int] = mapped_column(Integer)
    enviado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class TipoReajuste(str, enum.Enum):
    percentual = "percentual"      # ex.: 5,5%
    valor = "valor"                # acréscimo em R$ (ex.: + R$ 100,00)
    novo_salario = "novo_salario"  # informa diretamente o novo salário


class ReajusteSalarial(Base):
    """Histórico de aumentos. O salário de cada competência é o do último reajuste já vigente nela.

    `salario_anterior` e `salario_novo` ficam gravados para o histórico não depender de recálculos.
    """

    __tablename__ = "reajustes_salariais"
    __table_args__ = (UniqueConstraint("trabalhador_id", "vigencia"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trabalhador_id: Mapped[int] = mapped_column(ForeignKey("trabalhadores.id", ondelete="CASCADE"), index=True)
    vigencia: Mapped[date] = mapped_column(Date)  # sempre dia 1: vale para a competência inteira
    tipo: Mapped[TipoReajuste] = mapped_column(_enum(TipoReajuste))
    valor_informado: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # % ou R$, conforme o tipo
    salario_anterior: Mapped[Decimal] = mapped_column(Dinheiro)
    salario_novo: Mapped[Decimal] = mapped_column(Dinheiro)
    motivo: Mapped[Optional[str]] = mapped_column(String(160))
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    trabalhador: Mapped[Trabalhador] = relationship(back_populates="reajustes")
