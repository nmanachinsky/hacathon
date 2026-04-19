"""Государственные идентификаторы: паспорт, СНИЛС, ИНН, ВУ, MRZ, ОГРН."""

from __future__ import annotations

from collections.abc import Iterable

from ..types import PIICategory
from .base import RawMatch
from .context_scorer import context_window
from .patterns import (
    DRIVER_LICENSE_CONTEXT_RE,
    DRIVER_LICENSE_RE,
    INN_CONTEXT_RE,
    INN_RE,
    OGRN_CONTEXT_RE,
    OGRN_RE,
    PASSPORT_CONTEXT_RE,
    PASSPORT_RF_RE,
    SNILS_CONTEXT_RE,
    SNILS_RE,
)
from .validators import (
    inn_check,
    is_mrz_line,
    mrz_block_valid,
    ogrn_check,
    snils_check,
)


def detect_passports(text: str) -> Iterable[RawMatch]:
    for m in PASSPORT_RF_RE.finditer(text):
        ctx = context_window(text, m.start(), m.end(), 80)
        if not PASSPORT_CONTEXT_RE.search(ctx):
            # Без контекста — слишком много ложных срабатываний (любые 4+6 цифр)
            continue
        yield RawMatch(
            category=PIICategory.PASSPORT_RF,
            value=m.group(0),
            start=m.start(),
            end=m.end(),
            confidence=0.85,
        )


def detect_snils(text: str) -> Iterable[RawMatch]:
    for m in SNILS_RE.finditer(text):
        value = m.group(0)
        valid = snils_check(value)
        ctx = context_window(text, m.start(), m.end(), 60)
        has_ctx = bool(SNILS_CONTEXT_RE.search(ctx))
        if not valid and not has_ctx:
            continue
        if valid and has_ctx:
            confidence = 0.98
        elif valid:
            confidence = 0.85
        else:
            confidence = 0.7
        yield RawMatch(
            category=PIICategory.SNILS,
            value=value,
            start=m.start(),
            end=m.end(),
            confidence=confidence,
        )


def detect_inn(text: str) -> Iterable[RawMatch]:
    for m in INN_RE.finditer(text):
        value = m.group(0)
        valid_checksum = inn_check(value)
        ctx = context_window(text, m.start(), m.end(), 60)
        has_ctx = bool(INN_CONTEXT_RE.search(ctx))
        # Без валидной чек-суммы и без контекста — отбрасываем (слишком много шума: ID, телефоны без +7)
        if not valid_checksum and not has_ctx:
            continue
        category = PIICategory.INN_PERSONAL if len(value) == 12 else PIICategory.INN_LEGAL
        if valid_checksum and has_ctx:
            confidence = 0.98
        elif valid_checksum:
            confidence = 0.8
        else:
            # Контекст подтверждает ИНН, но чек-сумма не сходится (синтетика).
            confidence = 0.7
        yield RawMatch(
            category=category,
            value=value,
            start=m.start(),
            end=m.end(),
            confidence=confidence,
        )


def detect_ogrn(text: str) -> Iterable[RawMatch]:
    for m in OGRN_RE.finditer(text):
        value = m.group(0)
        if not ogrn_check(value):
            continue
        ctx = context_window(text, m.start(), m.end(), 60)
        if not OGRN_CONTEXT_RE.search(ctx):
            continue
        yield RawMatch(
            category=PIICategory.OGRN,
            value=value,
            start=m.start(),
            end=m.end(),
            confidence=0.9,
        )


def detect_driver_license(text: str) -> Iterable[RawMatch]:
    for m in DRIVER_LICENSE_RE.finditer(text):
        ctx = context_window(text, m.start(), m.end(), 60)
        if not DRIVER_LICENSE_CONTEXT_RE.search(ctx):
            continue
        yield RawMatch(
            category=PIICategory.DRIVER_LICENSE,
            value=m.group(0),
            start=m.start(),
            end=m.end(),
            confidence=0.8,
        )


def detect_mrz(text: str) -> Iterable[RawMatch]:
    """MRZ ищем построчно: блок из 2-3 валидных строк."""
    lines = text.splitlines(keepends=True)
    offsets: list[int] = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line)

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n\r")
        if not is_mrz_line(line):
            i += 1
            continue
        block: list[str] = [line]
        j = i + 1
        while j < len(lines) and j - i < 3 and is_mrz_line(lines[j].rstrip("\n\r")):
            block.append(lines[j].rstrip("\n\r"))
            j += 1
        if len(block) >= 2 and mrz_block_valid(block):
            start = offsets[i]
            end = offsets[i] + sum(len(line) + 1 for line in block)
            yield RawMatch(
                category=PIICategory.MRZ,
                value="\n".join(block),
                start=start,
                end=min(end, len(text)),
                confidence=0.95,
            )
        i = j if len(block) > 1 else i + 1
