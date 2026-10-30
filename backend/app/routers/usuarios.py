from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import exigir_admin
from ..models import PerfilUsuario, Usuario
from ..schemas import UsuarioCreate, UsuarioOut, UsuarioUpdate
from ..security import gerar_hash_senha

router = APIRouter(prefix="/usuarios", tags=["Usuários do sistema"], dependencies=[Depends(exigir_admin)])


def _obter(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return usuario


def _email_em_uso(db: Session, email: str, ignorar_id: int | None = None) -> bool:
    consulta = select(Usuario.id).where(Usuario.email == email)
    if ignorar_id:
        consulta = consulta.where(Usuario.id != ignorar_id)
    return db.scalar(consulta) is not None


def _admins_ativos(db: Session) -> int:
    return db.scalar(
        select(func.count()).select_from(Usuario).where(Usuario.perfil == PerfilUsuario.admin, Usuario.ativo)
    )


@router.get("", response_model=list[UsuarioOut])
def listar(db: Session = Depends(get_db)):
    return db.scalars(select(Usuario).order_by(Usuario.nome)).all()


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def criar(dados: UsuarioCreate, db: Session = Depends(get_db)):
    if _email_em_uso(db, dados.email):
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    usuario = Usuario(
        nome=dados.nome, email=dados.email, senha_hash=gerar_hash_senha(dados.senha),
        perfil=dados.perfil, ativo=dados.ativo,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.put("/{usuario_id}", response_model=UsuarioOut)
def atualizar(usuario_id: int, dados: UsuarioUpdate, db: Session = Depends(get_db),
              atual: Usuario = Depends(exigir_admin)):
    usuario = _obter(db, usuario_id)
    campos = dados.model_dump(exclude_unset=True)
    if "email" in campos and _email_em_uso(db, campos["email"], usuario.id):
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")

    deixa_de_ser_admin = (
        usuario.perfil == PerfilUsuario.admin and usuario.ativo
        and (campos.get("perfil", PerfilUsuario.admin) != PerfilUsuario.admin or campos.get("ativo") is False)
    )
    if deixa_de_ser_admin and _admins_ativos(db) <= 1:
        raise HTTPException(status_code=400, detail="É necessário manter ao menos um administrador ativo")
    if usuario.id == atual.id and campos.get("ativo") is False:
        raise HTTPException(status_code=400, detail="Você não pode desativar o próprio usuário")

    senha = campos.pop("senha", None)
    if senha:
        usuario.senha_hash = gerar_hash_senha(senha)
    for campo, valor in campos.items():
        setattr(usuario, campo, valor)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(usuario_id: int, db: Session = Depends(get_db), atual: Usuario = Depends(exigir_admin)):
    usuario = _obter(db, usuario_id)
    if usuario.id == atual.id:
        raise HTTPException(status_code=400, detail="Você não pode excluir o próprio usuário")
    if usuario.perfil == PerfilUsuario.admin and usuario.ativo and _admins_ativos(db) <= 1:
        raise HTTPException(status_code=400, detail="É necessário manter ao menos um administrador ativo")
    db.delete(usuario)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
