"""13º salário do trabalhador doméstico (Lei 4.090/62 e 4.749/65, aplicadas pela LC 150/2015).

- Avos: 1/12 por mês do ano com 15 dias ou mais de trabalho (a partir da admissão).
- Base: salário de dezembro (ou do mês do pagamento, na 1ª parcela) + média mensal das horas extras do ano.
- 1ª parcela (fevereiro a 30/11): metade do 13º, sem INSS; com registro, gera só FGTS.
- 2ª parcela (até 20/12): 13º integral menos a 1ª parcela e o INSS (calculado sobre o 13º integral, à
  parte do salário). Sem 1ª parcela, a 2ª é a parcela única.
Vale para trabalhadores com e sem registro; sem registro não há INSS nem encargos.
"""
import calendar
import json
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from ..models import DecimoTerceiro, TipoContrato, Trabalhador
from . import tabelas
from .calculo_folha import ZERO, media_horas_extras, q
from .calendario import meses_entre
from .inss import faixas_do_mes, inss_progressivo
from .salario import salario_em


def avos(trabalhador: Trabalhador, ano: int) -> int:
    """Meses do ano com 15 dias ou mais de trabalho, supondo o contrato ativo até dezembro."""
    total = 0
    for mes in range(1, 13):
        ultimo = date(ano, mes, calendar.monthrange(ano, mes)[1])
        inicio = max(date(ano, mes, 1), trabalhador.data_admissao)
        if (ultimo - inicio).days + 1 >= 15:
            total += 1
    return total


def data_padrao(ano: int, parcela: int) -> date:
    return date(ano, 11, 30) if parcela == 1 else date(ano, 12, 20)


def _media_do_ano(trabalhador: Trabalhador, ano: int, ate: date) -> Decimal:
    """Média das horas extras dos meses do ano já trabalhados antes do mês do pagamento."""
    inicio = max(date(ano, 1, 1), trabalhador.data_admissao)
    meses = [m for m in meses_entre(inicio, date(ano, 12, 31)) if m < ate.strftime("%Y-%m")]
    return media_horas_extras(trabalhador, meses)


def calcular_parcela(db: Session, trabalhador: Trabalhador, ano: int, parcela: int,
                     data_pagamento: date | None = None) -> DecimoTerceiro:
    """Calcula (ou recalcula) a parcela e grava. Não faz commit."""
    existentes = {d.parcela: d for d in trabalhador.decimos_terceiros if d.ano == ano}
    registro = existentes.get(parcela)
    if registro and registro.pago_em:
        raise ValueError("Parcela já paga: desfaça o pagamento antes de recalcular.")
    if parcela == 1 and 2 in existentes:
        raise ValueError("A 2ª parcela já foi calculada: exclua-a antes de mexer na 1ª.")
    n = avos(trabalhador, ano)
    if n == 0:
        raise ValueError(f"{trabalhador.nome} não tem meses trabalhados em {ano}.")

    data_pagamento = data_pagamento or (registro.data_pagamento if registro else data_padrao(ano, parcela))
    referencia = date(ano, 12, 1) if parcela == 2 else data_pagamento
    salario = salario_em(trabalhador, referencia)
    media = _media_do_ano(trabalhador, ano, data_pagamento if parcela == 1 else date(ano, 12, 1))
    valor_salario = q(salario * n / 12)
    valor_media = q(media * n / 12)
    integral = valor_salario + valor_media
    clt = trabalhador.tipo_contrato == TipoContrato.com_registro

    itens = []
    adiantamento = inss = encargos = ZERO
    tabela_inss = None
    if parcela == 1:
        bruto = q(integral / 2)
        itens.append({"descricao": "13º salário - adiantamento (1ª parcela, 50%)", "referencia": f"{n}/12 avos",
                      "tipo": "provento", "valor": str(bruto)})
        if clt:
            encargos = q(bruto * (tabelas.ALIQ_FGTS + tabelas.ALIQ_FGTS_INDENIZATORIO))
    else:
        if 1 in existentes:
            adiantamento = Decimal(existentes[1].valor_bruto)
        bruto = integral - adiantamento
        itens.append({"descricao": "13º salário", "referencia": f"{n}/12 avos", "tipo": "provento",
                      "valor": str(valor_salario)})
        if valor_media:
            itens.append({"descricao": "Média de horas extras no 13º", "referencia": f"{n}/12 avos",
                          "tipo": "provento", "valor": str(valor_media)})
        if adiantamento:
            itens.append({"descricao": "Adiantamento do 13º (1ª parcela)", "referencia": "",
                          "tipo": "desconto", "valor": str(adiantamento)})
        if clt:
            faixas, tabela_inss = faixas_do_mes(db, f"{ano}-12")
            inss = inss_progressivo(integral, faixas)
            encargos = q(integral * (tabelas.ALIQ_INSS_PATRONAL + tabelas.ALIQ_GILRAT)
                         + bruto * (tabelas.ALIQ_FGTS + tabelas.ALIQ_FGTS_INDENIZATORIO))
            if inss:
                itens.append({"descricao": "INSS sobre 13º salário", "referencia": f"tabela {tabela_inss}",
                              "tipo": "desconto", "valor": str(inss)})

    if registro is None:
        registro = DecimoTerceiro(trabalhador_id=trabalhador.id, ano=ano, parcela=parcela)
        trabalhador.decimos_terceiros.append(registro)
        db.add(registro)
    registro.avos = n
    registro.salario_base = q(salario)
    registro.media_variaveis = media
    registro.valor_integral = integral
    registro.valor_bruto = bruto
    registro.adiantamento = adiantamento
    registro.inss = inss
    registro.encargos = encargos
    registro.liquido = bruto - inss
    registro.data_pagamento = data_pagamento
    registro.detalhamento = json.dumps({"itens": itens, "tabela_inss": tabela_inss}, ensure_ascii=False)
    registro.calculado_em = datetime.now()
    return registro


def previsao(trabalhador: Trabalhador, ano: int) -> dict:
    """13º integral previsto para o ano, pelo salário vigente em dezembro (ou hoje) e as horas extras."""
    n = avos(trabalhador, ano)
    salario = salario_em(trabalhador, date(ano, 12, 1))
    media = _media_do_ano(trabalhador, ano, date(ano, 12, 1))
    return {"avos": n, "salario_base": q(salario), "media_variaveis": media,
            "valor_integral": q(salario * n / 12) + q(media * n / 12)}
