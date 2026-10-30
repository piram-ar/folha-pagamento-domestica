"""Parâmetros legais usados no cálculo da folha.

A tabela progressiva do INSS é cadastrada pela tela "Tabela do INSS" (tabelas tabelas_inss/faixas_inss),
uma por vigência. A lista abaixo (2025) só é usada se não houver nenhuma tabela cadastrada.
"""
import os
from decimal import Decimal

# Jornada do doméstico (LC 150/2015): 44h semanais -> divisor 220 para o valor-hora
DIVISOR_HORAS_MENSAL = Decimal(os.getenv("DIVISOR_HORAS_MENSAL", "220"))
# Mês comercial para o salário proporcional
DIAS_MES_COMERCIAL = Decimal("30")

# (teto da faixa, alíquota em fração)
FAIXAS_INSS_PADRAO = [
    (Decimal("1518.00"), Decimal("0.075")),
    (Decimal("2793.88"), Decimal("0.09")),
    (Decimal("4190.83"), Decimal("0.12")),
    (Decimal("8157.41"), Decimal("0.14")),
]

# Encargos do empregador doméstico recolhidos no DAE do eSocial
ALIQ_INSS_PATRONAL = Decimal(os.getenv("ALIQ_INSS_PATRONAL", "0.08"))
ALIQ_GILRAT = Decimal(os.getenv("ALIQ_GILRAT", "0.008"))
ALIQ_FGTS = Decimal(os.getenv("ALIQ_FGTS", "0.08"))
ALIQ_FGTS_INDENIZATORIO = Decimal(os.getenv("ALIQ_FGTS_INDENIZATORIO", "0.032"))

# Dias de férias por período aquisitivo completo
DIAS_FERIAS_POR_PERIODO = 30
