from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import exigir_admin, usuario_atual
from ..models import FaixaInss, TabelaInss
from ..schemas import TabelaInssIn, TabelaInssOut
from ..services.inss import tabela_vigente

router = APIRouter(prefix="/inss", tags=["Tabela do INSS"], dependencies=[Depends(usuario_atual)])


def _saida(tabela: TabelaInss, vigente_id: int | None) -> TabelaInssOut:
    saida = TabelaInssOut.model_validate(tabela)
    saida.vigente = tabela.id == vigente_id
    return saida


def _vigencia_em_uso(db: Session, vigencia: date, ignorar_id: int | None = None) -> bool:
    consulta = select(TabelaInss.id).where(TabelaInss.vigencia_inicio == vigencia)
    if ignorar_id:
        consulta = consulta.where(TabelaInss.id != ignorar_id)
    return db.scalar(consulta) is not None


def _obter(db: Session, tabela_id: int) -> TabelaInss:
    tabela = db.get(TabelaInss, tabela_id)
    if tabela is None:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    return tabela


@router.get("/tabelas", response_model=list[TabelaInssOut])
def listar(db: Session = Depends(get_db)):
    """Todas as tabelas, da vigência mais recente para a mais antiga."""
    vigente = tabela_vigente(db, date.today())
    tabelas = db.scalars(
        select(TabelaInss).options(selectinload(TabelaInss.faixas)).order_by(TabelaInss.vigencia_inicio.desc())
    ).all()
    return [_saida(t, vigente.id if vigente else None) for t in tabelas]


def _salvar(db: Session, tabela: TabelaInss, dados: TabelaInssIn) -> TabelaInssOut:
    if _vigencia_em_uso(db, dados.vigencia_inicio, tabela.id):
        raise HTTPException(status_code=409, detail=f"Já existe uma tabela com vigência em {dados.vigencia_inicio:%m/%Y}")
    tabela.vigencia_inicio = dados.vigencia_inicio
    tabela.descricao = dados.descricao
    tabela.faixas = [FaixaInss(teto=f.teto, aliquota=f.aliquota) for f in dados.faixas]
    db.add(tabela)
    db.commit()
    db.refresh(tabela)
    vigente = tabela_vigente(db, date.today())
    return _saida(tabela, vigente.id if vigente else None)


@router.post("/tabelas", response_model=TabelaInssOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(exigir_admin)])
def criar(dados: TabelaInssIn, db: Session = Depends(get_db)):
    return _salvar(db, TabelaInss(), dados)


@router.put("/tabelas/{tabela_id}", response_model=TabelaInssOut, dependencies=[Depends(exigir_admin)])
def atualizar(tabela_id: int, dados: TabelaInssIn, db: Session = Depends(get_db)):
    """Só afeta folhas calculadas ou recalculadas depois; folhas fechadas mantêm os valores."""
    return _salvar(db, _obter(db, tabela_id), dados)


@router.delete("/tabelas/{tabela_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(exigir_admin)])
def excluir(tabela_id: int, db: Session = Depends(get_db)):
    db.delete(_obter(db, tabela_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
