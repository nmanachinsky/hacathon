"""Нормализация текста перед детекцией."""

from __future__ import annotations

import re
import unicodedata

_WS_RE = re.compile(r"[ \t\u00a0\u200b\u2009]+")
_NL_RE = re.compile(r"\r\n?|\u2028|\u2029")


def normalize_text(text: str) -> str:
    """Нормализовать текст: NFKC, ё→е (мягко), сжать пробелы.

    Возвращает текст той же длины (где возможно), чтобы оффсеты совпадали.
    """
    if not text:
        return ""
    # Нормализация совместимости: '①' → '1', полноширинные → обычные.
    text = unicodedata.normalize("NFKC", text)
    text = _NL_RE.sub("\n", text)
    return text


def collapse_whitespace(text: str) -> str:
    """Сжать пробельные символы для контекстных сравнений (теряет оффсеты)."""
    text = _WS_RE.sub(" ", text)
    return text.strip()


def strip_diacritics(text: str) -> str:
    """Убрать диакритику (для словарных сравнений)."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def lower_yo_to_ye(text: str) -> str:
    """Заменить ё/Ё на е/Е (для сравнений)."""
    return text.replace("ё", "е").replace("Ё", "Е")
