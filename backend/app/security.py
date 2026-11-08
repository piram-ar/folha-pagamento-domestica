import threading
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import (ACCESS_TOKEN_EXPIRE_MINUTES, BCRYPT_ROUNDS, BLOQUEIO_LOGIN_MINUTOS, JWT_ALGORITHM, SECRET_KEY,
                     TENTATIVAS_LOGIN)


def gerar_hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


# Comparado quando o e-mail não existe: o login leva o mesmo tempo e não revela quais e-mails estão cadastrados
_HASH_FICTICIO = gerar_hash_senha("senha-que-nao-existe")


def verificar_senha(senha: str, senha_hash: str | None) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), (senha_hash or _HASH_FICTICIO).encode("utf-8")) and bool(senha_hash)
    except ValueError:
        return False


def criar_token(usuario_id: int, perfil: str, versao_sessao: int = 0) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(usuario_id), "perfil": perfil, "v": versao_sessao, "exp": expira}
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decodificar_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]})


class LimiteDeLogin:
    """Bloqueia por alguns minutos o e-mail ou o endereço que errou a senha várias vezes seguidas.

    Fica na memória: 1 processo da API (uvicorn --workers 1) e reiniciar o Pi zera as contagens, o que basta
    para frear tentativas automáticas sem gravar nada no cartão SD.
    """

    def __init__(self, tentativas: int, minutos: int):
        self.tentativas = tentativas
        self.janela = minutos * 60
        self._erros: dict[str, list[float]] = {}
        self._trava = threading.Lock()

    def _recentes(self, chave: str, agora: float) -> list[float]:
        erros = [t for t in self._erros.get(chave, []) if agora - t < self.janela]
        if erros:
            self._erros[chave] = erros
        else:
            self._erros.pop(chave, None)
        return erros

    def segundos_bloqueado(self, *chaves: str) -> int:
        """Quanto falta para liberar (0 = liberado)."""
        agora = time.monotonic()
        with self._trava:
            restante = 0.0
            for chave in chaves:
                erros = self._recentes(chave, agora)
                if len(erros) >= self.tentativas:
                    restante = max(restante, self.janela - (agora - erros[-self.tentativas]))
            return int(restante) + 1 if restante else 0

    def registrar_erro(self, *chaves: str) -> None:
        agora = time.monotonic()
        with self._trava:
            if len(self._erros) > 10_000:  # teto de memória contra muitos e-mails inventados
                self._erros.clear()
            for chave in chaves:
                self._erros.setdefault(chave, []).append(agora)

    def limpar(self, *chaves: str) -> None:
        with self._trava:
            for chave in chaves:
                self._erros.pop(chave, None)


# Por endereço de origem o limite é maior: várias pessoas da casa podem errar a senha no mesmo dia
limite_por_email = LimiteDeLogin(TENTATIVAS_LOGIN, BLOQUEIO_LOGIN_MINUTOS)
limite_por_origem = LimiteDeLogin(TENTATIVAS_LOGIN * 4, BLOQUEIO_LOGIN_MINUTOS)
