"""Биометрия и специальные категории ПДн."""

from __future__ import annotations

from collections.abc import Iterable

from ..types import PIICategory
from .base import RawMatch
from .patterns import (
    BIOMETRIC_TERMS_RE,
    HEALTH_TERMS_RE,
    POLITICS_TERMS_RE,
    RACE_TERMS_RE,
    RELIGION_TERMS_RE,
)


def detect_biometric(text: str) -> Iterable[RawMatch]:
    for m in BIOMETRIC_TERMS_RE.finditer(text):
        yield RawMatch(
            category=PIICategory.BIOMETRIC,
            value=m.group(0),
            start=m.start(),
            end=m.end(),
            confidence=0.85,
        )


def detect_health(text: str) -> Iterable[RawMatch]:
    for m in HEALTH_TERMS_RE.finditer(text):
        yield RawMatch(
            category=PIICategory.HEALTH,
            value=m.group(0),
            start=m.start(),
            end=m.end(),
            confidence=0.8,
        )


def detect_religion(text: str) -> Iterable[RawMatch]:
    for m in RELIGION_TERMS_RE.finditer(text):
        yield RawMatch(
            category=PIICategory.RELIGION,
            value=m.group(0),
            start=m.start(),
            end=m.end(),
            confidence=0.75,
        )


def detect_politics(text: str) -> Iterable[RawMatch]:
    for m in POLITICS_TERMS_RE.finditer(text):
        yield RawMatch(
            category=PIICategory.POLITICS,
            value=m.group(0),
            start=m.start(),
            end=m.end(),
            confidence=0.75,
        )


def detect_race(text: str) -> Iterable[RawMatch]:
    for m in RACE_TERMS_RE.finditer(text):
        yield RawMatch(
            category=PIICategory.RACE,
            value=m.group(0),
            start=m.start(),
            end=m.end(),
            confidence=0.75,
        )
