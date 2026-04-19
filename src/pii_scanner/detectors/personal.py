"""ФИО, дата/место рождения, адрес."""

from __future__ import annotations

from collections.abc import Iterable

from ..types import PIICategory
from .base import RawMatch
from .patterns import (
    ADDRESS_RE,
    BIRTH_CONTEXT_RE,
    BIRTH_DATE_RE,
    FIO_INITIALS_RE,
    FIO_RE,
    POSTAL_INDEX_RE,
)


def detect_fio_regex(text: str) -> Iterable[RawMatch]:
    """Поиск ФИО регулярным выражением (быстро, без NER).

    NER даёт более точные результаты, но также сильно увеличивает время.
    Этот детектор работает по-русски и неплохо для триплетов «Имя Отчество Фамилия».
    """
    for m in FIO_RE.finditer(text):
        yield RawMatch(
            category=PIICategory.FIO,
            value=m.group(0),
            start=m.start(),
            end=m.end(),
            confidence=0.7,
        )
    for m in FIO_INITIALS_RE.finditer(text):
        yield RawMatch(
            category=PIICategory.FIO,
            value=m.group(0),
            start=m.start(),
            end=m.end(),
            confidence=0.7,
        )


def detect_birth_dates(text: str) -> Iterable[RawMatch]:
    for m in BIRTH_DATE_RE.finditer(text):
        # Контекст «г.р.», «рождения» сильно повышает уверенность; иначе — это просто дата
        from .context_scorer import context_window

        ctx = context_window(text, m.start(), m.end(), 40)
        if not BIRTH_CONTEXT_RE.search(ctx):
            # Низкая уверенность — оставим как кандидата, чтобы не пропустить
            confidence = 0.4
        else:
            confidence = 0.9
        yield RawMatch(
            category=PIICategory.BIRTH_DATE,
            value=m.group(0),
            start=m.start(),
            end=m.end(),
            confidence=confidence,
        )


def detect_addresses(text: str) -> Iterable[RawMatch]:
    seen_spans: set[tuple[int, int]] = set()
    for m in ADDRESS_RE.finditer(text):
        if (m.start(), m.end()) in seen_spans:
            continue
        seen_spans.add((m.start(), m.end()))
        yield RawMatch(
            category=PIICategory.ADDRESS,
            value=m.group(0).strip(),
            start=m.start(),
            end=m.end(),
            confidence=0.7,
        )
    # Почтовый индекс рядом со словом «адрес»
    for m in POSTAL_INDEX_RE.finditer(text):
        from .context_scorer import context_window

        ctx = context_window(text, m.start(), m.end(), 40).lower()
        if "адрес" in ctx or "регистр" in ctx or "г." in ctx or "город" in ctx:
            yield RawMatch(
                category=PIICategory.ADDRESS,
                value=m.group(0),
                start=m.start(),
                end=m.end(),
                confidence=0.6,
            )
