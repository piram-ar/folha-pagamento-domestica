import os
import secrets
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/database.db")

# Valores de exemplo que já circularam no código e na documentação: quem os conhece forja o login de qualquer usuário
CHAVES_PUBLICAS = {"troque-esta-chave-no-arquivo-env", "troque-por-uma-chave-longa-e-aleatoria"}
TAMANHO_MINIMO_CHAVE = 32


def _pasta_dos_dados() -> Path:
    prefixo = "sqlite:///"
    if DATABASE_URL.startswith(prefixo):
        return Path(DATABASE_URL[len(prefixo):]).parent
    return Path("./data")


def _chave_secreta() -> str:
    """Chave que assina os tokens de login.

    Definida no .env: precisa ser longa e não pode ser um dos exemplos públicos (a API não sobe).
    Ausente: gera uma aleatória e guarda ao lado do banco (data/secret_key), para os logins
    sobreviverem a um reinício. Nunca há chave padrão fixa no código.
    """
    chave = os.getenv("SECRET_KEY")
    if chave is not None:
        chave = chave.strip()
        if chave in CHAVES_PUBLICAS or len(chave) < TAMANHO_MINIMO_CHAVE:
            raise RuntimeError(
                f"SECRET_KEY inválida no .env: use ao menos {TAMANHO_MINIMO_CHAVE} caracteres aleatórios "
                "(gere com: openssl rand -hex 32) ou apague a linha para a API gerar uma sozinha."
            )
        return chave
    arquivo = _pasta_dos_dados() / "secret_key"
    if arquivo.exists():
        chave = arquivo.read_text(encoding="ascii").strip()
        if len(chave) >= TAMANHO_MINIMO_CHAVE:
            return chave
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    chave = secrets.token_hex(32)
    arquivo.write_text(chave, encoding="ascii")
    try:
        arquivo.chmod(0o600)
    except OSError:  # Windows: sem permissões no estilo Unix
        pass
    return chave


SECRET_KEY = _chave_secreta()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
# Custo do bcrypt: 12 (padrão da lib) leva ~1,5 s por login no Pi 3; 10 leva ~0,4 s.
# Hashes já gravados continuam válidos (o custo fica embutido no próprio hash).
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "10"))

# Administrador criado automaticamente na primeira inicialização (banco sem usuários)
ADMIN_NOME = os.getenv("ADMIN_NOME", "Administrador")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@local")
# Senha só do primeiro acesso: no login, o sistema obriga a trocar por uma pessoal
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
SENHA_MINIMA = 10

# Login: após TENTATIVAS_LOGIN erros seguidos, o e-mail (ou o endereço de origem) fica bloqueado por BLOQUEIO_LOGIN_MINUTOS
TENTATIVAS_LOGIN = int(os.getenv("TENTATIVAS_LOGIN", "5"))
BLOQUEIO_LOGIN_MINUTOS = int(os.getenv("BLOQUEIO_LOGIN_MINUTOS", "15"))

# Documentação interativa da API (/api/docs): desligada, salvo para testes (API_DOCS=1)
API_DOCS = os.getenv("API_DOCS", "0") == "1"


def garantir_diretorio_sqlite() -> None:
    """Cria o diretório do arquivo SQLite, se necessário."""
    prefixo = "sqlite:///"
    if DATABASE_URL.startswith(prefixo):
        caminho = Path(DATABASE_URL[len(prefixo):])
        caminho.parent.mkdir(parents=True, exist_ok=True)
