"""Контекстный скоринг: близость ключевых слов меняет confidence находки."""

from __future__ import annotations

import re

# Карта: категория → паттерны позитивного контекста (повышают confidence)
POSITIVE_CONTEXT: dict[str, re.Pattern[str]] = {
    "passport_rf": re.compile(
        r"паспорт|серии?\s+\d|серия\s+(?:и\s+)?номер|документ,?\s+удостоверяющ|удостоверение\s+личности",
        re.IGNORECASE,
    ),
    "snils": re.compile(r"снилс|пенсионн|страхов(?:ой|ое)\s+свидет", re.IGNORECASE),
    "inn_personal": re.compile(r"инн|идентификационн", re.IGNORECASE),
    "inn_legal": re.compile(r"инн|кпп|идентификационн", re.IGNORECASE),
    "driver_license": re.compile(r"водит\w+|вод\.?\s*удост|ву\b|driver", re.IGNORECASE),
    "bank_card": re.compile(r"карт\w+|card|visa|mastercard|мир\b", re.IGNORECASE),
    "bank_account": re.compile(r"счет|счёт|расч[её]тн|р/с|account|iban", re.IGNORECASE),
    "bik": re.compile(r"бик\b|bik\b", re.IGNORECASE),
    "cvv": re.compile(r"cvv|cvc|код\s+безопасн", re.IGNORECASE),
    "ogrn": re.compile(r"огрн", re.IGNORECASE),
    "phone": re.compile(r"тел\.?|телеф|phone|моб\.?|mobile|конт\w+\s+тел", re.IGNORECASE),
    "email": re.compile(r"e[\-\s]?mail|почт|эл\.?\s*адрес", re.IGNORECASE),
    "birth_date": re.compile(r"д\.?\s*р\.?|год\s+рожд|г\.?\s*р\.?|рожден|date\s+of\s+birth|dob", re.IGNORECASE),
    "fio": re.compile(r"ф\.?\s*и\.?\s*о\.?|фамилия|имя|отчеств", re.IGNORECASE),
    "address": re.compile(r"адрес|регистрац|прописк|жительств", re.IGNORECASE),
}


def context_window(text: str, start: int, end: int, radius: int) -> str:
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    return text[lo:hi]


def boost_confidence(category_value: str, base: float, ctx: str) -> float:
    """Скорректировать confidence по контексту."""
    pat = POSITIVE_CONTEXT.get(category_value)
    if pat and pat.search(ctx):
        return min(1.0, base + 0.25)
    return base
