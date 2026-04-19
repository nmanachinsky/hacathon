"""PDF: pypdf (быстро) с fallback на pdfplumber."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ..types import TextChunk


def _extract_pypdf(path: Path, max_pages: int) -> tuple[list[str], int]:
    """Вернуть (тексты_страниц, общее_число_страниц)."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    total = len(reader.pages)
    pages_text: list[str] = []
    for i, page in enumerate(reader.pages[:max_pages]):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        pages_text.append(text)
    return pages_text, total


def _extract_pdfplumber(path: Path, max_pages: int) -> list[str]:
    import pdfplumber

    pages_text: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            pages_text.append(text)
    return pages_text


def extract(path: Path, max_pages: int = 500) -> Iterable[TextChunk]:
    pages_text, total = _extract_pypdf(path, max_pages)
    text_quality = sum(len(t) for t in pages_text)

    # Если pypdf дал частичный результат — pdfplumber может извлечь больше.
    # Полностью пустой PDF (quality == 0) — это скан, pdfplumber тоже вернёт 0,
    # поэтому проверяем 0 < quality < 200, чтобы избежать двойного полного прохода.
    if 0 < text_quality < 200:
        try:
            pages_text = _extract_pdfplumber(path, max_pages)
        except Exception:
            pass

    for i, t in enumerate(pages_text):
        if t.strip():
            yield TextChunk(text=t, locator=f"page={i + 1}/{total}")
