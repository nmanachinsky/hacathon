"""RTF → текст."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from striprtf.striprtf import rtf_to_text

from ..types import TextChunk


def extract(path: Path) -> Iterable[TextChunk]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = rtf_to_text(raw, errors="ignore")
    if text:
        yield TextChunk(text=text, locator="rtf_body")
