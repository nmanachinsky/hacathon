"""Базовая абстракция экстрактора."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from ..types import TextChunk


class Extractor(Protocol):
    def extract(self, path: Path) -> Iterable[TextChunk]: ...


class ExtractorError(RuntimeError):
    """Ошибка экстракции (битый файл, неподдерживаемая под-версия и т.п.)."""
