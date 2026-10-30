from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import usuario_atual
from ..models import GozoFerias, HistoricoFerias, Trabalhador
from ..schemas import FeriasTrabalhadorOut, GozoIn, GozoOut, PeriodoFeriasOut
from ..services.ferias import limite_concessivo, sincronizar_periodos, situacao_periodo
from .trabalhadores import obter_trabalhador

router = APIRouter(prefix="/ferias", tags=["Férias"], dependencies=[Depends(usuario_atual)])


def _periodo_out(p: HistoricoFerias, hoje: date) -> PeriodoFeriasOut:
    return PeriodoFeriasOut(
        id=p.id,
        periodo_aquisitivo_inicio=p.periodo_aquisitivo_inicio,
        periodo_aquisitivo_fim=p.periodo_aquisitivo_fim,
        dias_adquiridos=p.dias_adquiridos,
        dias_gozados=p.dias_gozados,
        saldo_dias=p.saldo_dias,
        completo=p.periodo_aquisitivo_fim <= hoje,
        limite_concessivo=limite_concessivo(p),
        situacao=situacao_periodo(p, hoje),
        gozos=[GozoOut.model_validate(g) for g in p.gozos],
    )


def _resumo(db: Session, trabalhador: Trabalhador) -> FeriasTrabalhadorOut:
    hoje = date.today()
    periodos = [_periodo_out(p, hoje) for p in sincronizar_periodos(db, trabalhador, hoje)]
    completos = [p for p in periodos if p.completo]
    atual = next((p for p in periodos if not p.completo), None)

    alertas = []
    for p in completos:
        faixa = f"{p.periodo_aquisitivo_inicio:%d/%m/%Y} a {p.periodo_aquisitivo_fim:%d/%m/%Y}"
        if p.situacao == "vencido":
            alertas.append(f"Férias vencidas ({faixa}): {p.saldo_dias} dias - prazo legal expirou "
                           f"em {p.limite_concessivo:%d/%m/%Y} (pagamento em dobro).")
        elif p.situacao == "vence_em_breve":
            alertas.append(f"Conceder {p.saldo_dias} dias do período {faixa} até {p.limite_concessivo:%d/%m/%Y}.")

    return FeriasTrabalhadorOut(
        trabalhador_id=trabalhador.id,
        trabalhador_nome=trabalhador.nome,
        data_admissao=trabalhador.data_admissao,
        saldo_total=sum(p.saldo_dias for p in completos),
        saldo_vencido=sum(p.saldo_dias for p in completos if p.situacao == "vencido"),
        periodo_atual=atual,
        alertas=alertas,
        periodos=periodos,
    )


@router.get("/dashboard", response_model=list[FeriasTrabalhadorOut])
def dashboard(db: Session = Depends(get_db)):
    trabalhadores = db.scalars(
        select(Trabalhador)
        .options(selectinload(Trabalhador.historico_ferias).selectinload(HistoricoFerias.gozos))
        .where(Trabalhador.ativo)
        .order_by(Trabalhador.nome)
    ).all()
    return [_resumo(db, t) for t in trabalhadores]


@router.get("/trabalhador/{trabalhador_id}", response_model=FeriasTrabalhadorOut)
def por_trabalhador(trabalhador_id: int, db: Session = Depends(get_db)):
    return _resumo(db, obter_trabalhador(db, trabalhador_id))


@router.post("/trabalhador/{trabalhador_id}/gozos", response_model=FeriasTrabalhadorOut,
             status_code=status.HTTP_201_CREATED)
def registrar_gozo(trabalhador_id: int, dados: GozoIn, db: Session = Depends(get_db)):
    trabalhador = obter_trabalhador(db, trabalhador_id)
    periodos = sincronizar_periodos(db, trabalhador)

    if dados.historico_ferias_id:
        periodo = next((p for p in periodos if p.id == dados.historico_ferias_id), None)
        if periodo is None:
            raise HTTPException(status_code=404, detail="Período aquisitivo não encontrado")
    else:
        periodo = next((p for p in periodos if p.saldo_dias > 0), None)
        if periodo is None:
            raise HTTPException(status_code=422, detail="Não há saldo de férias disponível")

    if dados.dias > periodo.saldo_dias:
        raise HTTPException(
            status_code=422,
            detail=f"Saldo insuficiente no período: disponível {periodo.saldo_dias} dia(s)",
        )

    data_fim = dados.data_inicio + timedelta(days=dados.dias - 1)
    conflito = db.scalar(
        select(GozoFerias.id)
        .join(HistoricoFerias)
        .where(
            HistoricoFerias.trabalhador_id == trabalhador.id,
            GozoFerias.data_inicio <= data_fim,
            GozoFerias.data_fim >= dados.data_inicio,
        )
    )
    if conflito:
        raise HTTPException(status_code=409, detail="Já existem férias registradas nesse intervalo de datas")

    periodo.gozos.append(GozoFerias(
        data_inicio=dados.data_inicio, data_fim=data_fim, dias=dados.dias, observacao=dados.observacao,
    ))
    periodo.dias_gozados += dados.dias
    periodo.saldo_dias = periodo.dias_adquiridos - periodo.dias_gozados
    db.commit()
    return _resumo(db, trabalhador)


@router.delete("/gozos/{gozo_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_gozo(gozo_id: int, db: Session = Depends(get_db)):
    gozo = db.get(GozoFerias, gozo_id)
    if gozo is None:
        raise HTTPException(status_code=404, detail="Registro de férias não encontrado")
    periodo = gozo.periodo
    periodo.dias_gozados -= gozo.dias
    periodo.saldo_dias = periodo.dias_adquiridos - periodo.dias_gozados
    db.delete(gozo)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
