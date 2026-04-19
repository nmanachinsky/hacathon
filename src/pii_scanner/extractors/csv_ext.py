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
            path, sep=sep, chunksize=_CHUNK_ROWS, dtype=str,
            keep_default_na=False, on_bad_lines="skip", encoding_errors="replace", low_memory=False,
        )
    except Exception:
        reader = pd.read_csv(
            path, sep=sep, chunksize=_CHUNK_ROWS, dtype=str,
            keep_default_na=False, on_bad_lines="skip", encoding="cp1251", encoding_errors="replace", low_memory=False,
        )

    chunk_index = 0
    for df in reader:
        # Предварительно определяем категории колонок
        col_mappings = {col: guess_column_category(str(col)) for col in df.columns}
        
        header_text = " ".join(df.columns.astype(str))
        body_lines: list[str] = [header_text]
        
        for _, row in df.iterrows():
            parts =[]
            for col, val in row.items():
                if not val: continue
                cat = col_mappings.get(col)
                if cat:
                    # Вставляем прямой маркер: детектор поймает его на 100%
                    parts.append(f"[[PII_DIRECT:{cat.value}:{val}]]")
                else:
                    parts.append(f"{col}={val}")
            body_lines.append("; ".join(parts))
            
        yield TextChunk(text="\n".join(body_lines), locator=f"chunk={chunk_index}:rows={len(df)}")
        chunk_index += 1
