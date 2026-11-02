"""Pagamento das férias: salário dos dias gozados + 1/3 constitucional, pago até 2 dias antes do início
(art. 145 da CLT, aplicado ao doméstico pela LC 150/2015). Vale para trabalhadores com e sem registro;
com registro, desconta o INSS e estima os encargos do empregador.

A folha dos meses de férias desconta esses dias do salário (já pagos aqui), e o INSS do mês considera
salário + férias (ver `calculo_folha.calcular`).
"""
import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from ..models import GozoFerias, TipoContrato
from . import tabelas
from .calculo_folha import ZERO, media_horas_extras, q
from .calendario import meses_entre
from .inss import faixas_do_mes, inss_progressivo
from .salario import salario_em

ANTECEDENCIA_PAGAMENTO = 2  # dias antes do início do gozo


def data_pagamento_padrao(inicio: date) -> date:
    return inicio - timedelta(days=ANTECEDENCIA_PAGAMENTO)


def calcular_pagamento(db: Session, gozo: GozoFerias, data_pagamento: date | None = None) -> GozoFerias:
    """Calcula (ou recalcula) o pagamento das férias e grava no próprio gozo. Não faz commit."""
    if gozo.pago_em:
        raise ValueError("Férias já pagas: desfaça o pagamento antes de recalcular.")
    periodo = gozo.periodo
    t = periodo.trabalhador
    salario = salario_em(t, gozo.data_inicio)

    # Média das horas extras do período aquisitivo (12 meses); férias antecipadas: os meses já trabalhados
    fim_media = min(periodo.periodo_aquisitivo_fim, gozo.data_inicio.replace(day=1) - timedelta(days=1))
    media = media_horas_extras(t, meses_entre(periodo.periodo_aquisitivo_inicio, fim_media)[:12])

    valor_salario = q(salario / tabelas.DIAS_MES_COMERCIAL * gozo.dias)
    valor_media = q(media / tabelas.DIAS_MES_COMERCIAL * gozo.dias)
    valor_ferias = valor_salario + valor_media
    terco = q(valor_ferias / 3)
    bruto = valor_ferias + terco
    # Abono pecuniário (LC 150/2015, art. 17 §3): os dias vendidos pela mesma remuneração, com 1/3;
    # tem natureza indenizatória, sem INSS nem FGTS
    abono = q((salario + media) / tabelas.DIAS_MES_COMERCIAL * gozo.dias_abono)
    terco_abono = q(abono / 3)

    itens = [
        {"descricao": "Férias", "referencia": f"{gozo.dias} dias", "tipo": "provento", "valor": str(valor_salario)},
    ]
    if valor_media:
        itens.append({"descricao": "Média de horas extras sobre férias", "referencia": f"{gozo.dias} dias",
                      "tipo": "provento", "valor": str(valor_media)})
    itens.append({"descricao": "1/3 constitucional de férias", "referencia": "1/3", "tipo": "provento",
                  "valor": str(terco)})
    if abono:
        itens.append({"descricao": "Abono pecuniário de férias", "referencia": f"{gozo.dias_abono} dias",
                      "tipo": "provento", "valor": str(abono)})
        itens.append({"descricao": "1/3 sobre abono pecuniário", "referencia": "1/3", "tipo": "provento",
                      "valor": str(terco_abono)})

    inss = encargos = ZERO
    tabela_inss = None
    if t.tipo_contrato == TipoContrato.com_registro:
        faixas, tabela_inss = faixas_do_mes(db, gozo.data_inicio.strftime("%Y-%m"))
        inss = inss_progressivo(bruto, faixas)
        encargos = q(bruto * tabelas.ALIQ_ENCARGOS_EMPREGADOR)
        if inss:
            itens.append({"descricao": "INSS sobre férias", "referencia": f"tabela {tabela_inss}",
                          "tipo": "desconto", "valor": str(inss)})

    gozo.data_pagamento = data_pagamento or gozo.data_pagamento or data_pagamento_padrao(gozo.data_inicio)
    gozo.salario_base = q(salario)
    gozo.media_variaveis = media
    gozo.valor_ferias = valor_ferias
    gozo.valor_terco = terco
    gozo.valor_abono = abono + terco_abono
    gozo.inss = inss
    gozo.encargos = encargos
    gozo.liquido = bruto + abono + terco_abono - inss
    gozo.detalhamento = json.dumps({"itens": itens, "tabela_inss": tabela_inss}, ensure_ascii=False)
    gozo.calculado_em = datetime.now()
    return gozo
