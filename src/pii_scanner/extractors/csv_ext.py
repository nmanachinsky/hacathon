"""Экстракция CSV/TSV — с потоковым чтением и батчами."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from ..types import TextChunk

_CHUNK_ROWS = 25_000


def _detect_separator(path: Path) -> str:
    with path.open("rb") as f:
        sample = f.read(8192).decode("utf-8", errors="replace")
    if path.suffix.lower() == ".tsv":
        return "\t"
    # Простая эвристика
    if sample.count(";") > sample.count(","):
        return ";"
    return ","


def extract(path: Path) -> Iterable[TextChunk]:
    sep = _detect_separator(path)
    try:
        reader = pd.read_csv(
            path,
            sep=sep,
            chunksize=_CHUNK_ROWS,
            dtype=str,
            keep_default_na=False,
            on_bad_lines="skip",
            encoding_errors="replace",
            low_memory=False,
        )
    except Exception:
        # Фолбэк: попробуем cp1251
        reader = pd.read_csv(
            path,
            sep=sep,
            chunksize=_CHUNK_ROWS,
            dtype=str,
            keep_default_na=False,
            on_bad_lines="skip",
            encoding="cp1251",
            encoding_errors="replace",
            low_memory=False,
        )

    chunk_index = 0
    for df in reader:
        # Заголовки превращаем в текст для контекстных детекторов
        header_text = " ".join(df.columns.astype(str))
        # Каждая строка → одна строка текста "col1=val1; col2=val2"
        # Это даёт контекст детекторам и резко поднимает точность
        body_lines: list[str] = [header_text]
        for _, row in df.iterrows():
            body_lines.append("; ".join(f"{c}={v}" for c, v in row.items() if v))
        text = "\n".join(body_lines)
        yield TextChunk(text=text, locator=f"chunk={chunk_index}:rows={len(df)}")
        chunk_index += 1
