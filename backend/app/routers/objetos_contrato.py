from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import exigir_admin, usuario_atual
from ..models import ObjetoContrato, Trabalhador
from ..schemas import ObjetoContratoIn, ObjetoContratoOut

router = APIRouter(prefix="/objetos-contrato", tags=["Objetos do contrato"], dependencies=[Depends(usuario_atual)])


def _obter(db: Session, objeto_id: int) -> ObjetoContrato:
    objeto = db.get(ObjetoContrato, objeto_id)
    if objeto is None:
        raise HTTPException(status_code=404, detail="Objeto do contrato não encontrado")
    return objeto


def _trabalhadores_por_objeto(db: Session) -> dict[int, int]:
    return dict(db.execute(
        select(Trabalhador.objeto_contrato_id, func.count()).group_by(Trabalhador.objeto_contrato_id)
    ).all())


def _saida(objeto: ObjetoContrato, em_uso: int) -> ObjetoContratoOut:
    return ObjetoContratoOut(id=objeto.id, descricao=objeto.descricao, ativo=objeto.ativo, trabalhadores=em_uso)


def _salvar(db: Session, objeto: ObjetoContrato, dados: ObjetoContratoIn) -> ObjetoContratoOut:
    repetido = db.scalar(select(ObjetoContrato.id).where(
        func.lower(ObjetoContrato.descricao) == dados.descricao.lower(), ObjetoContrato.id != (objeto.id or 0)))
    if repetido:
        raise HTTPException(status_code=409, detail="Já existe um objeto do contrato com esta descrição")
    objeto.descricao = dados.descricao
    objeto.ativo = dados.ativo
    db.add(objeto)
    db.commit()
    return _saida(objeto, _trabalhadores_por_objeto(db).get(objeto.id, 0))


@router.get("", response_model=list[ObjetoContratoOut])
def listar(apenas_ativos: bool = False, db: Session = Depends(get_db)):
    consulta = select(ObjetoContrato).order_by(ObjetoContrato.descricao)
    if apenas_ativos:
        consulta = consulta.where(ObjetoContrato.ativo)
    em_uso = _trabalhadores_por_objeto(db)
    return [_saida(o, em_uso.get(o.id, 0)) for o in db.scalars(consulta).all()]


@router.post("", response_model=ObjetoContratoOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(exigir_admin)])
def criar(dados: ObjetoContratoIn, db: Session = Depends(get_db)):
    return _salvar(db, ObjetoContrato(), dados)


@router.put("/{objeto_id}", response_model=ObjetoContratoOut, dependencies=[Depends(exigir_admin)])
def atualizar(objeto_id: int, dados: ObjetoContratoIn, db: Session = Depends(get_db)):
    """A nova descrição vale para todos os recibos, inclusive os reimpressos de meses passados."""
    return _salvar(db, _obter(db, objeto_id), dados)


@router.delete("/{objeto_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(exigir_admin)])
def excluir(objeto_id: int, db: Session = Depends(get_db)):
    objeto = _obter(db, objeto_id)
    if _trabalhadores_por_objeto(db).get(objeto.id):
        raise HTTPException(status_code=409, detail="Objeto em uso por trabalhadores: desative-o em vez de excluir.")
    db.delete(objeto)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
