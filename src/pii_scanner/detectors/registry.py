"""Реестр всех детекторов и единая точка вызова detect_all."""

from __future__ import annotations

from collections.abc import Iterable

from .base import RawMatch
from .contacts import detect_emails, detect_phones
from .context_scorer import boost_confidence, context_window
from .direct import detect_direct_markers
from .payment import detect_bank_accounts, detect_bank_cards, detect_bik, detect_cvv
from .personal import detect_addresses, detect_birth_dates, detect_birth_place, detect_fio_regex
from .sensitive import (
    detect_biometric,
    detect_health,
    detect_politics,
    detect_race,
    detect_religion,
)
from .state_id import (
    detect_driver_license,
    detect_inn,
    detect_mrz,
    detect_ogrn,
    detect_passports,
    detect_snils,
)


def _all_detectors():
    return (
        detect_direct_markers,  # Прямые маркеры из таблиц/JSON (наивысший приоритет)
        detect_emails,
        detect_phones,
        detect_passports,
        detect_snils,
        detect_inn,
        detect_ogrn,
        detect_driver_license,
        detect_mrz,
        detect_bank_cards,
        detect_bik,
        detect_bank_accounts,
        detect_cvv,
        detect_fio_regex,
        detect_birth_dates,
        detect_birth_place,     # Место рождения
        detect_addresses,
        detect_biometric,
        detect_health,
        detect_religion,
        detect_politics,
        detect_race,
    )


def detect_all(
    text: str,
    *,
    use_ner: bool = False,
    ner_max_chars: int = 50_000,
    context_radius: int = 60,
    min_confidence: float = 0.0,
) -> Iterable[RawMatch]:
    """Запустить все детекторы и применить контекстный скоринг."""
    if not text:
        return

    seen: set[tuple[str, int, int]] = set()

    for detector in _all_detectors():
        for raw in detector(text):
            key = (raw.category.value, raw.start, raw.end)
            if key in seen:
                continue
            seen.add(key)
            ctx = context_window(text, raw.start, raw.end, context_radius)
            boosted = boost_confidence(raw.category.value, raw.confidence, ctx)
            if boosted < min_confidence:
                continue
            yield RawMatch(
                category=raw.category,
                value=raw.value,
                start=raw.start,
                end=raw.end,
                confidence=boosted,
            )

    if use_ner:
        from .ner import detect_ner

        for raw in detect_ner(text, max_chars=ner_max_chars):
            key = (raw.category.value, raw.start, raw.end)
            if key in seen:
                continue
            seen.add(key)
            if raw.confidence >= min_confidence:
                yield raw
