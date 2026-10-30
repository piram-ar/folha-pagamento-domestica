"""Avisos de pagamento: calendário (.ics / .vcs) e e-mail diário."""
import calendar
import logging
import smtplib
import ssl
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    ConfigNotificacoes,
    FolhaPagamento,
    NotificacaoEnviada,
    SegurancaSmtp,
    TipoPagamento,
    Trabalhador,
)
from .pagamentos import Pagamento, data_pagamento, meses_a_partir, pagamentos_entre, regras

log = logging.getLogger("folha.notificacoes")

ID_CONFIG = 1
HORA_ALARME = 9  # alarmes do calendário tocam às 9h
MESES_AJUSTE_FERIADOS = 24
DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
ROTULO = {TipoPagamento.salario: "Pagamento do salário", TipoPagamento.adiantamento: "Pagamento do adiantamento"}


def obter_config(db: Session) -> ConfigNotificacoes:
    config = db.get(ConfigNotificacoes, ID_CONFIG)
    if config is None:
        config = ConfigNotificacoes(id=ID_CONFIG)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def lista_antecedencias(texto: str | None) -> list[int]:
    return sorted({int(x) for x in (texto or "").replace(";", ",").split(",") if x.strip().isdigit()}, reverse=True)


def trabalhadores_ativos(db: Session) -> list[Trabalhador]:
    return list(db.scalars(select(Trabalhador).where(Trabalhador.ativo).order_by(Trabalhador.nome)))


def _faltam(dias: int) -> str:
    return "é hoje" if dias == 0 else "é amanhã" if dias == 1 else f"faltam {dias} dias"


def _data_extenso(d: date) -> str:
    return f"{d:%d/%m/%Y} ({DIAS_SEMANA[d.weekday()]})"


def _regra_texto(dia: int, util: bool) -> str:
    return f"{dia}º dia útil do mês" if util else f"dia {dia} de cada mês (antecipado se cair em domingo ou feriado)"


# ---------- Calendário .ics (iCalendar, recorrente) ----------

def _escapar(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _dobrar(linha: str) -> str:
    """Quebra linhas acima de 75 bytes, como pede a RFC 5545."""
    partes, atual = [], ""
    for ch in linha:
        if len((atual + ch).encode("utf-8")) > 75:
            partes.append(atual)
            atual = " " + ch
        else:
            atual += ch
    partes.append(atual)
    return "\r\n".join(partes)


def _rrule(dia: int, util: bool) -> str:
    # Mesma regra de data_pagamento(), sem feriados (que entram via EXDATE/RDATE)
    seg_a_sab = "BYDAY=MO,TU,WE,TH,FR,SA"
    if util:
        return f"RRULE:FREQ=MONTHLY;{seg_a_sab};BYSETPOS={dia}"
    if dia == 1:  # dia 1 num domingo: adia para o dia 2 (sem feriados, é o único caso de adiamento)
        return f"RRULE:FREQ=MONTHLY;BYMONTHDAY=1,2;{seg_a_sab};BYSETPOS=1"
    dias = ",".join(str(n) for n in range(1, dia + 1))
    return f"RRULE:FREQ=MONTHLY;BYMONTHDAY={dias};{seg_a_sab};BYSETPOS=-1"


def _alarme_ics(antecedencia: int, resumo: str) -> list[str]:
    # Evento de dia inteiro começa à 0h: o alarme às 9h de "antecedencia" dias antes
    horas = 24 * antecedencia - HORA_ALARME
    gatilho = f"-PT{horas}H" if horas > 0 else f"PT{-horas}H"
    return ["BEGIN:VALARM", "ACTION:DISPLAY", f"TRIGGER:{gatilho}",
            f"DESCRIPTION:{_escapar(f'{resumo} ({_faltam(antecedencia)})')}", "END:VALARM"]


def gerar_ics(trabalhadores: list[Trabalhador], antecedencias: list[int], hoje: date | None = None) -> str:
    hoje = hoje or date.today()
    agora = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Folha Domestica//Avisos de pagamento//PT-BR",
              "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:Folha doméstica - pagamentos",
              "X-WR-TIMEZONE:America/Sao_Paulo"]
    inicio_mes = hoje.replace(day=1)
    for t in trabalhadores:
        for tipo, dia, util in regras(t):
            resumo = f"{ROTULO[tipo]} - {t.nome}"
            meses = list(meses_a_partir(inicio_mes, MESES_AJUSTE_FERIADOS))
            sem_feriado = [data_pagamento(a, m, dia, util, com_feriados=False) for a, m in meses]
            com_feriado = [data_pagamento(a, m, dia, util) for a, m in meses]
            # DTSTART precisa ser uma ocorrência da regra
            inicio = next((d for d in sem_feriado if d >= max(t.data_admissao, inicio_mes)), sem_feriado[-1])
            linhas += [
                "BEGIN:VEVENT",
                f"UID:folha-{t.id}-{tipo.value}@folha-domestica",
                f"DTSTAMP:{agora}",
                f"DTSTART;VALUE=DATE:{inicio:%Y%m%d}",
                f"DTEND;VALUE=DATE:{inicio + timedelta(days=1):%Y%m%d}",
                _rrule(dia, util),
                f"SUMMARY:{_escapar(resumo)}",
                f"DESCRIPTION:{_escapar(f'{ROTULO[tipo]} de {t.nome}: {_regra_texto(dia, util)}.')}",
                "TRANSP:TRANSPARENT",
            ]
            # Feriado nacional desloca a data: tira a ocorrência da regra e põe a data ajustada
            for regra_d, real_d in zip(sem_feriado, com_feriado):
                if regra_d != real_d and regra_d >= inicio:
                    linhas += [f"EXDATE;VALUE=DATE:{regra_d:%Y%m%d}", f"RDATE;VALUE=DATE:{real_d:%Y%m%d}"]
            for a in antecedencias:
                linhas += _alarme_ics(a, resumo)
            linhas.append("END:VEVENT")
    linhas.append("END:VCALENDAR")
    return "\r\n".join(_dobrar(l) for l in linhas) + "\r\n"


