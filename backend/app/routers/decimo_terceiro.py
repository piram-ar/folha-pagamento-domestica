from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from ..database import get_db
from ..deps import usuario_atual
from ..models import DecimoTerceiro, Trabalhador
from ..schemas import DecimoTerceiroIn, DecimoTerceiroOut, DecimoTerceiroPreviaOut, PagamentoFolhaIn
from ..services.decimo_terceiro import calcular_parcela, previsao
from .contratante import obter_contratante
from .trabalhadores import obter_trabalhador

router = APIRouter(prefix="/decimo-terceiro", tags=["13º salário"], dependencies=[Depends(usuario_atual)])


def _saida(d: DecimoTerceiro) -> DecimoTerceiroOut:
    dados = {c.name: getattr(d, c.name) for c in DecimoTerceiro.__table__.columns}
    dados["trabalhador_nome"] = d.trabalhador.nome
    dados["tipo_contrato"] = d.trabalhador.tipo_contrato
    return DecimoTerceiroOut.model_validate(dados)


def _obter(db: Session, decimo_id: int) -> DecimoTerceiro:
    d = db.scalar(
        select(DecimoTerceiro).options(joinedload(DecimoTerceiro.trabalhador)).where(DecimoTerceiro.id == decimo_id)
    )
    if d is None:
        raise HTTPException(status_code=404, detail="Parcela do 13º não encontrada")
    return d


@router.get("", response_model=list[DecimoTerceiroOut])
def listar(ano: int | None = None, db: Session = Depends(get_db)):
    consulta = (
        select(DecimoTerceiro).join(Trabalhador).options(joinedload(DecimoTerceiro.trabalhador))
        .order_by(DecimoTerceiro.ano.desc(), DecimoTerceiro.parcela.desc(), Trabalhador.nome)
    )
    if ano:
        consulta = consulta.where(DecimoTerceiro.ano == ano)
    return [_saida(d) for d in db.scalars(consulta).all()]


@router.get("/previa", response_model=list[DecimoTerceiroPreviaOut])
def previa(ano: int, db: Session = Depends(get_db)):
    """13º previsto no ano para cada trabalhador ativo e as parcelas já calculadas."""
    trabalhadores = db.scalars(
        select(Trabalhador)
        .options(selectinload(Trabalhador.reajustes), selectinload(Trabalhador.folhas),
                 selectinload(Trabalhador.decimos_terceiros))
        .where(Trabalhador.ativo)
        .order_by(Trabalhador.nome)
    ).all()
    saida = []
    for t in trabalhadores:
        prevista = previsao(t, ano)
        if not prevista["avos"]:
            continue  # admitido depois do ano
        saida.append(DecimoTerceiroPreviaOut(
            trabalhador_id=t.id, trabalhador_nome=t.nome, tipo_contrato=t.tipo_contrato, **prevista,
            parcelas=[_saida(d) for d in t.decimos_terceiros if d.ano == ano],
        ))
    return saida


@router.post("", response_model=DecimoTerceiroOut)
def calcular(dados: DecimoTerceiroIn, db: Session = Depends(get_db)):
    """Calcula (ou recalcula) a 1ª ou a 2ª parcela do 13º."""
    trabalhador = obter_trabalhador(db, dados.trabalhador_id)
    try:
        d = calcular_parcela(db, trabalhador, dados.ano, dados.parcela, dados.data_pagamento)
    except ValueError as erro:
        raise HTTPException(status_code=409, detail=str(erro))
    db.commit()
    db.refresh(d)
    return _saida(d)


@router.post("/{decimo_id}/pagar", response_model=DecimoTerceiroOut)
def pagar(decimo_id: int, dados: PagamentoFolhaIn | None = None, db: Session = Depends(get_db)):
    d = _obter(db, decimo_id)
    d.pago_em = (dados or PagamentoFolhaIn()).pago_em
    db.commit()
    return _saida(d)


@router.delete("/{decimo_id}/pagamento", response_model=DecimoTerceiroOut)
def desfazer_pagamento(decimo_id: int, db: Session = Depends(get_db)):
    d = _obter(db, decimo_id)
    d.pago_em = None
    db.commit()
    return _saida(d)


@router.delete("/{decimo_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(decimo_id: int, db: Session = Depends(get_db)):
    d = _obter(db, decimo_id)
    if d.pago_em:
        raise HTTPException(status_code=409, detail="Parcela já paga: desfaça o pagamento antes de excluir")
    if d.parcela == 1 and db.scalar(select(DecimoTerceiro.id).where(
            DecimoTerceiro.trabalhador_id == d.trabalhador_id, DecimoTerceiro.ano == d.ano,
            DecimoTerceiro.parcela == 2)):
        raise HTTPException(status_code=409, detail="Exclua a 2ª parcela antes: ela desconta a 1ª")
    db.delete(d)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{decimo_id}/recibo.pdf")
def recibo(decimo_id: int, db: Session = Depends(get_db)):
    from ..services.recibo_avulso import recibo_decimo_terceiro  # import tardio: fpdf2 só quando gera PDF

    d = _obter(db, decimo_id)
    nome = d.trabalhador.nome.split()[0].lower()
    return Response(
        content=recibo_decimo_terceiro(d, obter_contratante(db)),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="13o_{d.ano}_parcela{d.parcela}_{nome}.pdf"'},
    )
