"""Cálculo automático dos períodos aquisitivos de férias."""
import calendar
from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..models import HistoricoFerias, Trabalhador
from . import tabelas


def somar_meses(d: date, meses: int) -> date:
    total = d.month - 1 + meses
    ano, mes = d.year + total // 12, total % 12 + 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def meses_trabalhados(inicio: date, ate: date) -> int:
    """Meses completos entre as datas; fração igual ou superior a 15 dias conta como mês."""
    meses = 0
    while somar_meses(inicio, meses + 1) <= ate + timedelta(days=1):
        meses += 1
    if (ate - somar_meses(inicio, meses)).days + 1 >= 15:
        meses += 1
    return min(meses, 12)


def fim_periodo(inicio: date) -> date:
    return somar_meses(inicio, 12) - timedelta(days=1)


def limite_concessivo(periodo: HistoricoFerias) -> date:
    """Férias devem ser concedidas nos 12 meses seguintes ao fim do período aquisitivo."""
    return somar_meses(periodo.periodo_aquisitivo_fim + timedelta(days=1), 12) - timedelta(days=1)


def sincronizar_periodos(db: Session, trabalhador: Trabalhador, hoje: date | None = None) -> list[HistoricoFerias]:
    """Garante um registro por período aquisitivo desde a admissão até hoje."""
    hoje = hoje or date.today()
    existentes = {p.periodo_aquisitivo_inicio: p for p in trabalhador.historico_ferias}
    validos = set()

    inicio = trabalhador.data_admissao
    while inicio <= hoje:
        fim = fim_periodo(inicio)
        if fim <= hoje:
            adquiridos = tabelas.DIAS_FERIAS_POR_PERIODO
        else:  # período em andamento: 2,5 dias por mês (informativo)
            adquiridos = int(meses_trabalhados(inicio, hoje) * tabelas.DIAS_FERIAS_POR_PERIODO / 12)

        periodo = existentes.get(inicio)
        if periodo is None:
            periodo = HistoricoFerias(
                trabalhador_id=trabalhador.id,
                periodo_aquisitivo_inicio=inicio,
                dias_gozados=0,
            )
            db.add(periodo)
            trabalhador.historico_ferias.append(periodo)
        periodo.periodo_aquisitivo_fim = fim
        periodo.dias_adquiridos = adquiridos
        periodo.saldo_dias = adquiridos - (periodo.dias_gozados or 0)
        validos.add(inicio)
        inicio = fim + timedelta(days=1)

    # Remove períodos órfãos (ex.: data de admissão alterada) que não tenham gozos registrados
    for inicio_existente, periodo in existentes.items():
        if inicio_existente not in validos and not periodo.gozos:
            trabalhador.historico_ferias.remove(periodo)
            db.delete(periodo)

    # Evita escrita no cartão SD em toda consulta: só faz commit se algo mudou
    if db.new or db.deleted or any(db.is_modified(o) for o in db.dirty):
        db.commit()
    return sorted(trabalhador.historico_ferias, key=lambda p: p.periodo_aquisitivo_inicio)


def situacao_periodo(periodo: HistoricoFerias, hoje: date) -> str:
    if periodo.periodo_aquisitivo_fim > hoje:
        return "em_aquisicao"
    if periodo.saldo_dias <= 0:
        return "quitado"
    limite = limite_concessivo(periodo)
    if hoje > limite:
        return "vencido"
    if (limite - hoje).days <= 60:
        return "vence_em_breve"
    return "disponivel"
