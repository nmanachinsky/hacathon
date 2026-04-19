"""Роутинг файлов на подходящие экстракторы по расширению / mime."""

from __future__ import annotations

import mimetypes
from pathlib import Path

# Унифицированные имена «семейств» экстракторов
ExtractorKind = str

# Карта расширений → семейство экстрактора
EXT_MAP: dict[str, ExtractorKind] = {
    # plain text
    ".txt": "text",
    ".md": "text",
    ".log": "text",
    # web
    ".html": "html",
    ".htm": "html",
    ".xhtml": "html",
    # office
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "doc",
    ".rtf": "rtf",
    ".xlsx": "xlsx",
    ".xls": "xls",
    # structured
    ".csv": "csv",
    ".tsv": "csv",
    ".json": "json",
    ".jsonl": "json",
    ".ndjson": "json",
    ".parquet": "parquet",
    # images → OCR
    ".tif": "image",
    ".tiff": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".gif": "image",
    ".bmp": "image",
    ".webp": "image",
    # video → keyframes + OCR
    ".mp4": "video",
    ".mov": "video",
    ".avi": "video",
    ".mkv": "video",
}


def guess_kind(path: Path) -> ExtractorKind | None:
    """Определить семейство экстрактора по расширению / mime.

    Возвращает None, если формат не поддерживается.
    """
    ext = path.suffix.lower()
    if ext in EXT_MAP:
        return EXT_MAP[ext]

    mime, _ = mimetypes.guess_type(str(path))
    if not mime:
        return None
    if mime.startswith("text/html"):
        return "html"
    if mime.startswith("text/csv"):
        return "csv"
    if mime.startswith("text/"):
        return "text"
    if mime == "application/pdf":
        return "pdf"
    if mime == "application/json":
        return "json"
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    return None


def guess_mime(path: Path) -> str:
    """Грубое значение mime для отчёта."""
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"
