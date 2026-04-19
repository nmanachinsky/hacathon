"""Безопасное представление найденных значений."""

from __future__ import annotations

import hashlib
import re

from ..types import PIICategory


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def mask_value(value: str, category: PIICategory, mode: str = "partial") -> str:
    """Замаскировать значение по правилам категории.

    mode:
        full       — полностью скрыть длиной X
        partial    — оставить структурно значимые части
        hash_only  — только префикс хэша
    """
    value = value.strip()
    if mode == "hash_only":
        return f"sha256:{sha256_hex(value)[:12]}"
    if mode == "full":
        return "*" * min(len(value), 8)

    # partial — структурные правила по категориям
    if category == PIICategory.PHONE:
        digits = re.sub(r"\D", "", value)
        if len(digits) >= 10:
            return f"+{digits[0]} {digits[1:4]} ***-**-{digits[-2:]}"
    if category == PIICategory.EMAIL:
        if "@" in value:
            local, domain = value.split("@", 1)
            keep = local[:1]
            return f"{keep}{'*' * max(0, len(local) - 1)}@{domain}"
    if category == PIICategory.BANK_CARD:
        digits = re.sub(r"\D", "", value)
        if len(digits) >= 12:
            return f"{digits[:4]} **** **** {digits[-4:]}"
    if category == PIICategory.SNILS:
        d = re.sub(r"\D", "", value)
        if len(d) == 11:
            return f"{d[:3]}-***-*** {d[-2:]}"
    if category == PIICategory.PASSPORT_RF:
        d = re.sub(r"\D", "", value)
        if len(d) >= 6:
            return f"{d[:2]}** ****{d[-2:]}"
    if category in (PIICategory.INN_PERSONAL, PIICategory.INN_LEGAL):
        d = re.sub(r"\D", "", value)
        if len(d) >= 4:
            return f"{d[:2]}***{d[-2:]}"
    if category == PIICategory.BANK_ACCOUNT:
        d = re.sub(r"\D", "", value)
        if len(d) >= 6:
            return f"{d[:5]}***********{d[-4:]}"
    if category == PIICategory.BIK:
        d = re.sub(r"\D", "", value)
        if len(d) == 9:
            return f"{d[:4]}***{d[-2:]}"
    if category == PIICategory.CVV:
        return "***"
    if category == PIICategory.MRZ:
        return value[:3] + "***"
    if category == PIICategory.DRIVER_LICENSE:
        d = re.sub(r"\D", "", value)
        if len(d) >= 6:
            return f"{d[:2]}** ****{d[-2:]}"
    if category == PIICategory.FIO:
        parts = value.split()
        if parts:
            return " ".join(p[:1] + "." for p in parts)
    if category == PIICategory.ADDRESS:
        # Оставить первый токен (страна/индекс), остальное скрыть
        head = value.split(",")[0]
        return f"{head[:6]}…"
    if category == PIICategory.BIRTH_DATE:
        # YYYY/DD скрываем
        return "**.**.****"
    # дефолт
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]
