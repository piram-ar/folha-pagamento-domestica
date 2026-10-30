from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import usuario_atual
from ..models import BeneficioFixo, FolhaPagamento, ReajusteSalarial, StatusFolha, Trabalhador
from ..schemas import (
    BeneficioIn,
    BeneficioOut,
    ReajusteIn,
    ReajusteOut,
    TrabalhadorCreate,
    TrabalhadorDetalheOut,
    TrabalhadorOut,
    TrabalhadorUpdate,
    validar_dias_pagamento,
)
from ..services.salario import calcular_novo_salario, inicio_do_mes, salario_em, sincronizar_salario_atual

router = APIRouter(prefix="/trabalhadores", tags=["Trabalhadores"], dependencies=[Depends(usuario_atual)])


def obter_trabalhador(db: Session, trabalhador_id: int) -> Trabalhador:
    trabalhador = db.get(Trabalhador, trabalhador_id)
    if trabalhador is None:
        raise HTTPException(status_code=404, detail="Trabalhador não encontrado")
    return trabalhador


def _cpf_em_uso(db: Session, cpf: str, ignorar_id: int | None = None) -> bool:
    consulta = select(Trabalhador.id).where(Trabalhador.cpf == cpf)
    if ignorar_id:
        consulta = consulta.where(Trabalhador.id != ignorar_id)
    return db.scalar(consulta) is not None


@router.get("", response_model=list[TrabalhadorOut])
def listar(apenas_ativos: bool = False, db: Session = Depends(get_db)):
    consulta = select(Trabalhador).order_by(Trabalhador.nome)
    if apenas_ativos:
        consulta = consulta.where(Trabalhador.ativo)
    return db.scalars(consulta).all()


@router.post("", response_model=TrabalhadorDetalheOut, status_code=status.HTTP_201_CREATED)
def criar(dados: TrabalhadorCreate, db: Session = Depends(get_db)):
    if _cpf_em_uso(db, dados.cpf):
        raise HTTPException(status_code=409, detail="CPF já cadastrado")
    trabalhador = Trabalhador(**dados.model_dump())
    db.add(trabalhador)
    db.commit()
    db.refresh(trabalhador)
    return trabalhador


@router.get("/{trabalhador_id}", response_model=TrabalhadorDetalheOut)
def detalhar(trabalhador_id: int, db: Session = Depends(get_db)):
    trabalhador = db.scalar(
        select(Trabalhador)
        .options(selectinload(Trabalhador.beneficios), selectinload(Trabalhador.reajustes))
        .where(Trabalhador.id == trabalhador_id)
    )
    if trabalhador is None:
        raise HTTPException(status_code=404, detail="Trabalhador não encontrado")
    return trabalhador


@router.put("/{trabalhador_id}", response_model=TrabalhadorDetalheOut)
def atualizar(trabalhador_id: int, dados: TrabalhadorUpdate, db: Session = Depends(get_db)):
    trabalhador = obter_trabalhador(db, trabalhador_id)
    campos = dados.model_dump(exclude_unset=True)
    if "cpf" in campos and _cpf_em_uso(db, campos["cpf"], trabalhador.id):
        raise HTTPException(status_code=409, detail="CPF já cadastrado")
    novo_salario = campos.get("salario_base")
    if trabalhador.reajustes and novo_salario is not None and novo_salario != trabalhador.salario_base:
        raise HTTPException(
            status_code=409,
            detail="Este trabalhador tem reajustes registrados: altere o salário registrando um novo reajuste.",
        )
    for campo, valor in campos.items():
        setattr(trabalhador, campo, valor)
    try:  # a atualização é parcial: valida as datas de pagamento já combinadas com o cadastro
        validar_dias_pagamento(trabalhador)
    except ValueError as erro:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(erro))
    db.commit()
    db.refresh(trabalhador)
    return trabalhador


