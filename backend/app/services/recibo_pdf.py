"""Recibos em PDF: holerite (com vínculo, no padrão do recibo de salário do eSocial) e recibo simples
de prestação de serviços domésticos (sem vínculo)."""
import json
from decimal import Decimal

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from ..models import Contratante, FolhaPagamento, TipoContrato
from .esocial import rubrica_do_item

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

_UNIDADES = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez",
             "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
_DEZENAS = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
_CENTENAS = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos",
             "setecentos", "oitocentos", "novecentos"]


def _ate_999(n: int) -> str:
    if n == 100:
        return "cem"
    c, r = divmod(n, 100)
    partes = [_CENTENAS[c]] if c else []
    if r:
        if r < 20:
            partes.append(_UNIDADES[r])
        else:
            d, u = divmod(r, 10)
            partes.append(_DEZENAS[d] + (f" e {_UNIDADES[u]}" if u else ""))
    return " e ".join(partes)


def _inteiro_extenso(n: int) -> str:
    if n == 0:
        return "zero"
    escalas = [("", ""), ("mil", "mil"), ("milhão", "milhões"), ("bilhão", "bilhões")]
    grupos = []
    i = 0
    while n:
        n, g = divmod(n, 1000)
        if g:
            if i == 0:
                texto = _ate_999(g)
            elif i == 1:
                texto = "mil" if g == 1 else f"{_ate_999(g)} mil"
            else:
                texto = f"{_ate_999(g)} {escalas[i][0] if g == 1 else escalas[i][1]}"
            grupos.append((g, texto))
        i += 1
    grupos.reverse()
    resultado = grupos[0][1]
    for g, texto in grupos[1:]:
        resultado += (" e " if g < 100 or g % 100 == 0 else " ") + texto
    return resultado


def valor_por_extenso(valor: Decimal) -> str:
    centavos_total = int((Decimal(valor) * 100).quantize(Decimal("1")))
    reais, centavos = divmod(abs(centavos_total), 100)
    partes = []
    if reais:
        sufixo = "real" if reais == 1 else "reais"
        if reais >= 1_000_000 and reais % 1_000_000 == 0:
            sufixo = "de reais"
        partes.append(f"{_inteiro_extenso(reais)} {sufixo}")
    if centavos:
        partes.append(f"{_inteiro_extenso(centavos)} {'centavo' if centavos == 1 else 'centavos'}")
    return " e ".join(partes) or "zero real"


def brl(valor) -> str:
    texto = f"{Decimal(valor):,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_cpf(cpf: str) -> str:
    if len(cpf) == 11 and cpf.isdigit():
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    return cpf


def formatar_cep(cep: str) -> str:
    return f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else cep


def endereco(c: Contratante | None) -> str:
    """Endereço do local da prestação do serviço em uma linha."""
    if c is None:
        return ""
    rua = ", ".join(p for p in (c.logradouro, c.numero) if p)
    if c.complemento:
        rua = f"{rua} - {c.complemento}" if rua else c.complemento
    cidade = "/".join(p for p in (c.cidade, c.uf) if p)
    partes = (rua, c.bairro, cidade, f"CEP {formatar_cep(c.cep)}" if c.cep else None)
    return " - ".join(p for p in partes if p)


FUNCAO_PADRAO = "Empregado(a) doméstico(a)"


def celula_ajustada(pdf: FPDF, largura: float, altura: float, texto: str, **kwargs) -> None:
    """Célula de uma linha que reduz a fonte quando o texto (ex.: endereço) não cabe."""
    tamanho = pdf.font_size_pt
    while tamanho > 6 and pdf.get_string_width(texto) > largura - 2:
        tamanho -= 0.5
        pdf.set_font_size(tamanho)
    pdf.cell(largura, altura, texto, **kwargs)
    pdf.set_font_size(9)


def referencia_exibida(it: dict, folha: FolhaPagamento) -> str:
    """Referência da linha; no INSS, a alíquota efetiva (desconto ÷ base), como nos holerites usuais."""
    if rubrica_do_item(it) == "5180" and Decimal(folha.salario_bruto) > 0:
        efetiva = Decimal(it["valor"]) / Decimal(folha.salario_bruto) * 100
        return f"{efetiva:.2f}%".replace(".", ",")
    return it.get("referencia", "")


