"""Datas de pagamento do salário e do adiantamento.

Dia útil, para pagamento de salário, é de segunda a sábado, exceto feriados (IN MTb nº 1/1989):
o "5º dia útil" conta os sábados. Só os feriados nacionais são considerados.
"""
import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from ..models import TipoPagamento, Trabalhador
from .calendario import feriados_nacionais


def e_dia_util(d: date, com_feriados: bool = True) -> bool:
    return d.isoweekday() != 7 and not (com_feriados and d in feriados_nacionais(d.year))


def data_pagamento(ano: int, mes: int, dia: int, dia_util: bool, com_feriados: bool = True) -> date:
    """`dia_util`: N-ésimo dia útil do mês. Senão, dia N do mês (ou o último dia, em meses mais curtos),
    antecipado para o dia útil anterior se cair em domingo ou feriado; se não houver dia útil antes dele
    no mesmo mês (ex.: dia 1 num domingo), adiado para o próximo dia útil."""
    ultimo = calendar.monthrange(ano, mes)[1]
    if dia_util:
        uteis = [d for d in (date(ano, mes, n) for n in range(1, ultimo + 1)) if e_dia_util(d, com_feriados)]
        return uteis[min(dia, len(uteis)) - 1]
    alvo = date(ano, mes, min(dia, ultimo))
    d = alvo
    while not e_dia_util(d, com_feriados):
        d -= timedelta(days=1)
    if d.month == mes:
        return d
    d = alvo
    while not e_dia_util(d, com_feriados):
        d += timedelta(days=1)
    return d


@dataclass(frozen=True)
class Pagamento:
    trabalhador: Trabalhador
    tipo: TipoPagamento
    data: date

    @property
    def competencia(self) -> str:
        """Mês a que o pagamento se refere: o salário é do mês anterior; o adiantamento, do próprio mês."""
        if self.tipo == TipoPagamento.adiantamento:
            return f"{self.data:%Y-%m}"
        anterior = self.data.replace(day=1) - timedelta(days=1)
        return f"{anterior:%Y-%m}"


def regras(t: Trabalhador) -> list[tuple[TipoPagamento, int, bool]]:
    """(tipo, dia, é dia útil) de cada pagamento configurado para o trabalhador."""
    lista = [(TipoPagamento.salario, t.dia_pagamento_salario, t.salario_dia_util)]
    if t.adiantamento_acordado and t.dia_pagamento_adiantamento:
        lista.append((TipoPagamento.adiantamento, t.dia_pagamento_adiantamento, t.adiantamento_dia_util))
    return lista


def meses_a_partir(inicio: date, quantidade: int):
    """(ano, mês) de `quantidade` meses consecutivos a partir do mês de `inicio`."""
    ano, mes = inicio.year, inicio.month
    for _ in range(quantidade):
        yield ano, mes
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def pagamentos_entre(trabalhadores: list[Trabalhador], inicio: date, fim: date) -> list[Pagamento]:
    """Pagamentos de inicio a fim (inclusive), em ordem de data."""
    meses = (fim.year - inicio.year) * 12 + fim.month - inicio.month + 1
    lista = []
    for t in trabalhadores:
        for tipo, dia, util in regras(t):
            for ano, mes in meses_a_partir(inicio, meses):
                d = data_pagamento(ano, mes, dia, util)
                if inicio <= d <= fim and d >= t.data_admissao:
                    lista.append(Pagamento(t, tipo, d))
    return sorted(lista, key=lambda p: (p.data, p.trabalhador.nome, p.tipo.value))
