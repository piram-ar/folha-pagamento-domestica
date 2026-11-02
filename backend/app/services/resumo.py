"""Resumo anual dos pagamentos por trabalhador e saldo das provisões (reservas para férias, 13º e encargos).

Provisões: a cada mês trabalhado o contratante deveria guardar 1/12 da remuneração para o 13º e
1/12 + 1/3 para as férias (com registro, mais os encargos do empregador sobre esses valores). O saldo é
o provisionado desde a admissão menos o que já foi pago. Meses sem folha calculada entram pelo salário
vigente (estimativa).
"""
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal

from ..models import TipoContrato, Trabalhador
from . import tabelas
from .calculo_folha import ZERO, q, remuneracao_do_mes, valor_dias
from .calendario import dias_no_mes, meses_entre
from .salario import salario_do_mes

CATEGORIAS = {
    "salarios": "Salários e adicionais",
    "vale_transporte": "Vale-transporte",
    "vale_alimentacao": "Vale-alimentação",
    "outros_beneficios": "Outros benefícios",
    "ferias": "Férias + 1/3",
    "decimo_terceiro": "13º salário",
    "encargos": "Encargos (DAE)",
}


def _categoria_beneficio(entrada: dict) -> str:
    tipo = entrada.get("beneficio")
    if tipo is None:  # folhas calculadas antes de o tipo ser gravado no item
        descricao = entrada.get("descricao", "").lower()
        tipo = ("vale_transporte" if "transporte" in descricao
                else "vale_mercado" if any(p in descricao for p in ("mercado", "refei", "alimenta")) else "outro")
    if tipo == "vale_transporte":
        return "vale_transporte"
    return "vale_alimentacao" if tipo in ("vale_mercado", "vale_refeicao") else "outros_beneficios"


def _gozos_calculados(t: Trabalhador):
    return [g for p in t.historico_ferias for g in p.gozos if g.valor_ferias is not None]


def pagamentos_do_ano(t: Trabalhador, ano: int) -> dict:
    """Quanto cada ocorrência custou no ano (folhas da competência, férias e 13º pela data de pagamento)."""
    valores = dict.fromkeys(CATEGORIAS, ZERO)
    em_aberto, pendentes = ZERO, 0
    clt = t.tipo_contrato == TipoContrato.com_registro

    for f in t.folhas:
        if not f.mes_ano.startswith(f"{ano}-"):
            continue
        detalhe = json.loads(f.detalhamento or "{}")
        valores["salarios"] += Decimal(f.salario_bruto)
        for it in detalhe.get("itens", []):
            if it["codigo"] == "004":
                valores[_categoria_beneficio(it)] += Decimal(it["valor"])
        for inf in detalhe.get("beneficios_informativos", []):
            valores[_categoria_beneficio(inf)] += Decimal(inf["valor"])
        if "encargos_empregador" in detalhe:
            valores["encargos"] += Decimal(detalhe["encargos_empregador"])
        elif clt:
            valores["encargos"] += Decimal(f.encargos_recolher_guardar) - Decimal(f.inss_empregado)
        if not f.pago_em:
            em_aberto += Decimal(f.salario_liquido)
            pendentes += 1

    for g in _gozos_calculados(t):
        if g.data_pagamento.year == ano:
            valores["ferias"] += g.bruto  # os encargos das férias entram na DAE do mês do gozo (folha)
            if not g.pago_em:
                em_aberto += Decimal(g.liquido)
                pendentes += 1

    for d in t.decimos_terceiros:
        if d.ano == ano:
            valores["decimo_terceiro"] += Decimal(d.valor_bruto)
            valores["encargos"] += Decimal(d.encargos)
            if not d.pago_em:
                em_aberto += Decimal(d.liquido)
                pendentes += 1

    valores = {k: q(v) for k, v in valores.items()}
    return {"valores": valores, "total": q(sum(valores.values(), ZERO)), "em_aberto": q(em_aberto),
            "pendentes": pendentes}


def provisoes(t: Trabalhador, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    atual = hoje.strftime("%Y-%m")
    folhas = {f.mes_ano: f for f in t.folhas}
    admissao = t.data_admissao.strftime("%Y-%m")

    prov_ferias = ZERO
    prov_13: dict[int, Decimal] = defaultdict(lambda: ZERO)
    estimados = 0
    for mes in meses_entre(t.data_admissao, hoje):
        if mes in folhas:
            base = remuneracao_do_mes(folhas[mes])
        elif mes < atual:  # mês passado sem folha: estima pelo salário vigente
            base = salario_do_mes(t, mes)
            if mes == admissao:
                base = valor_dias(base, mes, dias_no_mes(mes) - t.data_admissao.day + 1)
            estimados += 1
        else:  # mês corrente ainda sem folha
            continue
        prov_ferias += base / 12 * Decimal(4) / 3
        prov_13[int(mes[:4])] += base / 12

    gozos = _gozos_calculados(t)
    ferias_pagas = sum((g.bruto for g in gozos if g.pago_em), ZERO)
    encargos_pagos = sum((Decimal(g.encargos) for g in gozos if g.pago_em), ZERO)

    decimo = []
    base_encargos_13 = ZERO
    for ano in sorted(set(prov_13) | {hoje.year}):
        parcelas = [d for d in t.decimos_terceiros if d.ano == ano]
        quitado = any(d.parcela == 2 and d.pago_em for d in parcelas)
        if quitado and ano < hoje.year:
            continue  # ano encerrado: diferenças de arredondamento ou reajuste não são reserva
        pago = sum((Decimal(d.valor_bruto) for d in parcelas if d.pago_em), ZERO)
        encargos_pagos += sum((Decimal(d.encargos) for d in parcelas if d.pago_em), ZERO)
        base_encargos_13 += prov_13[ano]
        decimo.append({"ano": ano, "provisionado": q(prov_13[ano]), "pago": q(pago),
                       "saldo": q(prov_13[ano] - pago), "quitado": quitado})

    resultado = {
        "ferias": {"provisionado": q(prov_ferias), "pago": q(ferias_pagas), "saldo": q(prov_ferias - ferias_pagas)},
        "decimo_terceiro": decimo,
        "encargos": None,
        "meses_estimados": estimados,
    }
    saldo = resultado["ferias"]["saldo"] + sum((d["saldo"] for d in decimo), ZERO)
    if t.tipo_contrato == TipoContrato.com_registro:
        prov_encargos = (prov_ferias + base_encargos_13) * tabelas.ALIQ_ENCARGOS_EMPREGADOR
        resultado["encargos"] = {"provisionado": q(prov_encargos), "pago": q(encargos_pagos),
                                 "saldo": q(prov_encargos - encargos_pagos)}
        saldo += resultado["encargos"]["saldo"]
    resultado["saldo_total"] = q(saldo)
    return resultado
