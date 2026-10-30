import logging
import warnings
from contextlib import asynccontextmanager
from pathlib import Path

from anyio import to_thread
from fastapi import FastAPI
from sqlalchemy import exc as sa_exc
from sqlalchemy import func, select

from . import config
from .database import SessionLocal
from .models import PerfilUsuario, Usuario
from .routers import auth, contratante, eventos, ferias, folha, trabalhadores, usuarios
from .security import gerar_hash_senha

# SQLite não tem tipo DECIMAL nativo; o SQLAlchemy converte e avisa. Os valores são arredondados a 2 casas.
warnings.filterwarnings("ignore", category=sa_exc.SAWarning, message=".*Decimal objects natively.*")

log = logging.getLogger("folha")


def criar_admin_inicial() -> None:
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Usuario)) == 0:
            db.add(Usuario(
                nome=config.ADMIN_NOME,
                email=config.ADMIN_EMAIL.strip().lower(),
                senha_hash=gerar_hash_senha(config.ADMIN_PASSWORD),
                perfil=PerfilUsuario.admin,
                ativo=True,
            ))
            db.commit()
            log.warning("Administrador inicial criado: %s (troque a senha após o primeiro acesso)", config.ADMIN_EMAIL)


def aplicar_migracoes() -> None:
    """Roda o `alembic upgrade head` no mesmo processo da API.

    No Pi 3 isso evita subir um segundo interpretador Python (e reimportar
    SQLAlchemy/modelos) a cada boot do container.
    """
    from alembic import command
    from alembic.config import Config

    raiz = Path(__file__).resolve().parent.parent
    cfg = Config(str(raiz / "alembic.ini"))
    cfg.set_main_option("script_location", str(raiz / "alembic"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Rotas síncronas rodam num pool de threads (padrão: 40). Com SQLite e 1 GB de RAM,
    # poucas threads bastam e evitam picos de memória.
    to_thread.current_default_thread_limiter().total_tokens = 4
    aplicar_migracoes()
    criar_admin_inicial()
    yield


app = FastAPI(
    title="Folha Doméstica", version="1.0.0", lifespan=lifespan,
    docs_url="/api/docs", openapi_url="/api/openapi.json",
)

for modulo in (auth, usuarios, contratante, trabalhadores, eventos, folha, ferias):
    app.include_router(modulo.router, prefix="/api")


@app.get("/api/health", tags=["Sistema"])
def health():
    return {"status": "ok"}
