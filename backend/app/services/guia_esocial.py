"""Guia de lançamento da folha no eSocial do empregador doméstico (PDF e CSV).

O eSocial doméstico não importa arquivos: a folha é digitada em "Folha/Recolhimento > Folha de
pagamento", rubrica a rubrica. A guia lista, por empregado, as rubricas e valores a informar.
"""
import csv
import io
import json
from decimal import Decimal

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from ..models import FolhaPagamento
from .esocial import AUTOMATICAS, RUBRICAS, rubrica_do_item
from .recibo_pdf import brl, celula_ajustada, competencia_extenso, formatar_cpf, referencia_exibida
from .salario import inicio_do_mes


def linhas_da_folha(folha: FolhaPagamento) -> list[dict]:
    detalhe = json.loads(folha.detalhamento or "{}")
    linhas = []
    for it in detalhe.get("itens", []):
        rubrica = rubrica_do_item(it)
        if rubrica in AUTOMATICAS:
            obs = "Calculada pelo eSocial: só confira"
        elif rubrica is None:
            obs = "Sem rubrica equivalente: avalie como lançar"
        else:
            obs = ""
        linhas.append({
            "rubrica": f"eSocial{rubrica}" if rubrica else "-",
            "descricao": RUBRICAS.get(rubrica, it["descricao"]),
            "item_recibo": it["descricao"],
            "tipo": "Vencimento" if it["tipo"] == "provento" else "Desconto",
            "referencia": referencia_exibida(it, folha),
            "valor": Decimal(it["valor"]),
            "observacao": obs,
        })
    return linhas


def _alertas(folha: FolhaPagamento) -> list[str]:
    alertas = []
    inicio = inicio_do_mes(folha.mes_ano)
    if any(r.vigencia == inicio for r in folha.trabalhador.reajustes):
        alertas.append("Houve reajuste salarial neste mês: antes de lançar a folha, registre a alteração do salário "
                       "no cadastro do empregado no eSocial (alteração contratual).")
    if folha.status.value != "fechada":
        alertas.append("Folha ainda em rascunho neste sistema: os valores podem mudar.")
    return alertas


def gerar_csv(folhas: list[FolhaPagamento]) -> bytes:
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow(["competencia", "cpf", "empregado", "rubrica", "descricao_esocial", "tipo", "referencia",
                       "valor", "observacao"])
    for f in folhas:
        for l in linhas_da_folha(f):
            escritor.writerow([f.mes_ano, formatar_cpf(f.trabalhador.cpf), f.trabalhador.nome, l["rubrica"],
                               l["descricao"], l["tipo"], l["referencia"], brl(l["valor"]), l["observacao"]])
    return ("﻿" + saida.getvalue()).encode("utf-8")  # BOM: o Excel abre os acentos corretamente


def gerar_pdf(folhas: list[FolhaPagamento], mes_ano: str) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_margins(12, 12, 12)
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.set_title(f"Guia de lançamento eSocial {mes_ano}")
    pdf.add_page()
    largura = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(largura, 7, "Guia de lançamento da folha no eSocial", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(largura, 5, f"Competência: {competencia_extenso(mes_ano).capitalize()}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.multi_cell(
        largura, 4.5,
        "O eSocial do empregador doméstico não aceita importação de arquivos. Em Folha/Recolhimento > Folha de "
        "pagamento, abra o mês, selecione cada empregado e informe as rubricas abaixo (Remuneração: vencimentos e "
        "descontos). Salário e INSS são calculados pelo próprio eSocial: use os valores daqui para conferir. "
        "Depois, encerre a folha e emita a DAE.",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.ln(3)

    if not folhas:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(largura, 8, "Nenhuma folha de empregado com registro calculada nesta competência.")
    col = [22, largura - 22 - 20 - 22 - 22 - 46, 20, 22, 22, 46]
    for f in folhas:
        if pdf.get_y() > pdf.h - 70:
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(largura, 7, f"{f.trabalhador.nome} - CPF {formatar_cpf(f.trabalhador.cpf)}", border="B",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(largura, 5, f"Salário do mês: R$ {brl(f.salario_base)}  -  Dias trabalhados: {f.dias_trabalhados}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        for alerta in _alertas(f):
            pdf.set_text_color(160, 60, 0)
            pdf.multi_cell(largura, 4.3, f"Atenção: {alerta}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(230, 230, 230)
        for w, txt in zip(col, ["Rubrica", "Descrição no eSocial", "Tipo", "Referência", "Valor (R$)", "Observação"]):
            pdf.cell(w, 6, txt, border=1, fill=True)
        pdf.ln()
        for l in linhas_da_folha(f):
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(col[0], 5.5, l["rubrica"], border=1)
            celula_ajustada(pdf, col[1], 5.5, l["descricao"], border=1)
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(col[2], 5.5, l["tipo"], border=1, align="C")
            celula_ajustada(pdf, col[3], 5.5, l["referencia"], border=1, align="C")
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(col[4], 5.5, brl(l["valor"]), border=1, align="R")
            pdf.set_font("Helvetica", "", 7)
            celula_ajustada(pdf, col[5], 5.5, l["observacao"], border=1)
            pdf.ln()
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(largura, 5.5, f"Líquido: R$ {brl(f.salario_liquido)}   -   DAE estimada: R$ {brl(f.encargos_recolher_guardar)}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)
    return bytes(pdf.output())
