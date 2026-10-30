from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import exigir_admin, usuario_atual
from ..models import Contratante
from ..schemas import ContratanteIn, ContratanteOut

router = APIRouter(prefix="/contratante", tags=["Empregador / contratante"], dependencies=[Depends(usuario_atual)])

ID_UNICO = 1


def obter_contratante(db: Session) -> Contratante | None:
    return db.get(Contratante, ID_UNICO)


@router.get("", response_model=ContratanteOut | None)
def detalhar(db: Session = Depends(get_db)):
    """Retorna null enquanto os dados ainda não foram cadastrados."""
    return obter_contratante(db)


@router.put("", response_model=ContratanteOut, dependencies=[Depends(exigir_admin)])
def salvar(dados: ContratanteIn, db: Session = Depends(get_db)):
    contratante = obter_contratante(db) or Contratante(id=ID_UNICO)
    for campo, valor in dados.model_dump().items():
        setattr(contratante, campo, valor)
    db.add(contratante)
    db.commit()
    db.refresh(contratante)
    return contratante
