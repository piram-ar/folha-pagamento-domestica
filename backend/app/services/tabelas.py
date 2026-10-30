"""Parâmetros legais usados no cálculo da folha.

ATENÇÃO: a tabela do INSS é reajustada todo ano (normalmente em janeiro).
Os valores abaixo são os de 2025. Atualize-os aqui ou, sem rebuild, defina a
variável de ambiente TABELA_INSS_JSON no arquivo .env, por exemplo:
TABELA_INSS_JSON=[["1518.00","0.075"],["2793.88","0.09"],["4190.83","0.12"],["8157.41","0.14"]]
(cada item = [teto da faixa, alíquota]).
"""
import json
import os
from decimal import Decimal

# Jornada do doméstico (LC 150/2015): 44h semanais -> divisor 220 para o valor-hora
DIVISOR_HORAS_MENSAL = Decimal(os.getenv("DIVISOR_HORAS_MENSAL", "220"))
# Mês comercial para o salário proporcional
DIAS_MES_COMERCIAL = Decimal("30")

_FAIXAS_INSS_PADRAO = [
    ["1518.00", "0.075"],
    ["2793.88", "0.09"],
    ["4190.83", "0.12"],
    ["8157.41", "0.14"],
]
FAIXAS_INSS = [
    (Decimal(teto), Decimal(aliquota))
    for teto, aliquota in (json.loads(os.getenv("TABELA_INSS_JSON") or "null") or _FAIXAS_INSS_PADRAO)
]

# Encargos do empregador doméstico recolhidos no DAE do eSocial
ALIQ_INSS_PATRONAL = Decimal(os.getenv("ALIQ_INSS_PATRONAL", "0.08"))
ALIQ_GILRAT = Decimal(os.getenv("ALIQ_GILRAT", "0.008"))
ALIQ_FGTS = Decimal(os.getenv("ALIQ_FGTS", "0.08"))
ALIQ_FGTS_INDENIZATORIO = Decimal(os.getenv("ALIQ_FGTS_INDENIZATORIO", "0.032"))

# Dias de férias por período aquisitivo completo
DIAS_FERIAS_POR_PERIODO = 30
