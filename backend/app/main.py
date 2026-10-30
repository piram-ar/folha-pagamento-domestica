import asyncio
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
from .routers import auth, contratante, eventos, ferias, folha, inss, notificacoes, trabalhadores, usuarios
from .security import gerar_hash_senha
from .services.notificacoes import enviar_avisos_do_dia
from .services.salario import aplicar_reajustes_vigentes

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


def tarefas_periodicas() -> bool:
    """Aplica reajustes que entraram em vigor e envia os avisos de pagamento pendentes.
    Retorna False se o envio de avisos falhou."""
    with SessionLocal() as db:
        try:
            aplicar_reajustes_vigentes(db)
        except Exception as erro:  # noqa: BLE001 - não impede o envio dos avisos
            log.warning("Falha ao aplicar reajustes salariais: %s", erro)
            db.rollback()
        try:
            enviar_avisos_do_dia(db)
            return True
        except Exception as erro:  # noqa: BLE001 - o erro fica registrado e aparece na tela de avisos
            log.warning("Falha ao enviar avisos de pagamento: %s", erro)
            return False


async def executar_periodicamente() -> None:
    # A cada 10 min; após uma falha (senha errada, sem internet), espera 1 h para tentar de novo
    while True:
        ok = await to_thread.run_sync(tarefas_periodicas)
        await asyncio.sleep(600 if ok else 3600)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Rotas síncronas rodam num pool de threads (padrão: 40). Com SQLite e 1 GB de RAM,
    # poucas threads bastam e evitam picos de memória.
    to_thread.current_default_thread_limiter().total_tokens = 4
    aplicar_migracoes()
    criar_admin_inicial()
    tarefa = asyncio.create_task(executar_periodicamente())
    yield
    tarefa.cancel()


app = FastAPI(
    title="Folha Doméstica", version="1.0.0", lifespan=lifespan,
    docs_url="/api/docs", openapi_url="/api/openapi.json",
)

for modulo in (auth, usuarios, contratante, trabalhadores, eventos, folha, ferias, inss, notificacoes):
    app.include_router(modulo.router, prefix="/api")
app.include_router(notificacoes.publico, prefix="/api")


@app.get("/api/health", tags=["Sistema"])
def health():
    return {"status": "ok"}