@router.delete("/{trabalhador_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(trabalhador_id: int, db: Session = Depends(get_db)):
    trabalhador = obter_trabalhador(db, trabalhador_id)
    possui_fechada = db.scalar(
        select(FolhaPagamento.id).where(
            FolhaPagamento.trabalhador_id == trabalhador.id, FolhaPagamento.status == StatusFolha.fechada
        )
    )
    if possui_fechada:
        raise HTTPException(
            status_code=409,
            detail="Trabalhador possui folhas fechadas. Para preservar o histórico, desative-o em vez de excluir.",
        )
    db.delete(trabalhador)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Configuração financeira: benefícios fixos ----------

@router.get("/{trabalhador_id}/beneficios", response_model=list[BeneficioOut])
def listar_beneficios(trabalhador_id: int, db: Session = Depends(get_db)):
    return obter_trabalhador(db, trabalhador_id).beneficios


@router.post("/{trabalhador_id}/beneficios", response_model=BeneficioOut, status_code=status.HTTP_201_CREATED)
def criar_beneficio(trabalhador_id: int, dados: BeneficioIn, db: Session = Depends(get_db)):
    obter_trabalhador(db, trabalhador_id)
    beneficio = BeneficioFixo(trabalhador_id=trabalhador_id, **dados.model_dump())
    db.add(beneficio)
    db.commit()
    db.refresh(beneficio)
    return beneficio


def _obter_beneficio(db: Session, trabalhador_id: int, beneficio_id: int) -> BeneficioFixo:
    beneficio = db.get(BeneficioFixo, beneficio_id)
    if beneficio is None or beneficio.trabalhador_id != trabalhador_id:
        raise HTTPException(status_code=404, detail="Benefício não encontrado")
    return beneficio


@router.put("/{trabalhador_id}/beneficios/{beneficio_id}", response_model=BeneficioOut)
def atualizar_beneficio(trabalhador_id: int, beneficio_id: int, dados: BeneficioIn, db: Session = Depends(get_db)):
    beneficio = _obter_beneficio(db, trabalhador_id, beneficio_id)
    for campo, valor in dados.model_dump().items():
        setattr(beneficio, campo, valor)
    db.commit()
    db.refresh(beneficio)
    return beneficio


@router.delete("/{trabalhador_id}/beneficios/{beneficio_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_beneficio(trabalhador_id: int, beneficio_id: int, db: Session = Depends(get_db)):
    db.delete(_obter_beneficio(db, trabalhador_id, beneficio_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Reajustes salariais ----------

@router.get("/{trabalhador_id}/reajustes", response_model=list[ReajusteOut])
def listar_reajustes(trabalhador_id: int, db: Session = Depends(get_db)):
    return obter_trabalhador(db, trabalhador_id).reajustes


@router.post("/{trabalhador_id}/reajustes", response_model=ReajusteOut, status_code=status.HTTP_201_CREATED)
def registrar_reajuste(trabalhador_id: int, dados: ReajusteIn, db: Session = Depends(get_db)):
    """Novo reajuste a partir de uma competência. Só se acrescenta ao fim do histórico, para que
    reajustes percentuais posteriores nunca fiquem calculados sobre um salário que mudou."""
    trabalhador = obter_trabalhador(db, trabalhador_id)
    vigencia = inicio_do_mes(dados.vigencia)
    if vigencia < trabalhador.data_admissao.replace(day=1):
        raise HTTPException(status_code=422, detail="A vigência não pode ser anterior à admissão")
    ultimo = trabalhador.reajustes[-1] if trabalhador.reajustes else None
    if ultimo and vigencia <= ultimo.vigencia:
        raise HTTPException(
            status_code=422,
            detail=f"Já há reajuste vigente a partir de {ultimo.vigencia:%m/%Y}. Registre a partir de um mês posterior "
                   "ou exclua o último reajuste.",
        )
    fechada = db.scalar(select(FolhaPagamento.mes_ano).where(
        FolhaPagamento.trabalhador_id == trabalhador.id, FolhaPagamento.status == StatusFolha.fechada,
        FolhaPagamento.mes_ano >= dados.vigencia,
    ).order_by(FolhaPagamento.mes_ano))
    if fechada:
        raise HTTPException(
            status_code=409,
            detail=f"A folha de {fechada[5:]}/{fechada[:4]} já está fechada. Reabra-a para registrar um reajuste "
                   "que a afete.",
        )

    anterior = salario_em(trabalhador, vigencia)
    novo = calcular_novo_salario(anterior, dados.tipo, dados.valor)
    if novo <= anterior:
        raise HTTPException(status_code=422, detail=f"O novo salário deve ser maior que o atual (R$ {anterior:.2f})".replace(".", ","))

    reajuste = ReajusteSalarial(
        vigencia=vigencia, tipo=dados.tipo, valor_informado=dados.valor,
        salario_anterior=anterior, salario_novo=novo, motivo=dados.motivo,
    )
    trabalhador.reajustes.append(reajuste)
    sincronizar_salario_atual(trabalhador)
    db.commit()
    db.refresh(reajuste)
    return reajuste


@router.delete("/{trabalhador_id}/reajustes/{reajuste_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_reajuste(trabalhador_id: int, reajuste_id: int, db: Session = Depends(get_db)):
    trabalhador = obter_trabalhador(db, trabalhador_id)
    reajuste = next((r for r in trabalhador.reajustes if r.id == reajuste_id), None)
    if reajuste is None:
        raise HTTPException(status_code=404, detail="Reajuste não encontrado")
    if reajuste is not trabalhador.reajustes[-1]:
        raise HTTPException(status_code=422, detail="Exclua os reajustes do mais recente para o mais antigo")
    fechada = db.scalar(select(FolhaPagamento.id).where(
        FolhaPagamento.trabalhador_id == trabalhador.id, FolhaPagamento.status == StatusFolha.fechada,
        FolhaPagamento.mes_ano >= f"{reajuste.vigencia:%Y-%m}",
    ))
    if fechada:
        raise HTTPException(status_code=409, detail="Há folha fechada usando este reajuste. Reabra-a antes de excluir.")
    trabalhador.reajustes.remove(reajuste)
    # Sem reajustes, o salário do cadastro volta a ser o anterior ao reajuste excluído
    trabalhador.salario_base = reajuste.salario_anterior if not trabalhador.reajustes else trabalhador.salario_base
    sincronizar_salario_atual(trabalhador)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
