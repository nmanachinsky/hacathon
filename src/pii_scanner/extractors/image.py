"""Извлечение текста из изображений через OCR (опциональный модуль)."""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from ..types import TextChunk

_MIN_SIDE_PX = 50       # Миниатюры без читаемого текста — пропускаем
_MAX_UPSCALE_SIDE = 2400  # Выше этого порога upscale только увеличит время OCR без пользы
_MAX_OCR_CHARS = 50_000   # Ограничиваем объём выхода Tesseract


@lru_cache(maxsize=1)
def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


@lru_cache(maxsize=1)
def _cv2_available() -> bool:
    try:
        __import__("cv2")
        return True
    except ImportError:
        return False


def _preprocess(img, min_upscale_side: int = 800):
    """Нормализация перед OCR: upscale если нужно + бинаризация."""
    from PIL import Image

    w, h = img.size
    min_side = min(w, h)

    if min_side < _MIN_SIDE_PX:
        return None  # Слишком мало — текста там нет

    if min_side < min_upscale_side:
        scale = 2.0
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    # Для изображений с min_side >= _MAX_UPSCALE_SIDE upscale пропускаем:
    # он только увеличил бы время OCR без прироста качества

    if _cv2_available():
        import cv2
        import numpy as np
        img_cv = np.array(img.convert("L"))
        img_cv = cv2.medianBlur(img_cv, 3)
        _, thresh = cv2.threshold(img_cv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        img = Image.fromarray(thresh)
    else:
        img = img.convert("L").point(lambda x: 0 if x < 140 else 255, "1")

    return img


def _ocr_with_tesseract(path: Path, languages: list[str], min_side_px: int = 800) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""

    try:
        with Image.open(path) as img:
            img.load()

            processed = _preprocess(img, min_upscale_side=min_side_px)
            if processed is None:
                return ""

            # oem 1 = LSTM only: быстрее oem 3 (legacy+LSTM), качество не хуже для RU текста
            custom_config = r"--oem 1 --psm 6"
            result = pytesseract.image_to_string(
                processed, lang="+".join(languages), config=custom_config
            )
            return result[:_MAX_OCR_CHARS]
    except Exception:
        return ""


def extract(
    path: Path,
    *,
    enabled: bool = True,
    languages: list[str] | None = None,
    min_side_px: int = 200,
) -> Iterable[TextChunk]:
    if not enabled or not _tesseract_available():
        return
    languages = languages or ["rus", "eng"]
    text = _ocr_with_tesseract(path, languages, min_side_px=min_side_px)
    if text and text.strip():
        yield TextChunk(text=text, locator="ocr")
