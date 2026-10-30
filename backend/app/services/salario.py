"""Salário de cada competência, a partir do histórico de reajustes."""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ReajusteSalarial, TipoReajuste, Trabalhador


def _q(valor) -> Decimal:
    return Decimal(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def inicio_do_mes(mes_ano: str) -> date:
    ano, mes = map(int, mes_ano.split("-"))
    return date(ano, mes, 1)


def salario_em(trabalhador: Trabalhador, referencia: date) -> Decimal:
    """Salário vigente na data: o do último reajuste já em vigor; antes do primeiro reajuste,
    o salário anterior a ele; sem reajustes, o salário do cadastro."""
    reajustes = sorted(trabalhador.reajustes, key=lambda r: r.vigencia)
    if not reajustes:
        return Decimal(trabalhador.salario_base)
    vigentes = [r for r in reajustes if r.vigencia <= referencia]
    return Decimal(vigentes[-1].salario_novo if vigentes else reajustes[0].salario_anterior)


def salario_do_mes(trabalhador: Trabalhador, mes_ano: str) -> Decimal:
    return salario_em(trabalhador, inicio_do_mes(mes_ano))


def calcular_novo_salario(anterior: Decimal, tipo: TipoReajuste, valor: Decimal) -> Decimal:
    if tipo == TipoReajuste.percentual:
        return _q(anterior * (1 + valor / 100))
    if tipo == TipoReajuste.valor:
        return _q(anterior + valor)
    return _q(valor)


def sincronizar_salario_atual(trabalhador: Trabalhador, hoje: date | None = None) -> bool:
    """Mantém `salario_base` (o salário mostrado no cadastro) igual ao vigente hoje.
    Retorna True se mudou (reajuste que acabou de entrar em vigor)."""
    if not trabalhador.reajustes:
        return False
    atual = salario_em(trabalhador, hoje or date.today())
    if Decimal(trabalhador.salario_base) != atual:
        trabalhador.salario_base = atual
        return True
    return False


def aplicar_reajustes_vigentes(db: Session) -> int:
    """Rodado periodicamente: atualiza o salário do cadastro quando um reajuste futuro entra em vigor."""
    ids = db.scalars(select(ReajusteSalarial.trabalhador_id).distinct()).all()
    mudou = sum(sincronizar_salario_atual(db.get(Trabalhador, i)) for i in ids)
    if mudou:
        db.commit()
    return mudou
