from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import usuario_atual
from ..models import BeneficioFixo, FolhaPagamento, StatusFolha, Trabalhador
from ..schemas import (
    BeneficioIn,
    BeneficioOut,
    TrabalhadorCreate,
    TrabalhadorDetalheOut,
    TrabalhadorOut,
    TrabalhadorUpdate,
    validar_dias_pagamento,
)

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
        select(Trabalhador).options(selectinload(Trabalhador.beneficios)).where(Trabalhador.id == trabalhador_id)
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