# ---------- Calendário .vcs (vCalendar 1.0, ocorrências explícitas) ----------

def gerar_vcs(trabalhadores: list[Trabalhador], antecedencias: list[int], hoje: date | None = None,
              meses: int = 12) -> str:
    """vCalendar 1.0 não tem regra para "N-ésimo dia útil": lista cada data dos próximos meses."""
    hoje = hoje or date.today()
    ano, mes = list(meses_a_partir(hoje, meses))[-1]
    fim = date(ano, mes, calendar.monthrange(ano, mes)[1])
    linhas = ["BEGIN:VCALENDAR", "VERSION:1.0", "PRODID:-//Folha Domestica//Avisos de pagamento//PT-BR"]
    for p in pagamentos_entre(trabalhadores, hoje, fim):
        resumo = f"{ROTULO[p.tipo]} - {p.trabalhador.nome}"
        linhas += [
            "BEGIN:VEVENT",
            f"UID:folha-{p.trabalhador.id}-{p.tipo.value}-{p.data:%Y%m%d}@folha-domestica",
            f"DTSTART:{p.data:%Y%m%d}T{HORA_ALARME:02d}0000",
            f"DTEND:{p.data:%Y%m%d}T{HORA_ALARME:02d}3000",
            f"SUMMARY;CHARSET=UTF-8:{resumo}",
        ]
        for a in antecedencias:
            quando = datetime.combine(p.data - timedelta(days=a), datetime.min.time()).replace(hour=HORA_ALARME)
            linhas.append(f"DALARM:{quando:%Y%m%dT%H%M%S};;;{resumo} ({_faltam(a)})")
        linhas.append("END:VEVENT")
    linhas.append("END:VCALENDAR")
    return "\r\n".join(linhas) + "\r\n"


# ---------- E-mail ----------

def enviar_email(config: ConfigNotificacoes, assunto: str, corpo: str) -> None:
    destinatarios = [e.strip() for e in (config.destinatarios or "").replace(";", ",").split(",") if e.strip()]
    if not config.smtp_host or not destinatarios:
        raise ValueError("Configure o servidor SMTP e ao menos um destinatário")
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = config.smtp_remetente or config.smtp_usuario
    msg["To"] = ", ".join(destinatarios)
    msg.set_content(corpo)

    contexto = ssl.create_default_context()
    if config.smtp_seguranca == SegurancaSmtp.ssl:
        servidor = smtplib.SMTP_SSL(config.smtp_host, config.smtp_porta, timeout=20, context=contexto)
    else:
        servidor = smtplib.SMTP(config.smtp_host, config.smtp_porta, timeout=20)
    with servidor:
        if config.smtp_seguranca == SegurancaSmtp.starttls:
            servidor.starttls(context=contexto)
        if config.smtp_usuario:
            servidor.login(config.smtp_usuario, config.smtp_senha or "")
        servidor.send_message(msg)


