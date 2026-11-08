from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import usuario_atual
from ..models import Usuario
from ..schemas import LoginIn, TokenOut, TrocaSenhaIn, UsuarioOut
from ..security import criar_token, gerar_hash_senha, limite_por_email, limite_por_origem, verificar_senha

router = APIRouter(prefix="/auth", tags=["Autenticação"])


def _origem(request: Request) -> str:
    # Atrás do Nginx, o uvicorn (--proxy-headers) já põe aqui o IP real repassado em X-Forwarded-For
    return "ip:" + (request.client.host if request.client else "?")


@router.post("/login", response_model=TokenOut)
def login(dados: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = dados.email.strip().lower()
    chave_email, chave_origem = "email:" + email, _origem(request)
    espera = max(limite_por_email.segundos_bloqueado(chave_email), limite_por_origem.segundos_bloqueado(chave_origem))
    if espera:
        minutos = -(-espera // 60)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Muitas tentativas com senha errada. Tente de novo em {minutos} min.",
            headers={"Retry-After": str(espera)},
        )
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))
    # Sempre roda o bcrypt (mesmo sem usuário): o tempo de resposta não revela quais e-mails existem
    if not verificar_senha(dados.senha, usuario.senha_hash if usuario else None) or usuario is None:
        limite_por_email.registrar_erro(chave_email)
        limite_por_origem.registrar_erro(chave_origem)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha incorretos")
    if not usuario.ativo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário desativado")
    limite_por_email.limpar(chave_email)
    return TokenOut(access_token=criar_token(usuario.id, usuario.perfil.value, usuario.versao_sessao), usuario=usuario)


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(usuario_atual)):
    return usuario


@router.post("/senha", response_model=TokenOut)
def trocar_senha(dados: TrocaSenhaIn, request: Request, usuario: Usuario = Depends(usuario_atual),
                 db: Session = Depends(get_db)):
    """A própria pessoa troca a senha. As outras sessões (outros aparelhos) são encerradas; esta recebe um token novo."""
    chave = "troca:" + str(usuario.id)
    if limite_por_email.segundos_bloqueado(chave):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Muitas tentativas com a senha atual errada. Aguarde alguns minutos.")
    if not verificar_senha(dados.senha_atual, usuario.senha_hash):
        limite_por_email.registrar_erro(chave)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta")
    if dados.senha_nova == dados.senha_atual or verificar_senha(dados.senha_nova, usuario.senha_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A nova senha precisa ser diferente da atual")
    if dados.senha_nova.strip().lower() in {"admin123", "1234567890", "0123456789", "senha12345", "folhadomestica"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Escolha uma senha menos óbvia")
    usuario.senha_hash = gerar_hash_senha(dados.senha_nova)
    usuario.trocar_senha = False
    usuario.versao_sessao += 1
    db.commit()
    db.refresh(usuario)
    limite_por_email.limpar(chave)
    return TokenOut(access_token=criar_token(usuario.id, usuario.perfil.value, usuario.versao_sessao), usuario=usuario)
