"""Выбор и запуск нужного экстрактора по семейству."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ..config import OCRCfg
from ..discovery.router import guess_kind
from ..types import TextChunk
from . import csv_ext, doc, docx, html, image, json_ext, parquet_ext, pdf, rtf, text, video, xls
from .base import ExtractorError


_HTML_MAGIC_PREFIXES = (b"<!doc", b"<html", b"<?xml", b"<!--", b"<head")


def _sniff_actual_kind(path: Path, declared_kind: str) -> str:
    """Распознать файлы, которые имеют расширение PDF/DOC/etc., но реально — HTML/XML.

    Многие выгрузки сохраняют веб-страницы под расширением .pdf — pypdf падает на них с
    "invalid pdf header: b'<!DOC'". Определяем по magic-байтам и подменяем kind.
    """
    if declared_kind not in {"pdf", "doc", "docx", "rtf"}:
        return declared_kind
    try:
        with path.open("rb") as f:
            head = f.read(512)
    except OSError:
        return declared_kind
    head_strip = head.lstrip().lower()
    if any(head_strip.startswith(p) for p in _HTML_MAGIC_PREFIXES):
        return "html"
    return declared_kind


def extract_text(
    path: Path,
    *,
    ocr_cfg: OCRCfg,
    max_pdf_pages: int = 500,
) -> Iterable[TextChunk]:
    kind = guess_kind(path)
    if kind is None:
        raise ExtractorError(f"unsupported format: {path.suffix}")
    kind = _sniff_actual_kind(path, kind)

    if kind == "text":
        yield from text.extract(path)
        return
    if kind == "html":
        yield from html.extract(path)
        return
    if kind == "csv":
        yield from csv_ext.extract(path)
        return
    if kind == "json":
        yield from json_ext.extract(path)
        return
    if kind == "parquet":
        yield from parquet_ext.extract(path)
        return
    if kind == "docx":
        yield from docx.extract(path)
        return
    if kind == "doc":
        yield from doc.extract(path)
        return
    if kind == "rtf":
        yield from rtf.extract(path)
        return
    if kind in ("xls", "xlsx"):
        yield from xls.extract(path)
        return
    if kind == "pdf":
        chunks = list(pdf.extract(path, max_pages=max_pdf_pages))
        total_text = sum(len(c.text) for c in chunks)
        # Если PDF не дал текста — пробуем OCR (если разрешено)
        if total_text < 100 and ocr_cfg.mode in ("auto", "always"):
            yield from _ocr_pdf(path, ocr_cfg)
            return
        yield from chunks
        if ocr_cfg.mode == "always":
            yield from _ocr_pdf(path, ocr_cfg)
        return
    if kind == "image":
        if ocr_cfg.mode == "off":
            return
        yield from image.extract(
            path,
            enabled=True,
            languages=ocr_cfg.languages,
            min_side_px=ocr_cfg.min_side_px,
        )
        return
    if kind == "video":
        if ocr_cfg.mode == "off":
            return
        yield from video.extract(
            path,
            enabled=True,
            languages=ocr_cfg.languages,
        )
        return
    raise ExtractorError(f"unhandled kind: {kind}")


def _ocr_pdf(path: Path, ocr_cfg: OCRCfg) -> Iterable[TextChunk]:
    """OCR-фолбэк для отсканированных PDF (требует pdf2image + tesseract)."""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        return
    import shutil

    if not shutil.which("tesseract"):
        return
    try:
        images = convert_from_path(str(path), dpi=200, fmt="jpeg", thread_count=1)
    except Exception:
        return

    from .image import _ocr_with_tesseract  # type: ignore[attr-defined]

    for i, img in enumerate(images):
        try:
            import io

            import pytesseract

            text_str = pytesseract.image_to_string(img, lang="+".join(ocr_cfg.languages))
        except Exception:
            text_str = ""
        if text_str and text_str.strip():
            yield TextChunk(text=text_str, locator=f"ocr_page={i + 1}")
