"""DOC (старый формат Word) → текст через antiword/textutil/libreoffice (по доступности)."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

from ..types import TextChunk


def _try_antiword(path: Path) -> str | None:
    if not shutil.which("antiword"):
        return None
    try:
        result = subprocess.run(
            ["antiword", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            errors="replace",
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except (subprocess.SubprocessError, OSError):
        return None
    return None


def _try_textutil(path: Path) -> str | None:
    """macOS-нативный конвертер."""
    if not shutil.which("textutil"):
        return None
    try:
        result = subprocess.run(
            ["textutil", "-convert", "txt", "-stdout", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            errors="replace",
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except (subprocess.SubprocessError, OSError):
        return None
    return None


def _try_soffice(path: Path) -> str | None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    try:
        # Конвертируем в текст рядом с файлом
        outdir = path.parent / ".soffice_tmp"
        outdir.mkdir(exist_ok=True)
        try:
            result = subprocess.run(
                [soffice, "--headless", "--convert-to", "txt", "--outdir", str(outdir), str(path)],
                capture_output=True,
                timeout=120,
            )
            txt_path = outdir / (path.stem + ".txt")
            if result.returncode == 0 and txt_path.exists():
                return txt_path.read_text(encoding="utf-8", errors="replace")
        finally:
            for f in outdir.glob("*"):
                f.unlink(missing_ok=True)
            outdir.rmdir()
    except (subprocess.SubprocessError, OSError):
        return None
    return None


def extract(path: Path) -> Iterable[TextChunk]:
    text = _try_antiword(path) or _try_textutil(path) or _try_soffice(path)
    if not text:
        # Последний фолбэк: тупо вытащить ASCII/CP1251 строки
        raw = path.read_bytes()
        text = raw.decode("cp1251", errors="ignore")
    if text:
        yield TextChunk(text=text, locator="doc_body")
