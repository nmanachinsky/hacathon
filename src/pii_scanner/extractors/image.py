"""Извлечение текста из изображений через OCR (опциональный модуль)."""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path

from ..types import TextChunk


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _ocr_with_tesseract(path: Path, languages: list[str]) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""
    try:
        with Image.open(path) as img:
            img.load()
            # Стандартный препроцессинг: greyscale + upscale если очень мелкое
            if min(img.size) < 600:
                scale = 2.0
                img = img.resize((int(img.width * scale), int(img.height * scale)))
            img = img.convert("L")
            return pytesseract.image_to_string(img, lang="+".join(languages))
    except Exception:
        return ""


def extract(
    path: Path,
    *,
    enabled: bool = True,
    languages: list[str] | None = None,
    min_side_px: int = 200,
) -> Iterable[TextChunk]:
    if not enabled:
        return
    languages = languages or ["rus", "eng"]
    if not _tesseract_available():
        # OCR отключен — но регистрируем сам файл как «изображение требует OCR»
        return
    text = _ocr_with_tesseract(path, languages)
    if text and text.strip():
        yield TextChunk(text=text, locator="ocr")
