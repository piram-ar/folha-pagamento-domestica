from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from ..database import get_db
from ..deps import usuario_atual
from ..models import GozoFerias, HistoricoFerias, Trabalhador
from ..schemas import (
    CalcularFeriasIn,
    FeriasTrabalhadorOut,
    GozoIn,
    GozoOut,
    PagamentoFeriasOut,
    PagamentoFolhaIn,
    PeriodoFeriasOut,
)
from ..services.ferias import limite_concessivo, sincronizar_periodos, situacao_periodo
from ..services.pagamento_ferias import calcular_pagamento
from .contratante import obter_contratante
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
        tipo_contrato=trabalhador.tipo_contrato,
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

    if dados.dias + dados.dias_abono > periodo.saldo_dias:
        raise HTTPException(
            status_code=422,
            detail=f"Saldo insuficiente no período: disponível {periodo.saldo_dias} dia(s)",
        )
    if dados.dias_abono:
        limite = periodo.dias_adquiridos // 3 - sum(g.dias_abono or 0 for g in periodo.gozos)
        if dados.dias_abono > limite:
            raise HTTPException(
                status_code=422,
                detail=f"O abono pecuniário vai até 1/3 dos dias do período: restam {max(limite, 0)} dia(s) para vender",
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

    gozo = GozoFerias(data_inicio=dados.data_inicio, data_fim=data_fim, dias=dados.dias, dias_abono=dados.dias_abono,
                      observacao=dados.observacao)
    periodo.gozos.append(gozo)
    periodo.dias_gozados += gozo.dias_do_periodo
    periodo.saldo_dias = periodo.dias_adquiridos - periodo.dias_gozados
    calcular_pagamento(db, gozo, dados.data_pagamento)
    db.commit()
    return _resumo(db, trabalhador)


def _pagamento_out(g: GozoFerias) -> PagamentoFeriasOut:
    p, t = g.periodo, g.periodo.trabalhador
    return PagamentoFeriasOut.model_validate({
        **GozoOut.model_validate(g).model_dump(),
        "trabalhador_id": t.id, "trabalhador_nome": t.nome, "tipo_contrato": t.tipo_contrato,
        "periodo_aquisitivo_inicio": p.periodo_aquisitivo_inicio, "periodo_aquisitivo_fim": p.periodo_aquisitivo_fim,
    })


def _obter_gozo(db: Session, gozo_id: int) -> GozoFerias:
    gozo = db.scalar(
        select(GozoFerias)
        .options(joinedload(GozoFerias.periodo).joinedload(HistoricoFerias.trabalhador))
        .where(GozoFerias.id == gozo_id)
    )
    if gozo is None:
        raise HTTPException(status_code=404, detail="Registro de férias não encontrado")
    return gozo


@router.get("/pagamentos", response_model=list[PagamentoFeriasOut])
def listar_pagamentos(trabalhador_id: int | None = None, db: Session = Depends(get_db)):
    """Férias com pagamento calculado (recibos), da mais recente para a mais antiga."""
    consulta = (
        select(GozoFerias).join(HistoricoFerias)
        .options(joinedload(GozoFerias.periodo).joinedload(HistoricoFerias.trabalhador))
        .where(GozoFerias.valor_ferias.is_not(None))
        .order_by(GozoFerias.data_inicio.desc())
    )
    if trabalhador_id:
        consulta = consulta.where(HistoricoFerias.trabalhador_id == trabalhador_id)
    return [_pagamento_out(g) for g in db.scalars(consulta).all()]


@router.post("/gozos/{gozo_id}/calcular", response_model=PagamentoFeriasOut)
def calcular(gozo_id: int, dados: CalcularFeriasIn | None = None, db: Session = Depends(get_db)):
    """Calcula (ou recalcula) o pagamento das férias: salário dos dias + média de horas extras + 1/3."""
    gozo = _obter_gozo(db, gozo_id)
    try:
        calcular_pagamento(db, gozo, dados.data_pagamento if dados else None)
    except ValueError as erro:
        raise HTTPException(status_code=409, detail=str(erro))
    db.commit()
    return _pagamento_out(gozo)


@router.post("/gozos/{gozo_id}/pagar", response_model=PagamentoFeriasOut)
def pagar(gozo_id: int, dados: PagamentoFolhaIn | None = None, db: Session = Depends(get_db)):
    gozo = _obter_gozo(db, gozo_id)
    if gozo.valor_ferias is None:
        raise HTTPException(status_code=409, detail="Calcule o pagamento das férias antes de marcar como pago")
    gozo.pago_em = (dados or PagamentoFolhaIn()).pago_em
    db.commit()
    return _pagamento_out(gozo)


@router.delete("/gozos/{gozo_id}/pagamento", response_model=PagamentoFeriasOut)
def desfazer_pagamento(gozo_id: int, db: Session = Depends(get_db)):
    gozo = _obter_gozo(db, gozo_id)
    gozo.pago_em = None
    db.commit()
    return _pagamento_out(gozo)


@router.get("/gozos/{gozo_id}/recibo.pdf")
def recibo(gozo_id: int, db: Session = Depends(get_db)):
    from ..services.recibo_avulso import recibo_ferias  # import tardio: fpdf2 só quando gera PDF

    gozo = _obter_gozo(db, gozo_id)
    if gozo.valor_ferias is None:
        raise HTTPException(status_code=409, detail="Calcule o pagamento das férias antes de gerar o recibo")
    nome = gozo.periodo.trabalhador.nome.split()[0].lower()
    return Response(
        content=recibo_ferias(gozo, obter_contratante(db)),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="ferias_{gozo.data_inicio:%Y-%m-%d}_{nome}.pdf"'},
    )


@router.delete("/gozos/{gozo_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_gozo(gozo_id: int, db: Session = Depends(get_db)):
    gozo = db.get(GozoFerias, gozo_id)
    if gozo is None:
        raise HTTPException(status_code=404, detail="Registro de férias não encontrado")
    if gozo.pago_em:
        raise HTTPException(status_code=409, detail="Férias já pagas: desfaça o pagamento antes de excluir")
    periodo = gozo.periodo
    periodo.dias_gozados -= gozo.dias_do_periodo
    periodo.saldo_dias = periodo.dias_adquiridos - periodo.dias_gozados
    db.delete(gozo)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
