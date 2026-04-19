"""Платёжные данные: банковские карты, счета, БИК, CVV."""

from __future__ import annotations

from collections.abc import Iterable

from ..types import PIICategory
from .base import RawMatch
from .context_scorer import context_window
from .patterns import (
    BANK_ACCOUNT_CONTEXT_RE,
    BANK_ACCOUNT_RE,
    BANK_CARD_RE,
    BIK_CONTEXT_RE,
    BIK_RE,
    CVV_CONTEXT_RE,
    CVV_RE,
)
from .validators import account_check, bik_check, luhn_check


def detect_bank_cards(text: str) -> Iterable[RawMatch]:
    for m in BANK_CARD_RE.finditer(text):
        value = m.group(0)
        if not luhn_check(value):
            continue
        yield RawMatch(
            category=PIICategory.BANK_CARD,
            value=value,
            start=m.start(),
            end=m.end(),
            confidence=0.95,
        )


def detect_bik(text: str) -> Iterable[RawMatch]:
    for m in BIK_RE.finditer(text):
        value = m.group(0)
        if not bik_check(value):
            continue
        ctx = context_window(text, m.start(), m.end(), 40)
        if not BIK_CONTEXT_RE.search(ctx):
            continue
        yield RawMatch(
            category=PIICategory.BIK,
            value=value,
            start=m.start(),
            end=m.end(),
            confidence=0.9,
        )


def detect_bank_accounts(text: str) -> Iterable[RawMatch]:
    """Найти 20-значные счета. Если рядом есть БИК — валидируем контрольный разряд."""
    biks = [m.group(0) for m in BIK_RE.finditer(text) if bik_check(m.group(0))]
    for m in BANK_ACCOUNT_RE.finditer(text):
        value = m.group(0)
        ctx = context_window(text, m.start(), m.end(), 80)
        has_ctx = bool(BANK_ACCOUNT_CONTEXT_RE.search(ctx))
        validated = any(account_check(value, b) for b in biks)
        if not (has_ctx or validated):
            continue
        yield RawMatch(
            category=PIICategory.BANK_ACCOUNT,
            value=value,
            start=m.start(),
            end=m.end(),
            confidence=0.95 if validated else 0.75,
        )


def detect_cvv(text: str) -> Iterable[RawMatch]:
    """CVV ищем только когда явно упомянут код безопасности рядом."""
    for ctx_match in CVV_CONTEXT_RE.finditer(text):
        # Ищем 3-4 цифры в окне 30 символов после ключевого слова
        window_end = min(len(text), ctx_match.end() + 30)
        window = text[ctx_match.end():window_end]
        for m in CVV_RE.finditer(window):
            yield RawMatch(
                category=PIICategory.CVV,
                value=m.group(0),
                start=ctx_match.end() + m.start(),
                end=ctx_match.end() + m.end(),
                confidence=0.8,
            )
