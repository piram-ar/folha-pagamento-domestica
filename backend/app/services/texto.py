"""Texto seguro para os PDFs e para os nomes dos arquivos baixados.

As fontes embutidas do PDF (Helvetica) só têm os caracteres do Latin-1. Aspas curvas, travessão ou emoji colados
do WhatsApp em um nome ou observação derrubavam o recibo com erro 500. Aqui eles viram o equivalente mais próximo.
"""
import re
import unicodedata
from urllib.parse import quote


SUBSTITUTOS = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'", "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "–": "-", "—": "-", "―": "-", "‐": "-", "‑": "-", "−": "-", "…": "...", "•": "-", "·": "-",
    "€": "EUR", "™": "(TM)", "Ł": "L", "ł": "l", "Đ": "D", "đ": "d", "Ø": "O", "ø": "o", "Œ": "OE", "œ": "oe",
    "ı": "i", "ß": "ss", "​": "", "‌": "", "‍": "", "﻿": "", "️": "",
}


def _caractere_latin1(c: str) -> str:
    if c in SUBSTITUTOS:
        return SUBSTITUTOS[c]
    try:
        c.encode("latin-1")
        return c
    except UnicodeEncodeError:
        pass
    sem_acento = "".join(x for x in unicodedata.normalize("NFKD", c) if not unicodedata.combining(x))
    try:
        if sem_acento:
            sem_acento.encode("latin-1")
            return sem_acento
    except UnicodeEncodeError:
        pass
    # Emoji e outros símbolos somem; letras de outros alfabetos viram "?"
    return "" if unicodedata.category(c).startswith(("S", "C")) else "?"


def latin1(texto: str) -> str:
    try:
        texto.encode("latin-1")
        return texto
    except UnicodeEncodeError:
        return "".join(_caractere_latin1(c) for c in texto)


def disposicao(nome: str, modo: str = "inline") -> str:
    """Cabeçalho Content-Disposition: nome ASCII simples (filename=) e o nome completo em UTF-8 (filename*=)."""
    simples = unicodedata.normalize("NFKD", latin1(nome)).encode("ascii", "ignore").decode("ascii")
    simples = re.sub(r"[^A-Za-z0-9._-]+", "_", simples).strip("_") or "arquivo"
    return f"{modo}; filename=\"{simples}\"; filename*=UTF-8''{quote(nome, safe='')}"


def primeiro_nome(nome: str) -> str:
    """Primeiro nome em minúsculas para o nome do arquivo ("" vira "trabalhador")."""
    partes = nome.split()
    return partes[0].lower() if partes else "trabalhador"
