"""Recibos de férias e de 13º salário em PDF (duas vias, uma por página), para com e sem registro."""
import json
from datetime import timedelta
from decimal import Decimal

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from ..models import Contratante, DecimoTerceiro, GozoFerias, TipoContrato, Trabalhador
from .recibo_pdf import FUNCAO_PADRAO, _rotulo_valor, brl, celula_ajustada, endereco, formatar_cpf, valor_por_extenso


def _via(pdf: FPDF, titulo: str, via: str, t: Trabalhador, contratante: Contratante | None,
         campos: list[tuple[str, str]], itens: list[dict], liquido: Decimal, referente: str) -> None:
    pdf.add_page()
    largura = pdf.w - pdf.l_margin - pdf.r_margin
    clt = t.tipo_contrato == TipoContrato.com_registro

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(largura * 0.7, 7, titulo)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(largura * 0.3, 7, via, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    cpf_contratante = formatar_cpf(contratante.cpf) if contratante and contratante.cpf else ""
    _rotulo_valor(pdf, largura * 0.72, "EMPREGADOR(A)" if clt else "CONTRATANTE", contratante.nome if contratante else "")
    _rotulo_valor(pdf, largura * 0.28, "CPF", cpf_contratante)
    pdf.ln(10)
    _rotulo_valor(pdf, largura, "LOCAL DE TRABALHO", endereco(contratante) or "-")
    pdf.ln(10)
    _rotulo_valor(pdf, largura * 0.72, "EMPREGADO(A)" if clt else "TRABALHADOR(A)", t.nome)
    _rotulo_valor(pdf, largura * 0.28, "CPF", formatar_cpf(t.cpf))
    pdf.ln(10)
    _rotulo_valor(pdf, largura * 0.44, "FUNÇÃO", t.funcao or FUNCAO_PADRAO)
    _rotulo_valor(pdf, largura * 0.28, "DATA DE ADMISSÃO", t.data_admissao.strftime("%d/%m/%Y"))
    _rotulo_valor(pdf, largura * 0.28, "VÍNCULO", "Com registro" if clt else "Sem registro")
    pdf.ln(10)
    for rotulo, valor in campos:
        _rotulo_valor(pdf, largura / len(campos), rotulo, valor)
    pdf.ln(13)

    col = [largura - 30 - 32 - 32, 30, 32, 32]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(230, 230, 230)
    for w, txt in zip(col, ["Descrição", "Referência", "Vencimentos", "Descontos"]):
        pdf.cell(w, 7, txt, border=1, align="C", fill=True)
    pdf.ln()
    proventos = descontos = Decimal("0")
    for it in itens:
        valor = Decimal(it["valor"])
        if it["tipo"] == "provento":
            proventos += valor
        else:
            descontos += valor
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(col[0], 6, it["descricao"], border="LR")
        celula_ajustada(pdf, col[1], 6, it.get("referencia", ""), border="LR", align="C")
        pdf.cell(col[2], 6, brl(valor) if it["tipo"] == "provento" else "", border="LR", align="R")
        pdf.cell(col[3], 6, brl(valor) if it["tipo"] == "desconto" else "", border="LR", align="R")
        pdf.ln()
    for _ in range(max(0, 5 - len(itens))):
        for w in col:
            pdf.cell(w, 6, "", border="LR")
        pdf.ln()
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(sum(col[:2]), 7, "Totais", border=1, align="R")
    pdf.cell(col[2], 7, brl(proventos), border=1, align="R")
    pdf.cell(col[3], 7, brl(descontos), border=1, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(sum(col[:2]), 9, "VALOR LÍQUIDO", border=1, align="R", fill=True)
    pdf.cell(col[2] + col[3], 9, f"R$ {brl(liquido)}", border=1, align="R", fill=True,
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 9.5)
    pdf.multi_cell(
        largura, 5,
        f"Declaro ter recebido a importância líquida de R$ {brl(liquido)} ({valor_por_extenso(liquido)}), "
        f"discriminada neste recibo, referente {referente}.",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.ln(12)
    pdf.cell(largura * 0.4, 5, "Data: ____/____/________")
    pdf.cell(largura * 0.6, 5, "_________________________________________________", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(largura * 0.4, 5, "")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.cell(largura * 0.6, 5, f"Assinatura: {t.nome}", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _documento(titulo: str, t: Trabalhador, contratante: Contratante | None, campos, itens, liquido,
               referente: str) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_margins(12, 12, 12)
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.set_title(f"{titulo} {t.nome}")
    clt = t.tipo_contrato == TipoContrato.com_registro
    vias = ("Via do empregador", "Via do empregado") if clt else ("Via do contratante", "Via do trabalhador")
    for via in vias:
        _via(pdf, titulo, via, t, contratante, campos, itens, liquido, referente)
    return bytes(pdf.output())


def recibo_ferias(gozo: GozoFerias, contratante: Contratante | None) -> bytes:
    periodo = gozo.periodo
    detalhe = json.loads(gozo.detalhamento or "{}")
    campos = [
        ("PERÍODO AQUISITIVO", f"{periodo.periodo_aquisitivo_inicio:%d/%m/%Y} a {periodo.periodo_aquisitivo_fim:%d/%m/%Y}"),
        ("PERÍODO DE GOZO", f"{gozo.data_inicio:%d/%m/%Y} a {gozo.data_fim:%d/%m/%Y}"),
        ("RETORNO", f"{gozo.data_fim + timedelta(days=1):%d/%m/%Y}"),
        ("PAGAMENTO", f"{gozo.data_pagamento:%d/%m/%Y}"),
    ]
    referente = (f"às férias de {gozo.dias} dias gozadas de {gozo.data_inicio:%d/%m/%Y} a {gozo.data_fim:%d/%m/%Y}, "
                 f"acrescidas de 1/3, do período aquisitivo de {periodo.periodo_aquisitivo_inicio:%d/%m/%Y} a "
                 f"{periodo.periodo_aquisitivo_fim:%d/%m/%Y}"
                 + (f", e ao abono pecuniário de {gozo.dias_abono} dias vendidos" if gozo.dias_abono else ""))
    return _documento("RECIBO DE FÉRIAS", periodo.trabalhador, contratante, campos, detalhe.get("itens", []),
                      Decimal(gozo.liquido), referente)


def recibo_decimo_terceiro(d: DecimoTerceiro, contratante: Contratante | None) -> bytes:
    detalhe = json.loads(d.detalhamento or "{}")
    nome_parcela = "1ª PARCELA" if d.parcela == 1 else ("2ª PARCELA" if d.adiantamento else "PARCELA ÚNICA")
    campos = [
        ("ANO", str(d.ano)),
        ("AVOS", f"{d.avos}/12"),
        ("SALÁRIO BASE", f"R$ {brl(d.salario_base)}"),
        ("PAGAMENTO", f"{d.data_pagamento:%d/%m/%Y}"),
    ]
    referente = f"ao 13º salário de {d.ano} ({nome_parcela.lower()})"
    return _documento(f"RECIBO DE 13º SALÁRIO - {nome_parcela}", d.trabalhador, contratante, campos,
                      detalhe.get("itens", []), Decimal(d.liquido), referente)
