"""Детектор 'прямых' ПДн (извлечённых по заголовкам колонок CSV/Parquet)."""

from __future__ import annotations

import re
from collections.abc import Iterable

from ..types import PIICategory
from .base import RawMatch

# Паттерн, который генерируют экстракторы: [[PII_DIRECT:category_name:value]]
DIRECT_MARKER_RE = re.compile(r"\[\[PII_DIRECT:([^:]+):(.*?)\]\]")

def detect_direct_markers(text: str) -> Iterable[RawMatch]:
    """Извлекает ПДн, явно размеченные экстракторами (100% confidence)."""
    for m in DIRECT_MARKER_RE.finditer(text):
        cat_str = m.group(1)
        value = m.group(2).strip()
        if not value:
            continue
        try:
            category = PIICategory(cat_str)
            yield RawMatch(
                category=category,
                value=value,
                start=m.start(),
                end=m.end(),
                confidence=1.0,  # Высший приоритет
            )
        except ValueError:
            continue