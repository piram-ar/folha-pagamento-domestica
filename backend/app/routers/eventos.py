from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import usuario_atual
from ..models import EventoFolha, FolhaPagamento, StatusFolha, TipoEvento
from ..schemas import EventoIn, EventoOut
from ..services.calculo_folha import q, valor_hora_extra, valor_horas_falta
from ..services.salario import salario_do_mes
from .trabalhadores import obter_trabalhador

router = APIRouter(prefix="/eventos", tags=["Lançamentos do mês"], dependencies=[Depends(usuario_atual)])


def _bloquear_se_fechada(db: Session, trabalhador_id: int, mes_ano: str) -> None:
    fechada = db.scalar(
        select(FolhaPagamento.id).where(
            FolhaPagamento.trabalhador_id == trabalhador_id,
            FolhaPagamento.mes_ano == mes_ano,
            FolhaPagamento.status == StatusFolha.fechada,
        )
    )
    if fechada:
        raise HTTPException(status_code=409, detail="A folha deste mês já foi fechada; lançamentos bloqueados.")


@router.get("", response_model=list[EventoOut])
def listar(mes_ano: str | None = None, trabalhador_id: int | None = None, db: Session = Depends(get_db)):
    consulta = select(EventoFolha).order_by(EventoFolha.data_lancamento.desc(), EventoFolha.id.desc())
    if mes_ano:
        consulta = consulta.where(EventoFolha.mes_ano == mes_ano)
    if trabalhador_id:
        consulta = consulta.where(EventoFolha.trabalhador_id == trabalhador_id)
    return db.scalars(consulta).all()


@router.post("", response_model=EventoOut, status_code=status.HTTP_201_CREATED)
def criar(dados: EventoIn, db: Session = Depends(get_db)):
    trabalhador = obter_trabalhador(db, dados.trabalhador_id)
    _bloquear_se_fechada(db, trabalhador.id, dados.mes_ano)

    valor = dados.valor
    percentual = dados.percentual_adicional
    descricao = dados.descricao
    if dados.tipo == TipoEvento.hora_extra:
        if not dados.quantidade_horas:
            raise HTTPException(status_code=422, detail="Informe a quantidade de horas extras")
        percentual = percentual if percentual is not None else Decimal("50")
        if valor is None:
            valor = valor_hora_extra(salario_do_mes(trabalhador, dados.mes_ano), dados.quantidade_horas, percentual)
    elif dados.tipo == TipoEvento.falta and valor is None and dados.quantidade_dias:
        valor = q(salario_do_mes(trabalhador, dados.mes_ano) / 30 * dados.quantidade_dias)
        descricao = descricao or f"{dados.quantidade_dias} dia(s) de falta"
    elif dados.tipo == TipoEvento.falta and valor is None:
        if not dados.quantidade_horas:
            raise HTTPException(status_code=422, detail="Informe as horas, os dias de falta ou o valor a descontar")
        valor = valor_horas_falta(salario_do_mes(trabalhador, dados.mes_ano), dados.quantidade_horas)
    if dados.tipo != TipoEvento.hora_extra:
        percentual = None

    if valor is None or valor <= 0:
        raise HTTPException(status_code=422, detail="Informe um valor maior que zero")

    evento = EventoFolha(
        trabalhador_id=trabalhador.id,
        mes_ano=dados.mes_ano,
        tipo=dados.tipo,
        quantidade_horas=dados.quantidade_horas,
        percentual_adicional=percentual,
        valor=valor,
        data_lancamento=dados.data_lancamento or date.today(),
        descricao=descricao,
    )
    db.add(evento)
    db.commit()
    db.refresh(evento)
    return evento


@router.delete("/{evento_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(evento_id: int, db: Session = Depends(get_db)):
    evento = db.get(EventoFolha, evento_id)
    if evento is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    _bloquear_se_fechada(db, evento.trabalhador_id, evento.mes_ano)
    db.delete(evento)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
