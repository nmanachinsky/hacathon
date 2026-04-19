"""Хелперы для анализа структурированных данных."""

from __future__ import annotations

import re

from ..types import PIICategory

# Эвристики для названий колонок
COLUMN_TO_CATEGORY = {
    PIICategory.EMAIL: re.compile(r"^(e[._-]?mail|почта)$", re.IGNORECASE),
    PIICategory.PHONE: re.compile(r"^(phone|tel|телефон|моб|сотов)", re.IGNORECASE),
    PIICategory.FIO: re.compile(r"^(fio|fullname|full_name|фио|name|surname|фамил|patronymic|отчеств)", re.IGNORECASE),
    PIICategory.PASSPORT_RF: re.compile(r"^(passport|паспорт|документ)", re.IGNORECASE),
    PIICategory.SNILS: re.compile(r"^(snils|снилс|pension)", re.IGNORECASE),
    PIICategory.INN_PERSONAL: re.compile(r"^(inn|инн|tax)", re.IGNORECASE),
    PIICategory.BIRTH_DATE: re.compile(r"(birth|др|dob|рожден|birthday)", re.IGNORECASE),
    PIICategory.ADDRESS: re.compile(r"^(address|адрес|город|city|страна|регион|region)", re.IGNORECASE),
    PIICategory.BANK_CARD: re.compile(r"(card|карт|pan)", re.IGNORECASE),
    PIICategory.BANK_ACCOUNT: re.compile(r"(account|счет|р/с)", re.IGNORECASE),
}

def guess_column_category(col_name: str) -> PIICategory | None:
    for cat, pattern in COLUMN_TO_CATEGORY.items():
        if pattern.search(col_name):
            return cat
    return None