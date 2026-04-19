"""Видео → ключевые кадры → OCR (опционально)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path

from ..types import TextChunk


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def extract(
    path: Path,
    *,
    enabled: bool = True,
    languages: list[str] | None = None,
    every_seconds: float = 5.0,
    max_frames: int = 5,
) -> Iterable[TextChunk]:
    if not enabled or not _ffmpeg_available():
        return

    from .image import _ocr_with_tesseract  # type: ignore[attr-defined]

    languages = languages or ["rus", "eng"]
    with tempfile.TemporaryDirectory() as tmpdir:
        out_pattern = str(Path(tmpdir) / "frame_%04d.jpg")
        cmd = [
            "ffmpeg", "-loglevel", "error", "-y",
            "-i", str(path),
            "-vf", f"fps=1/{every_seconds}",
            "-frames:v", str(max_frames),
            out_pattern,
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=180)
        except (subprocess.SubprocessError, OSError):
            return

        for i, frame in enumerate(sorted(Path(tmpdir).glob("frame_*.jpg"))):
            text = _ocr_with_tesseract(frame, languages)
            if text and text.strip():
                yield TextChunk(text=text, locator=f"frame={i + 1}")
