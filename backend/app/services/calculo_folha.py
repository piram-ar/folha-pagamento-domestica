"""Motor de cálculo da folha de pagamento do trabalhador doméstico."""
import json
from collections import defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    EventoFolha,
    FolhaPagamento,
    NaturezaBeneficio,
    StatusFolha,
    TipoBeneficio,
    TipoContrato,
    TipoEvento,
    Trabalhador,
)
from . import tabelas
from .calendario import dias_uteis as calcular_dias_uteis
from .inss import faixas_do_mes, inss_progressivo

CENTAVO = Decimal("0.01")
ZERO = Decimal("0")

ROTULO_BENEFICIO = {
    TipoBeneficio.vale_transporte: "Vale-transporte",
    TipoBeneficio.vale_mercado: "Vale-mercado",
    TipoBeneficio.vale_refeicao: "Vale-refeição",
    TipoBeneficio.plano_saude: "Plano de saúde",
    TipoBeneficio.outro: "Benefício",
}


def q(valor) -> Decimal:
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _fmt(valor: Decimal) -> str:
    """Número sem zeros à direita, com vírgula decimal (ex.: 1.50 -> '1,5')."""
    texto = f"{Decimal(valor):f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def valor_hora(salario_base: Decimal) -> Decimal:
    return Decimal(salario_base) / tabelas.DIVISOR_HORAS_MENSAL


def valor_hora_extra(salario_base: Decimal, horas: Decimal, percentual: Decimal) -> Decimal:
    fator = 1 + Decimal(percentual) / 100
    return q(valor_hora(salario_base) * fator * Decimal(horas))


def valor_horas_falta(salario_base: Decimal, horas: Decimal) -> Decimal:
    return q(valor_hora(salario_base) * Decimal(horas))


def vt_por_dia(beneficio) -> bool:
    """Vale-transporte pago (no salário ou à parte) é cadastrado por dia e multiplicado pelos dias úteis.

    A cota descontada do empregado (natureza "desconto") continua sendo um valor mensal fixo.
    """
    return beneficio.tipo == TipoBeneficio.vale_transporte and beneficio.natureza != NaturezaBeneficio.desconto


