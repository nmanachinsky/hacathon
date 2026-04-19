"""Экстракция JSON / JSONL."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from ..types import TextChunk

_MAX_JSON_BYTES = 10 * 1024 * 1024   # 10 MB — хвост больших JSON-дампов не несёт новых ПДн
_MAX_JSONL_LINES = 10_000             # Достаточно строк для надёжного обнаружения ПДн


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
    # Большие файлы читаем с ограничением — PII обычно в первых записях
    size = path.stat().st_size
    if size > _MAX_JSON_BYTES:
        raw = path.read_bytes()[:_MAX_JSON_BYTES]
        text = raw.decode("utf-8", errors="replace")
    else:
        text = path.read_text(encoding="utf-8", errors="replace")

    if not text.strip():
        return

    # JSONL?
    suffix = path.suffix.lower()
    if suffix in {".jsonl", ".ndjson"}:
        lines: list[str] = []
        lines_seen = 0
        for raw_line in text.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            if lines_seen >= _MAX_JSONL_LINES:
                break
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            lines.extend(_stringify(obj))
            lines_seen += 1
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
        yield TextChunk(text=text, locator="raw_json")
        return

    pieces = list(_stringify(obj))
    yield TextChunk(text="\n".join(pieces), locator="json_root")
