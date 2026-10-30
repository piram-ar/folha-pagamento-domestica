# Imagem multi-arquitetura: funciona em arm64 (Raspberry Pi 3 com SO 64-bit) e x86_64
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Menos arenas do malloc = menos RAM fragmentada com o pool de threads do FastAPI
    MALLOC_ARENA_MAX=2 \
    DATABASE_URL=sqlite:////data/database.db \
    TZ=America/Sao_Paulo

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
# Pré-compila o bytecode na imagem: o boot no Pi não precisa recompilar o código
RUN python -m compileall -q app alembic

VOLUME ["/data"]
EXPOSE 8000

# As migrações rodam dentro do próprio processo da API (ver app/main.py).
# 1 worker (SQLite + 1 GB de RAM); sem access log: o Nginx já registra e poupa o cartão SD.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", \
     "--no-access-log", "--proxy-headers", "--forwarded-allow-ips=*"]
