"""Dias úteis do mês (base do vale-transporte)."""
import calendar
from datetime import date, timedelta
from functools import lru_cache

# Feriados nacionais de data fixa (dia, mês). Consciência Negra (20/11) entra à parte, nacional desde 2024.
_FERIADOS_FIXOS = [(1, 1), (21, 4), (1, 5), (7, 9), (12, 10), (2, 11), (15, 11), (25, 12)]

DIAS_SEMANA_PADRAO = "12345"  # 1 = segunda ... 7 = domingo (ISO)


def _pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = divmod(b, 4)
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


@lru_cache(maxsize=16)
def feriados_nacionais(ano: int) -> frozenset[date]:
    feriados = {date(ano, mes, dia) for dia, mes in _FERIADOS_FIXOS}
    if ano >= 2024:
        feriados.add(date(ano, 11, 20))
    feriados.add(_pascoa(ano) - timedelta(days=2))  # Sexta-feira Santa
    return frozenset(feriados)


def dias_uteis(mes_ano: str, dias_semana: str = DIAS_SEMANA_PADRAO) -> int:
    """Dias do mês em que o trabalhador trabalha, sem os feriados nacionais.

    Feriados estaduais/municipais e faltas não entram: ajuste o número na tela da folha.
    """
    ano, mes = map(int, mes_ano.split("-"))
    feriados = feriados_nacionais(ano)
    total = 0
    for dia in range(1, calendar.monthrange(ano, mes)[1] + 1):
        d = date(ano, mes, dia)
        if str(d.isoweekday()) in dias_semana and d not in feriados:
            total += 1
    return total
