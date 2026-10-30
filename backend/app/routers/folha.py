import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from ..database import get_db
from ..deps import exigir_admin, usuario_atual
from ..models import FolhaPagamento, StatusFolha, TipoContrato, Trabalhador
from ..schemas import CalcularFolhaIn, DiasUteisOut, FolhaOut, MesAno, PagamentoFolhaIn
from ..services.calculo_folha import gerar_ou_atualizar, vt_por_dia
from ..services.calendario import dias_uteis
from .contratante import obter_contratante
from .trabalhadores import obter_trabalhador

router = APIRouter(prefix="/folha", tags=["Folha de pagamento"], dependencies=[Depends(usuario_atual)])


def _saida(folha: FolhaPagamento) -> FolhaOut:
    dados = {c.name: getattr(folha, c.name) for c in FolhaPagamento.__table__.columns}
    dados["detalhamento"] = json.loads(folha.detalhamento) if folha.detalhamento else None
    dados["trabalhador_nome"] = folha.trabalhador.nome
    dados["tipo_contrato"] = folha.trabalhador.tipo_contrato
    return FolhaOut.model_validate(dados)


def _obter(db: Session, folha_id: int) -> FolhaPagamento:
    folha = db.scalar(
        select(FolhaPagamento).options(joinedload(FolhaPagamento.trabalhador)).where(FolhaPagamento.id == folha_id)
    )
    if folha is None:
        raise HTTPException(status_code=404, detail="Folha não encontrada")
    return folha


@router.get("", response_model=list[FolhaOut])
def listar(mes_ano: str | None = None, trabalhador_id: int | None = None, db: Session = Depends(get_db)):
    consulta = select(FolhaPagamento).join(Trabalhador).options(joinedload(FolhaPagamento.trabalhador)).order_by(
        FolhaPagamento.mes_ano.desc(), Trabalhador.nome
    )
    if mes_ano:
        consulta = consulta.where(FolhaPagamento.mes_ano == mes_ano)
    if trabalhador_id:
        consulta = consulta.where(FolhaPagamento.trabalhador_id == trabalhador_id)
    return [_saida(f) for f in db.scalars(consulta).all()]


@router.post("/calcular", response_model=FolhaOut)
def calcular(dados: CalcularFolhaIn, db: Session = Depends(get_db)):
    """Calcula (ou recalcula) a folha do mês e grava como rascunho."""
    trabalhador = obter_trabalhador(db, dados.trabalhador_id)
    try:
        folha = gerar_ou_atualizar(db, trabalhador, dados.mes_ano, dados.dias_trabalhados, dados.dias_uteis)
    except ValueError as erro:
        raise HTTPException(status_code=409, detail=str(erro))
    return _saida(folha)


@router.get("/dias-uteis", response_model=list[DiasUteisOut])
def sugerir_dias_uteis(mes_ano: MesAno, db: Session = Depends(get_db)):
    """Dias úteis sugeridos no mês para cada trabalhador (dias da semana dele, sem feriados nacionais)."""
    trabalhadores = db.scalars(select(Trabalhador).options(selectinload(Trabalhador.beneficios))).all()
    return [
        DiasUteisOut(
            trabalhador_id=t.id,
            dias_uteis=dias_uteis(mes_ano, t.dias_semana_trabalho),
            tem_vt_diario=any(vt_por_dia(b) for b in t.beneficios),
        )
        for t in trabalhadores
    ]


@router.get("/esocial.{formato}")
def guia_esocial(formato: str, mes_ano: MesAno, db: Session = Depends(get_db)):
    """Guia para digitar a folha dos empregados com registro no eSocial (que não importa arquivos)."""
    if formato not in ("pdf", "csv"):
        raise HTTPException(status_code=404, detail="Formato deve ser pdf ou csv")
    # Import tardio: fpdf2 só é carregado quando alguém gera documento
    from ..services import guia_esocial

    folhas = db.scalars(
        select(FolhaPagamento).join(Trabalhador)
        .options(joinedload(FolhaPagamento.trabalhador).selectinload(Trabalhador.reajustes))
        .where(FolhaPagamento.mes_ano == mes_ano, Trabalhador.tipo_contrato == TipoContrato.com_registro)
        .order_by(Trabalhador.nome)
    ).all()
    if formato == "csv":
        conteudo, tipo = guia_esocial.gerar_csv(folhas), "text/csv; charset=utf-8"
    else:
        conteudo, tipo = guia_esocial.gerar_pdf(folhas, mes_ano), "application/pdf"
    disposicao = "inline" if formato == "pdf" else "attachment"
    return Response(content=conteudo, media_type=tipo,
                    headers={"Content-Disposition": f'{disposicao}; filename="esocial_{mes_ano}.{formato}"'})


@router.get("/{folha_id}", response_model=FolhaOut)
def detalhar(folha_id: int, db: Session = Depends(get_db)):
    return _saida(_obter(db, folha_id))


@router.post("/{folha_id}/fechar", response_model=FolhaOut)
def fechar(folha_id: int, db: Session = Depends(get_db)):
    folha = _obter(db, folha_id)
    if folha.status == StatusFolha.fechada:
        raise HTTPException(status_code=409, detail="Folha já está fechada")
    folha.status = StatusFolha.fechada
    folha.fechado_em = datetime.now()
    db.commit()
    return _saida(folha)


@router.post("/{folha_id}/reabrir", response_model=FolhaOut, dependencies=[Depends(exigir_admin)])
def reabrir(folha_id: int, db: Session = Depends(get_db)):
    folha = _obter(db, folha_id)
    if folha.pago_em:
        raise HTTPException(status_code=409, detail="Folha já paga: desfaça o pagamento antes de reabrir")
    folha.status = StatusFolha.rascunho
    folha.fechado_em = None
    db.commit()
    return _saida(folha)


@router.post("/{folha_id}/pagar", response_model=FolhaOut)
def registrar_pagamento(folha_id: int, dados: PagamentoFolhaIn | None = None, db: Session = Depends(get_db)):
    """Marca o líquido como pago. Folha paga não pode mais mudar, então é fechada junto."""
    folha = _obter(db, folha_id)
    folha.pago_em = (dados or PagamentoFolhaIn()).pago_em
    if folha.status != StatusFolha.fechada:
        folha.status = StatusFolha.fechada
        folha.fechado_em = datetime.now()
    db.commit()
    return _saida(folha)


@router.delete("/{folha_id}/pagamento", response_model=FolhaOut)
def desfazer_pagamento(folha_id: int, db: Session = Depends(get_db)):
    folha = _obter(db, folha_id)
    folha.pago_em = None
    db.commit()
    return _saida(folha)


@router.delete("/{folha_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(folha_id: int, db: Session = Depends(get_db)):
    folha = _obter(db, folha_id)
    if folha.status == StatusFolha.fechada:
        raise HTTPException(status_code=409, detail="Não é possível excluir uma folha fechada")
    db.delete(folha)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{folha_id}/recibo.pdf")
def recibo_pdf(folha_id: int, db: Session = Depends(get_db)):
    # Import tardio: fpdf2 carrega Pillow e fontTools (~20 MB de RAM); só paga quem gerar PDF
    from ..services.recibo_pdf import gerar_recibo_pdf

    folha = _obter(db, folha_id)
    nome_arquivo = f"recibo_{folha.mes_ano}_{folha.trabalhador.nome.split()[0].lower()}.pdf"
    return Response(
        content=gerar_recibo_pdf(folha, obter_contratante(db)),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nome_arquivo}"'},
    )
