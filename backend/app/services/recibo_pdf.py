"""Geração do recibo de pagamento (holerite) em PDF."""
import json
from decimal import Decimal

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from ..models import Contratante, FolhaPagamento, TipoContrato

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


# Com registro (CLT) a relação é de emprego; sem registro, de prestação de serviço
TERMOS = {
    TipoContrato.com_registro: {
        "titulo": "RECIBO DE PAGAMENTO DE SALÁRIO",
        "contratante": "Empregador(a)",
        "contratado": "Empregado(a)",
        "vinculo": "Com registro (CLT / eSocial)",
        "referente": "ao pagamento de",
        "valor_base": "Salário base",
    },
    TipoContrato.sem_registro: {
        "titulo": "RECIBO DE PAGAMENTO DE SERVIÇOS PRESTADOS",
        "contratante": "Contratante",
        "contratado": "Contratado(a)",
        "vinculo": "Sem registro (prestação de serviço)",
        "referente": "aos serviços prestados em",
        "valor_base": "Valor mensal",
    },
}


def _linha_ajustada(pdf: FPDF, largura: float, altura: float, texto: str, **kwargs) -> None:
    """Célula de uma linha que reduz a fonte quando o texto (ex.: endereço) não cabe."""
    tamanho = pdf.font_size_pt
    while tamanho > 6 and pdf.get_string_width(texto) > largura - 2:
        tamanho -= 0.5
        pdf.set_font_size(tamanho)
    pdf.cell(largura, altura, texto, **kwargs)
    pdf.set_font_size(9)


def competencia_extenso(mes_ano: str) -> str:
    ano, mes = mes_ano.split("-")
    return f"{MESES[int(mes) - 1]}/{ano}"


def _via(pdf: FPDF, folha: FolhaPagamento, detalhe: dict, contratante: Contratante | None, titulo_via: str) -> None:
    t = folha.trabalhador
    termos = TERMOS[t.tipo_contrato]
    nome_contratante = contratante.nome if contratante else termos["contratante"]
    pdf.add_page()
    largura = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(largura, 8, termos["titulo"], align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(largura, 5, titulo_via, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # Cabeçalho empregador / empregado (contratante / contratado)
    pdf.set_font("Helvetica", "", 9)
    cpf_contratante = f"  -  CPF {formatar_cpf(contratante.cpf)}" if contratante and contratante.cpf else ""
    linhas = [
        (termos["contratante"], nome_contratante + cpf_contratante),
        (termos["contratado"], f"{t.nome}  -  CPF {formatar_cpf(t.cpf)}"),
        ("Local do serviço", endereco(contratante) or "-"),
        ("Admissão" if t.tipo_contrato == TipoContrato.com_registro else "Início", t.data_admissao.strftime("%d/%m/%Y")),
        ("Vínculo", termos["vinculo"]),
        ("Competência", competencia_extenso(folha.mes_ano).capitalize()),
        (termos["valor_base"], f"R$ {brl(folha.salario_base)}   -   Dias trabalhados: {folha.dias_trabalhados}"),
    ]
    for rotulo, valor in linhas:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(32, 6, rotulo, border=1)
        pdf.set_font("Helvetica", "", 9)
        _linha_ajustada(pdf, largura - 32, 6, valor, border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # Tabela de proventos e descontos
    col = [14, largura - 14 - 30 - 32 - 32, 30, 32, 32]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    for w, txt in zip(col, ["Cód.", "Descrição", "Referência", "Proventos", "Descontos"]):
        pdf.cell(w, 7, txt, border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for it in detalhe.get("itens", []):
        provento = brl(it["valor"]) if it["tipo"] == "provento" else ""
        desconto = brl(it["valor"]) if it["tipo"] == "desconto" else ""
        pdf.cell(col[0], 6, it["codigo"], border="LR", align="C")
        pdf.cell(col[1], 6, it["descricao"], border="LR")
        pdf.cell(col[2], 6, it.get("referencia", ""), border="LR", align="C")
        pdf.cell(col[3], 6, provento, border="LR", align="R")
        pdf.cell(col[4], 6, desconto, border="LR", align="R")
        pdf.ln()
    # linha de fechamento + totais
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(sum(col[:3]), 7, "Totais", border=1, align="R")
    pdf.cell(col[3], 7, brl(folha.total_proventos), border=1, align="R")
    pdf.cell(col[4], 7, brl(folha.total_descontos), border=1, align="R")
    pdf.ln()
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(sum(col[:3]), 9, "VALOR LÍQUIDO A RECEBER", border=1, align="R", fill=True)
    pdf.cell(col[3] + col[4], 9, f"R$ {brl(folha.salario_liquido)}", border=1, align="R", fill=True)
    pdf.ln(12)

    # Bases / informativos
    pdf.set_font("Helvetica", "", 8)
    if t.tipo_contrato == TipoContrato.com_registro:
        enc = detalhe.get("encargos", {}).get("itens", {})
        fgts = next((v for k, v in enc.items() if k.startswith("FGTS (")), "0")
        pdf.cell(largura, 5, f"Base de cálculo INSS/FGTS: R$ {brl(folha.salario_bruto)}    "
                             f"FGTS do mês (depositado pelo empregador): R$ {brl(fgts)}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for inf in detalhe.get("beneficios_informativos", []):
        pdf.cell(largura, 5, f"{inf['descricao']} fornecido à parte: R$ {brl(inf['valor'])}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    # Declaração e assinatura
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        largura, 5.5,
        f"Declaro ter recebido de {nome_contratante} a importância líquida de R$ {brl(folha.salario_liquido)} "
        f"({valor_por_extenso(folha.salario_liquido)}), referente {termos['referente']} "
        f"{competencia_extenso(folha.mes_ano)}, conforme discriminado acima.",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.ln(18)
    pdf.cell(largura / 2 - 5, 5, "Local e data: ____/____/________")
    pdf.cell(largura / 2 + 5, 5, "_______________________________________", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(largura / 2 - 5, 5, "")
    pdf.cell(largura / 2 + 5, 5, t.nome, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if folha.status.value == "rascunho":
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(200, 0, 0)
        pdf.ln(6)
        pdf.cell(largura, 5, "RASCUNHO - folha ainda não fechada", align="C")
        pdf.set_text_color(0, 0, 0)


def gerar_recibo_pdf(folha: FolhaPagamento, contratante: Contratante | None = None) -> bytes:
    detalhe = json.loads(folha.detalhamento or "{}")
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_title(f"Recibo {folha.trabalhador.nome} {folha.mes_ano}")
    termos = TERMOS[folha.trabalhador.tipo_contrato]
    _via(pdf, folha, detalhe, contratante, f"1ª via - {termos['contratante']}")
    _via(pdf, folha, detalhe, contratante, f"2ª via - {termos['contratado']}")
    return bytes(pdf.output())
