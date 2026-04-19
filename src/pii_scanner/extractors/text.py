"""Экстрактор простого текста с авто-определением кодировки."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import chardet

from ..types import TextChunk


def extract(path: Path) -> Iterable[TextChunk]:
    raw = path.read_bytes()
    if not raw:
        return
    encoding = "utf-8"
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        guess = chardet.detect(raw[:65536])
        encoding = guess.get("encoding") or "cp1251"
    text = raw.decode(encoding, errors="replace")
    yield TextChunk(text=text, locator="full")
