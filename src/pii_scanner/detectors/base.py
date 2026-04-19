"""Базовые типы для детекторов."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from ..types import PIICategory


@dataclass(frozen=True, slots=True)
class RawMatch:
    """Сырой результат от детектора (до маскирования)."""

    category: PIICategory
    value: str
    start: int
    end: int
    confidence: float


class Detector(Protocol):
    """Протокол детектора. Принимает текст, возвращает поток сырых матчей."""

    def detect(self, text: str) -> Iterable[RawMatch]: ...
