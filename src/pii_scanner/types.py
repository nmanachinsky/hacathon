"""Базовые иммутабельные типы домена."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class PIICategory(str, Enum):
    """Категории ПДн согласно 152-ФЗ."""

    # Обычные ПДн
    FIO = "fio"
    PHONE = "phone"
    EMAIL = "email"
    BIRTH_DATE = "birth_date"
    BIRTH_PLACE = "birth_place"
    ADDRESS = "address"

    # Государственные идентификаторы
    PASSPORT_RF = "passport_rf"
    SNILS = "snils"
    INN_PERSONAL = "inn_personal"
    INN_LEGAL = "inn_legal"
    DRIVER_LICENSE = "driver_license"
    MRZ = "mrz"
    OGRN = "ogrn"

    # Платёжные данные
    BANK_CARD = "bank_card"
    BANK_ACCOUNT = "bank_account"
    BIK = "bik"
    CVV = "cvv"

    # Биометрия
    BIOMETRIC = "biometric"

    # Специальные категории
    HEALTH = "health"
    RELIGION = "religion"
    POLITICS = "politics"
    RACE = "race"
    OTHER_SENSITIVE = "other_sensitive"


# Группировка категорий для классификации УЗ
REGULAR_CATEGORIES = frozenset({
    PIICategory.FIO,
    PIICategory.PHONE,
    PIICategory.EMAIL,
    PIICategory.BIRTH_DATE,
    PIICategory.BIRTH_PLACE,
    PIICategory.ADDRESS,
})

STATE_ID_CATEGORIES = frozenset({
    PIICategory.PASSPORT_RF,
    PIICategory.SNILS,
    PIICategory.INN_PERSONAL,
    PIICategory.DRIVER_LICENSE,
    PIICategory.MRZ,
})

PAYMENT_CATEGORIES = frozenset({
    PIICategory.BANK_CARD,
    PIICategory.BANK_ACCOUNT,
    PIICategory.BIK,
    PIICategory.CVV,
})

BIOMETRIC_CATEGORIES = frozenset({PIICategory.BIOMETRIC})

SENSITIVE_CATEGORIES = frozenset({
    PIICategory.HEALTH,
    PIICategory.RELIGION,
    PIICategory.POLITICS,
    PIICategory.RACE,
    PIICategory.OTHER_SENSITIVE,
})


class ProtectionLevel(str, Enum):
    """Уровни защищённости информационной системы (152-ФЗ / ПП РФ № 1119)."""

    UZ_1 = "УЗ-1"
    UZ_2 = "УЗ-2"
    UZ_3 = "УЗ-3"
    UZ_4 = "УЗ-4"
    NONE = "Без ПДн"


@dataclass(frozen=True, slots=True)
class TextChunk:
    """Кусок извлечённого текста с источником."""

    text: str
    # Локатор источника внутри файла: "page=3", "sheet=Sheet1!A1", "row=42:col=email"
    locator: str = ""


@dataclass(frozen=True, slots=True)
class Finding:
    """Единичная находка ПДн."""

    category: PIICategory
    value_masked: str
    value_hash: str
    confidence: float
    locator: str = ""
    context: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence должен быть в [0, 1], получено {self.confidence}")


@dataclass(frozen=True, slots=True)
class FileMeta:
    """Метаданные файла."""

    path: Path
    size_bytes: int
    extension: str
    mime: str
    content_hash: str
    duplicates: tuple[Path, ...] = ()


@dataclass(slots=True)
class FileReport:
    """Итоговый отчёт по одному файлу."""

    meta: FileMeta
    findings: list[Finding] = field(default_factory=list)
    category_counts: dict[PIICategory, int] = field(default_factory=dict)
    protection_level: ProtectionLevel = ProtectionLevel.NONE
    error: str | None = None
    elapsed_seconds: float = 0.0
    text_length: int = 0
    rows_processed: int = 0  # для структурированных файлов
