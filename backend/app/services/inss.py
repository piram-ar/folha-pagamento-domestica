"""Tabela progressiva do INSS do empregado, cadastrada por vigência."""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import TabelaInss
from . import tabelas

Faixas = list[tuple[Decimal, Decimal]]  # (teto, alíquota em fração)


def tabela_vigente(db: Session, referencia: date) -> TabelaInss | None:
    """Tabela de vigência mais recente que já valia na data de referência."""
    return db.scalar(
        select(TabelaInss)
        .options(selectinload(TabelaInss.faixas))
        .where(TabelaInss.vigencia_inicio <= referencia)
        .order_by(TabelaInss.vigencia_inicio.desc())
        .limit(1)
    )


def faixas_do_mes(db: Session, mes_ano: str) -> tuple[Faixas, str]:
    """Faixas usadas na folha do mês e um rótulo para o recibo (ex.: 'vigência 01/2025')."""
    ano, mes = map(int, mes_ano.split("-"))
    tabela = tabela_vigente(db, date(ano, mes, 1))
    if tabela is None or not tabela.faixas:
        return tabelas.FAIXAS_INSS_PADRAO, "padrão 2025"
    faixas = [(Decimal(f.teto), Decimal(f.aliquota) / 100) for f in tabela.faixas]
    return faixas, f"vigência {tabela.vigencia_inicio:%m/%Y}"


def inss_progressivo(base: Decimal, faixas: Faixas) -> Decimal:
    total, piso = Decimal("0"), Decimal("0")
    for teto, aliquota in faixas:
        if base <= piso:
            break
        total += (min(base, teto) - piso) * aliquota
        piso = teto
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
