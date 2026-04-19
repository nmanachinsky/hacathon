"""Экстракция текста из HTML."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import chardet

from ..types import TextChunk

_MAX_HTML_BYTES = 5 * 1024 * 1024  # 5 MB — trafilatura сам отбирает основной контент


def extract(path: Path) -> Iterable[TextChunk]:
    raw = path.read_bytes()
    if not raw:
        return
    # Обрезаем гигантские HTML: хвост обычно — рекомендации/трекеры, не ПДн
    if len(raw) > _MAX_HTML_BYTES:
        raw = raw[:_MAX_HTML_BYTES]
    try:
        text_html = raw.decode("utf-8")
    except UnicodeDecodeError:
        encoding = chardet.detect(raw[:65536]).get("encoding") or "cp1251"
        text_html = raw.decode(encoding, errors="replace")

    # Сначала пробуем trafilatura — даёт «основной» контент
    try:
        import trafilatura

        extracted = trafilatura.extract(text_html, include_tables=True, include_links=False)
        if extracted:
            yield TextChunk(text=extracted, locator="trafilatura")
            return
    except Exception:
        pass

    # Фолбэк: selectolax — быстро снимает теги
    try:
        from selectolax.parser import HTMLParser

        tree = HTMLParser(text_html)
        for tag in tree.css("script, style, noscript"):
            tag.decompose()
        text = tree.body.text(separator=" ") if tree.body else tree.text(separator=" ")
        if text:
            yield TextChunk(text=text, locator="selectolax")
    except Exception:
        # последний фолбэк
        yield TextChunk(text=text_html, locator="raw_html")
