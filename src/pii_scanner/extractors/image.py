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
            
            # Адаптивный upscale для сканов низкого разрешения
            if min(img.size) < 800:
                scale = 2.0
                img = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
            
            # Попытка бинаризации Оцу через cv2 (сильно улучшает читаемость сканов и водяных знаков)
            try:
                import cv2
                import numpy as np
                img_cv = np.array(img.convert("L"))
                # Медианный блюр убирает мелкий шум (пыль сканера)
                img_cv = cv2.medianBlur(img_cv, 3)
                _, thresh = cv2.threshold(img_cv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                img = Image.fromarray(thresh)
            except ImportError:
                # Фолбэк на базовую бинаризацию PIL
                img = img.convert("L").point(lambda x: 0 if x < 140 else 255, "1")
                
            # psm 6: Assume a single uniform block of text. Спасает структуру документа.
            custom_config = r'--oem 3 --psm 6'
            return pytesseract.image_to_string(img, lang="+".join(languages), config=custom_config)
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