def calcular(db: Session, trabalhador: Trabalhador, mes_ano: str, dias_trabalhados: int,
             dias_uteis: int | None = None) -> dict:
    """Calcula todos os valores da folha do mês sem gravar nada."""
    if dias_uteis is None:
        dias_uteis = calcular_dias_uteis(mes_ano, trabalhador.dias_semana_trabalho)
    salario_base = Decimal(trabalhador.salario_base)
    dias = min(Decimal(dias_trabalhados), tabelas.DIAS_MES_COMERCIAL)
    salario_proporcional = q(salario_base / tabelas.DIAS_MES_COMERCIAL * dias)

    eventos = db.scalars(
        select(EventoFolha)
        .where(EventoFolha.trabalhador_id == trabalhador.id, EventoFolha.mes_ano == mes_ano)
        .order_by(EventoFolha.data_lancamento)
    ).all()

    itens: list[dict] = []

    def item(codigo, descricao, referencia, tipo, valor):
        if valor:
            itens.append({
                "codigo": codigo, "descricao": descricao, "referencia": referencia,
                "tipo": tipo, "valor": str(q(valor)),
            })

    clt = trabalhador.tipo_contrato == TipoContrato.com_registro
    item("001", "Salário" if clt else "Serviços prestados", f"{dias_trabalhados} dias", "provento", salario_proporcional)

    # Horas extras agrupadas por percentual
    he_por_pct: dict[Decimal, list[Decimal]] = defaultdict(lambda: [ZERO, ZERO])
    total_bonus = total_faltas = total_vales = ZERO
    horas_falta = ZERO
    qtd_vales = 0
    for ev in eventos:
        if ev.tipo == TipoEvento.hora_extra:
            pct = Decimal(ev.percentual_adicional or 50)
            he_por_pct[pct][0] += Decimal(ev.quantidade_horas or 0)
            he_por_pct[pct][1] += Decimal(ev.valor)
        elif ev.tipo == TipoEvento.bonus:
            total_bonus += Decimal(ev.valor)
        elif ev.tipo == TipoEvento.falta:
            total_faltas += Decimal(ev.valor)
            horas_falta += Decimal(ev.quantidade_horas or 0)
        elif ev.tipo == TipoEvento.vale_antecipacao:
            total_vales += Decimal(ev.valor)
            qtd_vales += 1

    total_he = ZERO
    for pct in sorted(he_por_pct):
        horas, valor = he_por_pct[pct]
        total_he += valor
        item("002", f"Horas extras {_fmt(pct)}%", f"{_fmt(horas)} h" if horas else "", "provento", valor)
    item("003", "Bônus / gratificação", "", "provento", total_bonus)

    total_benef_prov = total_benef_desc = ZERO
    informativos = []
    for b in trabalhador.beneficios:
        rotulo = b.descricao or ROTULO_BENEFICIO[b.tipo]
        valor, referencia = Decimal(b.valor), ""
        if vt_por_dia(b):
            valor = q(valor * dias_uteis)
            referencia = f"{dias_uteis} d × {q(b.valor)}".replace(".", ",")
        if b.natureza == NaturezaBeneficio.provento:
            total_benef_prov += valor
            item("004", rotulo, referencia, "provento", valor)
        elif b.natureza == NaturezaBeneficio.desconto:
            total_benef_desc += valor
            item("104", b.descricao or f"Desconto {rotulo.lower()}", "", "desconto", valor)
        elif valor:
            descricao = f"{rotulo} ({dias_uteis} dias úteis)" if vt_por_dia(b) else rotulo
            informativos.append({"descricao": descricao, "valor": str(q(valor))})

    item("101", "Faltas / atrasos", f"{_fmt(horas_falta)} h" if horas_falta else "", "desconto", total_faltas)
    item("102", "Adiantamento salarial (vales)", f"{qtd_vales} lanç.", "desconto", total_vales)

    # Base de cálculo dos encargos: remuneração (sem benefícios indenizatórios)
    salario_bruto = max(q(salario_proporcional + total_he + total_bonus - total_faltas), ZERO)

    inss_empregado = ZERO
    tabela_inss = None
    if trabalhador.tipo_contrato == TipoContrato.com_registro:
        faixas, tabela_inss = faixas_do_mes(db, mes_ano)
        inss_empregado = inss_progressivo(salario_bruto, faixas)
        item("103", "INSS", f"tabela {tabela_inss}", "desconto", inss_empregado)
        partes = {
            "INSS do empregado (descontado no recibo)": inss_empregado,
            f"INSS patronal ({_fmt(tabelas.ALIQ_INSS_PATRONAL * 100)}%)": q(salario_bruto * tabelas.ALIQ_INSS_PATRONAL),
            f"GILRAT ({_fmt(tabelas.ALIQ_GILRAT * 100)}%)": q(salario_bruto * tabelas.ALIQ_GILRAT),
            f"FGTS ({_fmt(tabelas.ALIQ_FGTS * 100)}%)": q(salario_bruto * tabelas.ALIQ_FGTS),
            f"FGTS indenização compensatória ({_fmt(tabelas.ALIQ_FGTS_INDENIZATORIO * 100)}%)":
                q(salario_bruto * tabelas.ALIQ_FGTS_INDENIZATORIO),
        }
        titulo_encargos = "Guia DAE eSocial (estimativa a recolher)"
    else:
        provisao_ferias = q(salario_bruto / 12)
        partes = {
            "Provisão de férias (1/12)": provisao_ferias,
            "Provisão de 1/3 de férias": q(provisao_ferias / 3),
            "Provisão de 13º salário (1/12)": q(salario_bruto / 12),
        }
        titulo_encargos = "Fundo de reserva (valor a guardar)"

    encargos = {k: str(v) for k, v in partes.items()}
    total_encargos = q(sum(partes.values(), ZERO))

    total_proventos = q(salario_proporcional + total_he + total_bonus + total_benef_prov)
    total_descontos = q(total_faltas + total_vales + total_benef_desc + inss_empregado)
    salario_liquido = q(total_proventos - total_descontos)

    return {
        "dias_uteis": dias_uteis,
        "salario_base": q(salario_base),
        "salario_proporcional": salario_proporcional,
        "total_horas_extras": q(total_he),
        "total_bonus": q(total_bonus),
        "total_faltas": q(total_faltas),
        "total_descontos_vales": q(total_vales),
        "total_beneficios": q(total_benef_prov),
        "total_descontos_beneficios": q(total_benef_desc),
        "inss_empregado": inss_empregado,
        "salario_bruto": salario_bruto,
        "total_proventos": total_proventos,
        "total_descontos": total_descontos,
        "encargos_recolher_guardar": total_encargos,
        "salario_liquido": salario_liquido,
        "detalhamento": {
            "itens": itens,
            "beneficios_informativos": informativos,
            "encargos": {"titulo": titulo_encargos, "itens": encargos, "total": str(total_encargos)},
            "valor_hora": str(q(valor_hora(salario_base))),
            "tabela_inss": tabela_inss,
        },
    }


def gerar_ou_atualizar(db: Session, trabalhador: Trabalhador, mes_ano: str, dias_trabalhados: int,
                       dias_uteis: int | None = None) -> FolhaPagamento:
    folha = db.scalar(
        select(FolhaPagamento).where(
            FolhaPagamento.trabalhador_id == trabalhador.id, FolhaPagamento.mes_ano == mes_ano
        )
    )
    if folha and folha.status == StatusFolha.fechada:
        raise ValueError("A folha deste mês já está fechada. Reabra-a para recalcular.")

    resultado = calcular(db, trabalhador, mes_ano, dias_trabalhados, dias_uteis)
    detalhamento = resultado.pop("detalhamento")
    if folha is None:
        folha = FolhaPagamento(trabalhador_id=trabalhador.id, mes_ano=mes_ano, status=StatusFolha.rascunho)
        db.add(folha)
    folha.dias_trabalhados = dias_trabalhados
    for campo, valor in resultado.items():
        setattr(folha, campo, valor)
    folha.detalhamento = json.dumps(detalhamento, ensure_ascii=False)
    folha.calculado_em = datetime.now()
    db.commit()
    db.refresh(folha)
    return folha
