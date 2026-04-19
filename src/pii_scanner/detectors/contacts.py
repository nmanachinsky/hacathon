"""Детекторы контактных данных: телефон, email."""

from __future__ import annotations

from collections.abc import Iterable

from ..types import PIICategory
from .base import RawMatch
from .patterns import EMAIL_RE, PHONE_RE


def detect_emails(text: str) -> Iterable[RawMatch]:
    for m in EMAIL_RE.finditer(text):
        yield RawMatch(
            category=PIICategory.EMAIL,
            value=m.group(0),
            start=m.start(),
            end=m.end(),
            confidence=0.95,
        )


def detect_phones(text: str) -> Iterable[RawMatch]:
    for m in PHONE_RE.finditer(text):
        yield RawMatch(
            category=PIICategory.PHONE,
            value=m.group(0),
            start=m.start(),
            end=m.end(),
            confidence=0.85,
        )
