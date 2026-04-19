"""Экстракция Parquet (батчами через pyarrow)."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ..types import TextChunk

_BATCH = 25_000


def extract(path: Path) -> Iterable[TextChunk]:
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(path)
    schema = pf.schema_arrow
    columns = [field.name for field in schema]

    chunk_index = 0
    for batch in pf.iter_batches(batch_size=_BATCH):
        df = batch.to_pandas()
        body_lines: list[str] = [" ".join(columns)]
        for _, row in df.iterrows():
            body_lines.append("; ".join(f"{c}={v}" for c, v in row.items() if v is not None and v != ""))
        yield TextChunk(text="\n".join(body_lines), locator=f"batch={chunk_index}:rows={len(df)}")
        chunk_index += 1
