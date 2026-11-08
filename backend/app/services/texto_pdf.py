"""FPDF que não derruba o recibo por causa de um caractere fora do Latin-1 (ver services/texto.py)."""
from fpdf import FPDF

from .texto import latin1


class PDF(FPDF):
    """FPDF que troca, em vez de recusar, os caracteres que a fonte embutida não tem."""

    def normalize_text(self, text: str) -> str:
        if not self.is_ttf_font:
            text = latin1(text)
        return super().normalize_text(text)