def competencia_extenso(mes_ano: str) -> str:
    ano, mes = mes_ano.split("-")
    return f"{MESES[int(mes) - 1]}/{ano}"


def _rotulo_valor(pdf: FPDF, largura: float, rotulo: str, valor: str, altura: float = 10) -> None:
    """Célula de formulário: rótulo pequeno em cima e valor embaixo (estilo holerite)."""
    x, y = pdf.get_x(), pdf.get_y()
    pdf.cell(largura, altura, "", border=1)
    pdf.set_xy(x + 1, y + 0.6)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(largura - 2, 3, rotulo)
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(x + 1, y + 4)
    pdf.set_font("Helvetica", "", 9)
    celula_ajustada(pdf, largura - 2, 5, valor)
    pdf.set_xy(x + largura, y)


def _marca_rascunho(pdf: FPDF, folha: FolhaPagamento, largura: float) -> None:
    if folha.status.value == "rascunho":
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(200, 0, 0)
        pdf.cell(largura, 5, "RASCUNHO - folha ainda não fechada", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)


# ---------- Com vínculo: holerite no padrão do recibo de salário do eSocial ----------

def _holerite(pdf: FPDF, folha: FolhaPagamento, detalhe: dict, contratante: Contratante | None,
              via_empregador: bool) -> None:
    t = folha.trabalhador
    pdf.add_page()
    largura = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(largura * 0.65, 7, "RECIBO DE PAGAMENTO DE SALÁRIO")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(largura * 0.35, 7, f"Competência: {competencia_extenso(folha.mes_ano).capitalize()}", align="R",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(largura * 0.65, 5, "Empregador(a) doméstico(a) - eSocial")
    pdf.cell(largura * 0.35, 5, "Via do empregador" if via_empregador else "Via do empregado", align="R",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    # Identificação
    cpf_empregador = formatar_cpf(contratante.cpf) if contratante and contratante.cpf else ""
    _rotulo_valor(pdf, largura * 0.72, "EMPREGADOR(A)", contratante.nome if contratante else "")
    _rotulo_valor(pdf, largura * 0.28, "CPF DO EMPREGADOR(A)", cpf_empregador)
    pdf.ln(10)
    _rotulo_valor(pdf, largura, "LOCAL DE TRABALHO", endereco(contratante) or "-")
    pdf.ln(10)
    _rotulo_valor(pdf, largura * 0.72, "EMPREGADO(A)", t.nome)
    _rotulo_valor(pdf, largura * 0.28, "CPF DO EMPREGADO(A)", formatar_cpf(t.cpf))
    pdf.ln(10)
    _rotulo_valor(pdf, largura * 0.44, "FUNÇÃO", t.funcao or FUNCAO_PADRAO)
    _rotulo_valor(pdf, largura * 0.28, "DATA DE ADMISSÃO", t.data_admissao.strftime("%d/%m/%Y"))
    _rotulo_valor(pdf, largura * 0.28, "SALÁRIO CONTRATUAL", f"R$ {brl(folha.salario_base)}")
    pdf.ln(13)

    # Rubricas
    col = [22, largura - 22 - 26 - 30 - 30, 26, 30, 30]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(230, 230, 230)
    for w, txt in zip(col, ["Rubrica", "Descrição", "Referência", "Vencimentos", "Descontos"]):
        pdf.cell(w, 7, txt, border=1, align="C", fill=True)
    pdf.ln()
    itens = detalhe.get("itens", [])
    for it in itens:
        rubrica = rubrica_do_item(it)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.cell(col[0], 6, f"eSocial{rubrica}" if rubrica else it["codigo"], border="LR", align="C")
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(col[1], 6, it["descricao"], border="LR")
        celula_ajustada(pdf, col[2], 6, referencia_exibida(it, folha), border="LR", align="C")
        pdf.cell(col[3], 6, brl(it["valor"]) if it["tipo"] == "provento" else "", border="LR", align="R")
        pdf.cell(col[4], 6, brl(it["valor"]) if it["tipo"] == "desconto" else "", border="LR", align="R")
        pdf.ln()
    for _ in range(max(0, 8 - len(itens))):  # altura mínima do quadro, como no formulário impresso
        for w in col:
            pdf.cell(w, 6, "", border="LR")
        pdf.ln()

    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(sum(col[:3]), 7, "Totais", border=1, align="R")
    pdf.cell(col[3], 7, brl(folha.total_proventos), border=1, align="R")
    pdf.cell(col[4], 7, brl(folha.total_descontos), border=1, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(sum(col[:3]), 9, "VALOR LÍQUIDO", border=1, align="R", fill=True)
    pdf.cell(col[3] + col[4], 9, f"R$ {brl(folha.salario_liquido)}", border=1, align="R", fill=True,
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    # Bases de cálculo (rodapé do holerite)
    enc = detalhe.get("encargos", {}).get("itens", {})
    fgts = next((v for k, v in enc.items() if k.startswith("FGTS (")), "0")
    base_irrf = Decimal(folha.salario_bruto) - Decimal(folha.inss_empregado)
    bases = [("SALÁRIO BASE", folha.salario_base), ("BASE CÁLC. INSS", folha.salario_bruto),
             ("BASE CÁLC. FGTS", folha.salario_bruto), ("FGTS DO MÊS", fgts), ("BASE CÁLC. IRRF", base_irrf)]
    for rotulo, valor in bases:
        _rotulo_valor(pdf, largura / 5, rotulo, brl(valor))
    pdf.ln(12)

    pdf.set_font("Helvetica", "", 8)
    for inf in detalhe.get("beneficios_informativos", []):
        pdf.cell(largura, 4.5, f"{inf['descricao']} fornecido à parte: R$ {brl(inf['valor'])}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if detalhe.get("tabela_inss"):
        pdf.cell(largura, 4.5, f"INSS calculado pela tabela progressiva ({detalhe['tabela_inss']}).",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # Declaração: a data é preenchida pelo empregado (orientação do manual do eSocial)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.multi_cell(
        largura, 5,
        f"Declaro ter recebido a importância líquida de R$ {brl(folha.salario_liquido)} "
        f"({valor_por_extenso(folha.salario_liquido)}), discriminada neste recibo, referente ao salário de "
        f"{competencia_extenso(folha.mes_ano)}.",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.ln(12)
    pdf.cell(largura * 0.4, 5, "Data: ____/____/________")
    pdf.cell(largura * 0.6, 5, "_________________________________________________", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(largura * 0.4, 5, "")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.cell(largura * 0.6, 5, f"Assinatura do(a) empregado(a): {t.nome}", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    if via_empregador and enc:
        # Demonstrativo dos valores devidos: só na via do empregador
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(largura, 6, "DEMONSTRATIVO DOS VALORES DEVIDOS - estimativa da guia DAE (uso do empregador)",
                 border="B", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8.5)
        for rotulo, valor in enc.items():
            pdf.cell(largura * 0.75, 4.8, rotulo)
            pdf.cell(largura * 0.25, 4.8, f"R$ {brl(valor)}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(largura * 0.75, 5.5, "Total estimado da DAE", border="T")
        pdf.cell(largura * 0.25, 5.5, f"R$ {brl(folha.encargos_recolher_guardar)}", border="T", align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.cell(largura, 4.5, "O valor oficial é o da DAE emitida pelo eSocial após o fechamento da folha "
                               "(vencimento: dia 20 do mês seguinte).", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    _marca_rascunho(pdf, folha, largura)


# ---------- Sem vínculo: recibo simples de prestação de serviços ----------

# Termos de emprego (salário, horas extras, faltas) não cabem em prestação de serviço
_DESCRICAO_SERVICO = {"002": "Horas adicionais", "003": "Gratificação", "101": "Dias não trabalhados",
                      "105": "Atrasos", "102": "Adiantamentos já recebidos"}


def _descricao_servico(it: dict) -> str:
    base = _DESCRICAO_SERVICO.get(it["codigo"])
    if it["codigo"] == "002":
        return f"{base} {it['descricao'].split()[-1]}"  # mantém o percentual
    return base or it["descricao"]


def _recibo_servico(pdf: FPDF, folha: FolhaPagamento, detalhe: dict, contratante: Contratante | None,
                    via: str) -> None:
    t = folha.trabalhador
    largura = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(largura * 0.6, 9, "RECIBO")
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(largura * 0.4, 9, f"R$ {brl(folha.salario_liquido)}", border=1, align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(largura, 5, f"Prestação de serviços domésticos - {via}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    if contratante:
        pagador = contratante.nome + (f", CPF nº {formatar_cpf(contratante.cpf)}" if contratante.cpf else "")
    else:
        pagador = "____________________________________, CPF nº ______________"
    local = endereco(contratante)
    pdf.set_font("Helvetica", "", 10.5)
    pdf.multi_cell(
        largura, 6,
        f"Eu, {t.nome}, inscrito(a) no CPF sob o nº {formatar_cpf(t.cpf)}, declaro que recebi de {pagador}, "
        f"a importância de R$ {brl(folha.salario_liquido)} ({valor_por_extenso(folha.salario_liquido)}), "
        f"referente ao pagamento de serviços domésticos prestados em {competencia_extenso(folha.mes_ano)} "
        f"({folha.dias_trabalhados} dias)" + (f", no endereço {local}" if local else "") + ".",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )

    itens = detalhe.get("itens", [])
    if len(itens) > 1:  # só discrimina quando há mais que o valor dos serviços
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(largura, 5, "Discriminação", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8.5)
        for it in itens:
            sinal = "(-) " if it["tipo"] == "desconto" else ""
            ref = f" ({it['referencia']})" if it.get("referencia") else ""
            pdf.cell(largura * 0.75, 4.6, f"{sinal}{_descricao_servico(it)}{ref}")
            pdf.cell(largura * 0.25, 4.6, f"R$ {brl(it['valor'])}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(largura * 0.75, 5, "Valor recebido", border="T")
        pdf.cell(largura * 0.25, 5, f"R$ {brl(folha.salario_liquido)}", border="T", align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 8)
    for inf in detalhe.get("beneficios_informativos", []):
        pdf.cell(largura, 4.5, f"{inf['descricao']} fornecido à parte: R$ {brl(inf['valor'])}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(6)
    pdf.set_font("Helvetica", "", 10)
    cidade = contratante.cidade if contratante and contratante.cidade else "_______________________"
    pdf.cell(largura, 6, f"{cidade}, ____ de ____________________ de ________.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(12)
    pdf.cell(largura, 5, "_________________________________________________", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(largura, 5, f"{t.nome} - CPF {formatar_cpf(t.cpf)}", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    _marca_rascunho(pdf, folha, largura)


def _linha_de_recorte(pdf: FPDF) -> None:
    pdf.ln(4)
    pdf.set_draw_color(150, 150, 150)
    pdf.set_dash_pattern(dash=1.5, gap=1.5)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.set_dash_pattern()
    pdf.set_draw_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.cell(0, 4, "recorte aqui", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)


def gerar_recibo_pdf(folha: FolhaPagamento, contratante: Contratante | None = None) -> bytes:
    detalhe = json.loads(folha.detalhamento or "{}")
    pdf = FPDF(format="A4")
    pdf.set_margins(12, 12, 12)
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.set_title(f"Recibo {folha.trabalhador.nome} {folha.mes_ano}")
    if folha.trabalhador.tipo_contrato == TipoContrato.com_registro:
        _holerite(pdf, folha, detalhe, contratante, via_empregador=True)
        _holerite(pdf, folha, detalhe, contratante, via_empregador=False)
    else:
        # As duas vias na mesma folha A4, separadas por uma linha de recorte
        pdf.add_page()
        _recibo_servico(pdf, folha, detalhe, contratante, "via do contratante")
        if pdf.get_y() > pdf.h / 2 - 6:  # discriminação longa: segunda via em outra página
            pdf.add_page()
        else:
            pdf.set_y(pdf.h / 2 - 6)
            _linha_de_recorte(pdf)
        _recibo_servico(pdf, folha, detalhe, contratante, "via do prestador")
    return bytes(pdf.output())
