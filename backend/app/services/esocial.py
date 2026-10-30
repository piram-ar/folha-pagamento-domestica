"""Rubricas do eSocial do empregador doméstico usadas pelo sistema.

Fonte: Manual do eSocial do Empregador Doméstico (versão 13/08/2026), tabela de rubricas.
O módulo doméstico do eSocial não aceita importação de arquivo: os valores são digitados na tela
"Folha/Recolhimento". Por isso o sistema gera uma guia de lançamento (PDF/CSV) com estas rubricas.
"""

RUBRICAS = {
    "1000": "Salário",
    "1100": "Horas extras",
    "1350": "Outros adicionais",
    "1410": "Gratificações",
    "1550": "Vale-Transporte - Adiantamento pago em dinheiro",
    "5050": "Atrasos",
    "5060": "Faltas",
    "5090": "Vale-Transporte - Desconto",
    "5098": "Desconto do adiantamento de salário",
    "5166": "Assistência Médica e/ou Odontológica - Desconto (empregado doméstico)",
    "5180": "Contribuição previdenciária do empregado (INSS)",
}

# Preenchidas pelo próprio eSocial (a partir do cadastro e do cálculo dele): servem só para conferência
AUTOMATICAS = {"1000", "5180"}

# Linhas do recibo -> rubrica, para folhas calculadas antes de o código eSocial ser gravado no item
_POR_CODIGO = {"001": "1000", "002": "1100", "003": "1410", "101": "5060", "102": "5098", "103": "5180", "105": "5050"}


def rubrica_beneficio(tipo: str, desconto: bool) -> str | None:
    if tipo == "vale_transporte":
        return "5090" if desconto else "1550"
    if desconto:
        return "5166" if tipo == "plano_saude" else None
    return "1350"  # benefício pago em dinheiro junto com o salário tem natureza salarial


def rubrica_do_item(item: dict) -> str | None:
    if item.get("esocial"):
        return item["esocial"]
    codigo, descricao = item.get("codigo"), item.get("descricao", "").lower()
    if codigo in ("004", "104"):
        tipo = "vale_transporte" if "transporte" in descricao else "plano_saude" if "saúde" in descricao else "outro"
        return rubrica_beneficio(tipo, codigo == "104")
    return _POR_CODIGO.get(codigo)
