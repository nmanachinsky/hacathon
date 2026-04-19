"""Экстракция Parquet (только первые строки для быстрого сэмплирования)."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ..types import TextChunk

# Для определения наличия ПДн достаточно первых строк — не читаем весь файл
_MAX_ROWS = 1_000


def extract(path: Path) -> Iterable[TextChunk]:
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(path)
    columns = [field.name for field in pf.schema_arrow]

    # Читаем только первый батч — break после него
    for batch in pf.iter_batches(batch_size=_MAX_ROWS):
        df = batch.to_pandas()
        break
    else:
        return

    body_lines: list[str] = [" ".join(columns)]
    # to_dict('records') ~10x быстрее iterrows(): нет создания Series на строку
    for record in df.to_dict("records"):
        row_str = "; ".join(f"{c}={v}" for c, v in record.items() if v is not None and str(v) != "")
        if row_str:
            body_lines.append(row_str)

    yield TextChunk(text="\n".join(body_lines), locator=f"batch=0:rows={len(df)}")