def _linha_aviso(db: Session, p: Pagamento, hoje: date) -> str:
    texto = f"- {ROTULO[p.tipo]} de {p.trabalhador.nome}: {_data_extenso(p.data)}, {_faltam((p.data - hoje).days)}."
    if p.tipo == TipoPagamento.salario:
        folha = db.scalar(select(FolhaPagamento).where(
            FolhaPagamento.trabalhador_id == p.trabalhador.id, FolhaPagamento.mes_ano == p.competencia))
        if folha:
            valor = f"{folha.salario_liquido:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            situacao = "fechada" if folha.status.value == "fechada" else "ainda em rascunho"
            texto += f"\n  Líquido da folha de {p.competencia[5:]}/{p.competencia[:4]}: R$ {valor} ({situacao})."
        else:
            texto += f"\n  A folha de {p.competencia[5:]}/{p.competencia[:4]} ainda não foi calculada."
    return texto


def avisos_pendentes(db: Session, config: ConfigNotificacoes, hoje: date) -> list[tuple[Pagamento, list[int]]]:
    """Pagamentos com aviso a enviar hoje e as antecedências que o aviso cobre.

    Um aviso de N dias vence quando faltam N dias ou menos. Se o Pi ficou desligado no dia certo,
    o aviso sai no dia seguinte (com os dias que realmente faltam), sem repetir avisos já enviados.
    """
    antecedencias = lista_antecedencias(config.antecedencias)
    if not antecedencias:
        return []
    pendentes = []
    for p in pagamentos_entre(trabalhadores_ativos(db), hoje, hoje + timedelta(days=max(antecedencias))):
        faltam = (p.data - hoje).days
        vencidas = [a for a in antecedencias if faltam <= a]
        if not vencidas:
            continue
        enviadas = set(db.scalars(select(NotificacaoEnviada.antecedencia).where(
            NotificacaoEnviada.trabalhador_id == p.trabalhador.id,
            NotificacaoEnviada.tipo == p.tipo,
            NotificacaoEnviada.data_pagamento == p.data,
        )))
        if min(vencidas) not in enviadas:
            pendentes.append((p, [a for a in vencidas if a not in enviadas]))
    return pendentes


def enviar_avisos_do_dia(db: Session, agora: datetime | None = None, forcar: bool = False) -> int:
    """Envia, num único e-mail, os avisos pendentes. Retorna quantos pagamentos foram avisados."""
    agora = agora or datetime.now()
    config = obter_config(db)
    if not config.email_ativo or (not forcar and agora.hour < config.hora_envio):
        return 0
    hoje = agora.date()
    pendentes = avisos_pendentes(db, config, hoje)
    if not pendentes:
        return 0
    linhas = [_linha_aviso(db, p, hoje) for p, _ in pendentes]
    proximo = min(p.data for p, _ in pendentes)
    dias = (proximo - hoje).days
    quando = "hoje" if dias == 0 else "amanhã" if dias == 1 else f"em {dias} dias"
    assunto = f"Folha doméstica: pagamento {quando} ({proximo:%d/%m})"
    corpo = "Lembretes de pagamento:\n\n" + "\n".join(linhas) + "\n\n-- Folha Doméstica"
    try:
        enviar_email(config, assunto, corpo)
    except Exception as erro:  # noqa: BLE001 - registra qualquer falha de SMTP/rede para a tela
        config.ultimo_erro = f"{agora:%d/%m/%Y %H:%M}: {erro}"
        db.commit()
        raise
    for p, antecedencias in pendentes:
        for a in antecedencias:
            db.add(NotificacaoEnviada(trabalhador_id=p.trabalhador.id, tipo=p.tipo, data_pagamento=p.data, antecedencia=a))
    config.ultimo_envio_em = agora
    config.ultimo_erro = None
    db.commit()
    log.info("Aviso de pagamento enviado (%d pagamento(s))", len(pendentes))
    return len(pendentes)
