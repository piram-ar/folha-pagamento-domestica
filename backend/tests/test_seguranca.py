"""Testes de segurança da API: app real, banco temporário.

    cd backend && pip install -r requirements.txt -r requirements-dev.txt && python -m pytest tests -q

A ordem importa (o mesmo banco segue de um teste para o outro); os de força bruta ficam por último porque
bloqueiam o login.
"""
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PASTA = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite:///" + PASTA.replace("\\", "/") + "/t.db"
os.environ.pop("SECRET_KEY", None)
os.environ.pop("API_DOCS", None)
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.main import app  # noqa: E402

SENHA_ADMIN = "senha-do-admin-2026"
SENHA_COMUM = "senha-da-pessoa-2026"


def _b64(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


def _cabecalho(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def c():
    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield cliente


@pytest.fixture(scope="module")
def cenario(c):
    """Admin com senha própria, um usuário padrão, um objeto do contrato e um trabalhador."""
    r = c.post("/api/auth/login", json={"email": "admin@local", "senha": "admin123"})
    assert r.status_code == 200 and r.json()["usuario"]["trocar_senha"] is True
    provisorio = _cabecalho(r.json()["access_token"])
    # Antes de trocar a senha de instalação, nada além de /auth/me e /auth/senha
    assert c.get("/api/trabalhadores", headers=provisorio).status_code == 403
    assert c.get("/api/auth/me", headers=provisorio).status_code == 200
    r = c.post("/api/auth/senha", json={"senha_atual": "admin123", "senha_nova": SENHA_ADMIN}, headers=provisorio)
    assert r.status_code == 200, r.text
    H = _cabecalho(r.json()["access_token"])
    assert c.get("/api/trabalhadores", headers=provisorio).status_code == 401  # o token antigo morreu

    obj = c.post("/api/objetos-contrato", json={"descricao": "Serviços gerais"}, headers=H).json()
    t = c.post("/api/trabalhadores", json={
        "nome": "Łukasz “Zé” Świętek – 🙂", "cpf": "52998224725", "tipo_contrato": "com_registro",
        "salario_base": "1800", "data_admissao": "2024-01-02", "objeto_contrato_id": obj["id"]}, headers=H).json()
    assert c.post("/api/usuarios", json={"nome": "Comum", "email": "comum@local", "senha": "curta",
                                         "perfil": "padrao"}, headers=H).status_code == 422  # senha < 10
    assert c.post("/api/usuarios", json={"nome": "Comum", "email": "comum@local", "senha": "provisoria-123",
                                         "perfil": "padrao"}, headers=H).status_code == 201
    r = c.post("/api/auth/login", json={"email": "comum@local", "senha": "provisoria-123"})
    assert r.json()["usuario"]["trocar_senha"] is True  # senha escolhida pelo admin: troca no 1º acesso
    r = c.post("/api/auth/senha", json={"senha_atual": "provisoria-123", "senha_nova": SENHA_COMUM},
               headers=_cabecalho(r.json()["access_token"]))
    P = _cabecalho(r.json()["access_token"])
    return {"H": H, "P": P, "obj": obj, "t": t}


def test_toda_rota_exige_login(c, cenario):
    publicas = {"/api/auth/login", "/api/health", "/api/notificacoes/assinatura/{token}.{formato}"}
    abertas, testadas = [], 0
    # O esquema OpenAPI é gerado em memória (a rota /api/openapi.json fica desligada)
    for caminho, metodos in app.openapi()["paths"].items():
        if caminho in publicas:
            continue
        url = re.sub(r"\{[^}]+\}", "1", caminho.replace("{formato}", "pdf"))
        for metodo in metodos:
            testadas += 1
            r = c.request(metodo.upper(), url, params={"mes_ano": "2026-10", "ano": 2026})
            if r.status_code != 401:
                abertas.append(f"{metodo.upper()} {caminho} -> {r.status_code}")
    assert testadas > 60 and not abertas


def test_documentacao_da_api_fechada(c):
    assert c.get("/api/docs").status_code == 404
    assert c.get("/api/openapi.json").status_code == 404


def test_usuario_padrao_bloqueado_nas_acoes_de_admin(c, cenario):
    H, P, t = cenario["H"], cenario["P"], cenario["t"]
    folha = c.post("/api/folha/calcular", json={"trabalhador_id": t["id"], "mes_ano": "2026-09",
                                                "dias_trabalhados": 30}, headers=H).json()
    assert c.post(f"/api/folha/{folha['id']}/pagar", json={}, headers=H).status_code == 200
    tentativas = {
        "listar usuários": c.get("/api/usuarios", headers=P),
        "criar admin": c.post("/api/usuarios", json={"nome": "X", "email": "x@x", "senha": "1234567890ab",
                                                     "perfil": "admin"}, headers=P),
        "promover a si mesmo": c.put("/api/usuarios/2", json={"perfil": "admin"}, headers=P),
        "alterar contratante": c.put("/api/contratante", json={"nome": "Outro"}, headers=P),
        "alterar tabela INSS": c.post("/api/inss/tabelas", json={}, headers=P),
        "alterar SMTP": c.put("/api/notificacoes/config", json={}, headers=P),
        "trocar link do calendário": c.post("/api/notificacoes/novo-link", headers=P),
        "reabrir folha": c.post(f"/api/folha/{folha['id']}/reabrir", headers=P),
        "criar objeto do contrato": c.post("/api/objetos-contrato", json={"descricao": "abc"}, headers=P),
        "desfazer pagamento da folha": c.delete(f"/api/folha/{folha['id']}/pagamento", headers=P),
        "desfazer pagamento de férias": c.delete("/api/ferias/gozos/1/pagamento", headers=P),
        "desfazer pagamento do 13º": c.delete("/api/decimo-terceiro/1/pagamento", headers=P),
    }
    assert [k for k, r in tentativas.items() if r.status_code != 403] == []
    assert c.delete(f"/api/folha/{folha['id']}/pagamento", headers=H).status_code == 200  # o admin pode


def test_usuario_padrao_nao_ve_segredos_dos_avisos(c, cenario):
    c.post("/api/notificacoes/novo-link", headers=cenario["H"])
    assert c.get("/api/notificacoes/config", headers=cenario["H"]).json()["token_calendario"]
    cfg = c.get("/api/notificacoes/config", headers=cenario["P"]).json()
    assert cfg["token_calendario"] is None and cfg["smtp_usuario"] is None and cfg["ultimo_erro"] is None


def test_tokens_forjados_sao_recusados(c, cenario):
    agora = datetime.now(timezone.utc)
    exp = agora + timedelta(hours=1)
    casos = {
        "alg=none": _b64({"alg": "none", "typ": "JWT"}) + "." + _b64({"sub": "1", "exp": int(exp.timestamp())}) + ".",
        "chave errada": jwt.encode({"sub": "1", "exp": exp}, "outra-chave-qualquer-com-32-caracteres!", algorithm="HS256"),
        "chave antiga do código": jwt.encode({"sub": "1", "v": 1, "exp": exp}, "troque-esta-chave-no-arquivo-env",
                                             algorithm="HS256"),
        "expirado": jwt.encode({"sub": "1", "v": 1, "exp": agora - timedelta(minutes=1)}, config.SECRET_KEY,
                               algorithm="HS256"),
        "sem validade": jwt.encode({"sub": "1", "v": 1}, config.SECRET_KEY, algorithm="HS256"),
        "versão de sessão antiga": jwt.encode({"sub": "1", "v": 0, "exp": exp}, config.SECRET_KEY, algorithm="HS256"),
    }
    aceitos = [k for k, tok in casos.items() if c.get("/api/auth/me", headers=_cabecalho(tok)).status_code != 401]
    assert aceitos == []
    perfil_falso = jwt.encode({"sub": "2", "v": 1, "perfil": "admin", "exp": exp}, config.SECRET_KEY, algorithm="HS256")
    assert c.get("/api/usuarios", headers=_cabecalho(perfil_falso)).status_code == 403  # perfil vem do banco


def test_chave_gerada_e_guardada_ao_lado_do_banco():
    arquivo = Path(PASTA) / "secret_key"
    assert arquivo.read_text().strip() == config.SECRET_KEY and len(config.SECRET_KEY) >= 32


@pytest.mark.parametrize("chave", ["", "curta", "troque-esta-chave-no-arquivo-env", "troque-por-uma-chave-longa-e-aleatoria"])
def test_api_nao_sobe_com_chave_fraca(chave):
    env = {**os.environ, "SECRET_KEY": chave, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, "-c", "import app.config"], cwd=RAIZ, env=env, capture_output=True, encoding="utf-8", errors="replace")
    assert r.returncode != 0 and "SECRET_KEY" in r.stderr


def test_troca_de_senha_e_desativacao_encerram_sessoes(c, cenario):
    H = cenario["H"]
    r = c.post("/api/auth/login", json={"email": "comum@local", "senha": SENHA_COMUM})
    antigo = _cabecalho(r.json()["access_token"])
    c.put("/api/usuarios/2", json={"senha": "definida-pelo-admin"}, headers=H)
    assert c.get("/api/auth/me", headers=antigo).status_code == 401
    r = c.post("/api/auth/login", json={"email": "comum@local", "senha": "definida-pelo-admin"})
    novo = _cabecalho(r.json()["access_token"])
    r = c.post("/api/auth/senha", json={"senha_atual": "definida-pelo-admin", "senha_nova": SENHA_COMUM}, headers=novo)
    cenario["P"] = P = _cabecalho(r.json()["access_token"])
    c.put("/api/usuarios/2", json={"ativo": False}, headers=H)
    assert c.get("/api/auth/me", headers=P).status_code == 401
    c.put("/api/usuarios/2", json={"ativo": True}, headers=H)
    assert c.get("/api/auth/me", headers=P).status_code == 401  # reativar não ressuscita a sessão antiga


def test_troca_de_senha_exige_a_senha_atual(c, cenario):
    r = c.post("/api/auth/senha", json={"senha_atual": "errada", "senha_nova": "outra-senha-longa"}, headers=cenario["H"])
    assert r.status_code == 400


def test_recibos_com_caracteres_fora_do_latin1(c, cenario):
    H, t = cenario["H"], cenario["t"]
    folha = c.post("/api/folha/calcular", json={"trabalhador_id": t["id"], "mes_ano": "2026-10",
                                                "dias_trabalhados": 31}, headers=H).json()
    r = c.get(f"/api/folha/{folha['id']}/recibo.pdf", headers=H)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    disposicao = r.headers["content-disposition"]
    assert 'filename="recibo_2026-10_lukasz.pdf"' in disposicao and "filename*=UTF-8''" in disposicao
    assert c.get("/api/folha/esocial.pdf", params={"mes_ano": "2026-10"}, headers=H).status_code == 200


def test_csv_neutraliza_formulas(c, cenario):
    H = cenario["H"]
    r = c.post("/api/trabalhadores", json={"nome": '=HYPERLINK("http://x","a")', "cpf": "11144477735",
                                           "tipo_contrato": "com_registro", "salario_base": "1500",
                                           "data_admissao": "2024-01-02", "objeto_contrato_id": cenario["obj"]["id"]},
               headers=H)
    c.post("/api/folha/calcular", json={"trabalhador_id": r.json()["id"], "mes_ano": "2026-10",
                                        "dias_trabalhados": 31}, headers=H)
    csv = c.get("/api/folha/esocial.csv", params={"mes_ano": "2026-10"}, headers=H).text
    assert "'=HYPERLINK" in csv
    assert not any(cel.strip('"').startswith("=") for linha in csv.splitlines() for cel in linha.split(";"))


def test_entradas_grandes_e_link_do_calendario(c, cenario):
    assert c.post("/api/auth/login", json={"email": "a" * 100000, "senha": "b" * 100000}).status_code == 422
    assert c.get("/api/notificacoes/proximos", params={"dias": 10**9}, headers=cenario["H"]).status_code == 200
    assert c.get("/api/notificacoes/assinatura/qualquer.ics").status_code == 404


def test_cors_so_para_o_app(c):
    r = c.options("/api/auth/login", headers={"Origin": "http://site-malicioso.com", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers
    r = c.options("/api/auth/login", headers={"Origin": "https://localhost", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "https://localhost"


# ---- Daqui para baixo o login fica bloqueado: manter no fim do arquivo ----

def test_tempo_do_login_nao_revela_emails(c):
    def medir(email):
        t0 = time.perf_counter()
        for _ in range(3):
            c.post("/api/auth/login", json={"email": email, "senha": "x"})
        return (time.perf_counter() - t0) / 3
    existe, nao_existe = medir("comum@local"), medir("ninguem@local")
    assert existe < nao_existe * 2 and nao_existe < existe * 2


def test_login_bloqueia_forca_bruta(c):
    status = [c.post("/api/auth/login", json={"email": "admin@local", "senha": f"errada{i}"}).status_code
              for i in range(8)]
    assert status[:5] == [401] * 5 and set(status[5:]) == {429}
    # Bloqueado inclusive com a senha certa, até passar o tempo
    r = c.post("/api/auth/login", json={"email": "admin@local", "senha": SENHA_ADMIN})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
