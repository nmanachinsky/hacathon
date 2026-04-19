"""Экстракция JSON / JSONL."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from ..types import TextChunk


def _stringify(obj, parent_key: str = "") -> Iterable[str]:
    """Рекурсивный обход JSON: возвращает «key=value» для скалярных листьев."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{parent_key}.{k}" if parent_key else str(k)
            yield from _stringify(v, full_key)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            full_key = f"{parent_key}[{i}]"
            yield from _stringify(item, full_key)
    else:
        if obj is None or obj == "":
            return
        yield f"{parent_key}={obj}"


def extract(path: Path) -> Iterable[TextChunk]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return

    # JSONL?
    suffix = path.suffix.lower()
    if suffix in {".jsonl", ".ndjson"}:
        lines: list[str] = []
        for raw_line in text.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            lines.extend(_stringify(obj))
            if len(lines) >= 10_000:
                yield TextChunk(text="\n".join(lines), locator="jsonl_batch")
                lines.clear()
        if lines:
            yield TextChunk(text="\n".join(lines), locator="jsonl_batch")
        return

    # Обычный JSON
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        # Просто отдаём как текст
        yield TextChunk(text=text, locator="raw_json")
        return

    pieces = list(_stringify(obj))
    yield TextChunk(text="\n".join(pieces), locator="json_root")
