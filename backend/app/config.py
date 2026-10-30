import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/database.db")

SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave-no-arquivo-env")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
# Custo do bcrypt: 12 (padrão da lib) leva ~1,5 s por login no Pi 3; 10 leva ~0,4 s.
# Hashes já gravados continuam válidos (o custo fica embutido no próprio hash).
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "10"))

# Administrador criado automaticamente na primeira inicialização (banco sem usuários)
ADMIN_NOME = os.getenv("ADMIN_NOME", "Administrador")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@local")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


def garantir_diretorio_sqlite() -> None:
    """Cria o diretório do arquivo SQLite, se necessário."""
    prefixo = "sqlite:///"
    if DATABASE_URL.startswith(prefixo):
        caminho = Path(DATABASE_URL[len(prefixo):])
        caminho.parent.mkdir(parents=True, exist_ok=True)
