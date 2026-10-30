import secrets
from datetime import date, timedelta

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import exigir_admin, usuario_atual
from ..models import ConfigNotificacoes
from ..schemas import ConfigNotificacoesIn, ConfigNotificacoesOut, ProximoPagamentoOut
from ..services import notificacoes as servico
from ..services.pagamentos import pagamentos_entre

router = APIRouter(prefix="/notificacoes", tags=["Avisos de pagamento"])
# Link de assinatura do calendário: aberto pelo app de agenda, sem login (protegido pelo token)
publico = APIRouter(prefix="/notificacoes", tags=["Avisos de pagamento"])

autenticado = [Depends(usuario_atual)]
somente_admin = [Depends(exigir_admin)]


def _saida(config: ConfigNotificacoes) -> ConfigNotificacoesOut:
    dados = {c: getattr(config, c) for c in ConfigNotificacoesOut.model_fields if c != "smtp_senha_definida"}
    return ConfigNotificacoesOut(**dados, smtp_senha_definida=bool(config.smtp_senha))


@router.get("/config", response_model=ConfigNotificacoesOut, dependencies=autenticado)
def ler_config(db: Session = Depends(get_db)):
    return _saida(servico.obter_config(db))


@router.put("/config", response_model=ConfigNotificacoesOut, dependencies=somente_admin)
def salvar_config(dados: ConfigNotificacoesIn, db: Session = Depends(get_db)):
    config = servico.obter_config(db)
    campos = dados.model_dump()
    senha = campos.pop("smtp_senha")
    if senha:  # a senha nunca volta para a tela; vazio mantém a atual
        config.smtp_senha = senha
    for campo, valor in campos.items():
        setattr(config, campo, valor.strip() if isinstance(valor, str) else valor)
    db.commit()
    return _saida(config)


@router.post("/teste", dependencies=somente_admin)
async def enviar_teste(db: Session = Depends(get_db)):
    config = servico.obter_config(db)
    try:
        await to_thread.run_sync(
            servico.enviar_email, config, "Folha doméstica: e-mail de teste",
            "Se você recebeu esta mensagem, os avisos de pagamento por e-mail estão funcionando.\n\n-- Folha Doméstica",
        )
    except Exception as erro:  # noqa: BLE001 - devolve o motivo (senha, porta, TLS...) para a tela
        raise HTTPException(status_code=400, detail=f"Falha ao enviar: {erro}")
    return {"mensagem": f"E-mail de teste enviado para {config.destinatarios}"}


@router.post("/novo-link", response_model=ConfigNotificacoesOut, dependencies=somente_admin)
def gerar_link(db: Session = Depends(get_db)):
    """Gera (ou troca) o link de assinatura; o link anterior deixa de funcionar."""
    config = servico.obter_config(db)
    config.token_calendario = secrets.token_urlsafe(24)
    db.commit()
    return _saida(config)


@router.get("/proximos", response_model=list[ProximoPagamentoOut], dependencies=autenticado)
def proximos(dias: int = 45, db: Session = Depends(get_db)):
    hoje = date.today()
    return [
        ProximoPagamentoOut(
            trabalhador_id=p.trabalhador.id, trabalhador_nome=p.trabalhador.nome, tipo=p.tipo, data=p.data,
            competencia=p.competencia, dias_faltando=(p.data - hoje).days,
        )
        for p in pagamentos_entre(servico.trabalhadores_ativos(db), hoje, hoje + timedelta(days=min(dias, 400)))
    ]


def _calendario(db: Session, formato: str) -> Response:
    config = servico.obter_config(db)
    antecedencias = servico.lista_antecedencias(config.antecedencias)
    trabalhadores = servico.trabalhadores_ativos(db)
    if formato == "vcs":
        conteudo, tipo = servico.gerar_vcs(trabalhadores, antecedencias), "text/x-vcalendar"
    else:
        conteudo, tipo = servico.gerar_ics(trabalhadores, antecedencias), "text/calendar"
    return Response(
        content=conteudo.encode("utf-8"), media_type=f"{tipo}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="pagamentos-folha.{formato}"'},
    )


@router.get("/calendario.ics", dependencies=autenticado)
def baixar_ics(db: Session = Depends(get_db)):
    return _calendario(db, "ics")


@router.get("/calendario.vcs", dependencies=autenticado)
def baixar_vcs(db: Session = Depends(get_db)):
    return _calendario(db, "vcs")


@publico.get("/assinatura/{token}.ics", include_in_schema=False)
def assinatura(token: str, db: Session = Depends(get_db)):
    config = servico.obter_config(db)
    if not config.token_calendario or not secrets.compare_digest(token, config.token_calendario):
        raise HTTPException(status_code=404, detail="Link de calendário inválido")
    return _calendario(db, "ics")
