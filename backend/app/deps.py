import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import PerfilUsuario, Usuario
from .security import decodificar_token

bearer = HTTPBearer(auto_error=False)

# Com a troca de senha pendente, a sessão só serve para ver o próprio usuário e definir a senha nova
ROTAS_TROCA_DE_SENHA = {"/api/auth/me", "/api/auth/senha"}


def usuario_atual(
    request: Request,
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    erro = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessão inválida ou expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if cred is None:
        raise erro
    try:
        payload = decodificar_token(cred.credentials)
        usuario_id = int(payload["sub"])
        versao = int(payload.get("v", 0))
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise erro
    usuario = db.get(Usuario, usuario_id)
    # Senha, perfil ou situação mudaram depois do login: a sessão antiga deixa de valer
    if usuario is None or not usuario.ativo or versao != usuario.versao_sessao:
        raise erro
    if usuario.trocar_senha and request.url.path not in ROTAS_TROCA_DE_SENHA:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Defina uma nova senha para continuar")
    return usuario


def exigir_admin(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
    if usuario.perfil != PerfilUsuario.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    return usuario
