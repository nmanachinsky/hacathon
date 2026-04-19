"""Классификация уровня защищённости (УЗ-1…УЗ-4) согласно ПП РФ № 1119."""

from __future__ import annotations

from ..config import ClassificationCfg
from ..types import (
    BIOMETRIC_CATEGORIES,
    PAYMENT_CATEGORIES,
    REGULAR_CATEGORIES,
    SENSITIVE_CATEGORIES,
    STATE_ID_CATEGORIES,
    PIICategory,
    ProtectionLevel,
)


def classify(
    counts: dict[PIICategory, int],
    *,
    rows_processed: int = 0,
    cfg: ClassificationCfg | None = None,
) -> ProtectionLevel:
    """Определить УЗ по счётчикам категорий.

    Правила (упрощённые из 152-ФЗ + ПП № 1119):
    - УЗ-1: специальные категории (здоровье/религия/политика/раса) ИЛИ биометрия
    - УЗ-2: платёжные данные ИЛИ много госидентификаторов
    - УЗ-3: мало госидентификаторов ИЛИ много обычных ПДн
    - УЗ-4: только обычные ПДн в небольшом количестве
    - NONE: ничего не найдено
    """
    cfg = cfg or ClassificationCfg()

    if not counts:
        return ProtectionLevel.NONE

    # Считаем суммы по группам
    sensitive = sum(c for cat, c in counts.items() if cat in SENSITIVE_CATEGORIES)
    biometric = sum(c for cat, c in counts.items() if cat in BIOMETRIC_CATEGORIES)
    payment = sum(c for cat, c in counts.items() if cat in PAYMENT_CATEGORIES)
    state_id = sum(c for cat, c in counts.items() if cat in STATE_ID_CATEGORIES)
    regular = sum(c for cat, c in counts.items() if cat in REGULAR_CATEGORIES)

    if sensitive > 0 or biometric > 0:
        return ProtectionLevel.UZ_1

    state_id_large = (
        state_id >= cfg.state_id_large_count
        or (rows_processed > 0 and state_id / rows_processed >= cfg.state_id_large_ratio)
    )
    regular_large = (
        regular >= cfg.regular_pii_large_count
        or (rows_processed > 0 and regular / rows_processed >= cfg.regular_pii_large_ratio)
    )

    if payment > 0 or state_id_large:
        return ProtectionLevel.UZ_2
    if state_id > 0 or regular_large:
        return ProtectionLevel.UZ_3
    if regular > 0:
        return ProtectionLevel.UZ_4
    return ProtectionLevel.NONE


def recommendations_for(level: ProtectionLevel) -> str:
    """Краткие рекомендации по уровню защиты."""
    return {
        ProtectionLevel.UZ_1: (
            "Максимальный уровень защиты: шифрование, изолированное хранение, "
            "контроль доступа, аудит, уведомление РКН при инцидентах."
        ),
        ProtectionLevel.UZ_2: (
            "Высокий уровень: шифрование при передаче, ограничение доступа, "
            "журналирование операций, регулярные аудиты."
        ),
        ProtectionLevel.UZ_3: (
            "Стандартный уровень: контроль доступа, ролевая модель, "
            "хранение в защищённых хранилищах."
        ),
        ProtectionLevel.UZ_4: (
            "Базовый уровень: парольный доступ, минимизация копий, "
            "соблюдение принципа минимальной достаточности."
        ),
        ProtectionLevel.NONE: "ПДн не обнаружены — стандартные меры ИБ.",
    }[level]
