"""Тесты классификатора УЗ."""

from pii_scanner.classification.uz_classifier import classify
from pii_scanner.config import ClassificationCfg
from pii_scanner.types import PIICategory, ProtectionLevel


def test_no_pii():
    assert classify({}) == ProtectionLevel.NONE


def test_uz1_biometric():
    counts = {PIICategory.BIOMETRIC: 1}
    assert classify(counts) == ProtectionLevel.UZ_1


def test_uz1_sensitive():
    counts = {PIICategory.HEALTH: 1, PIICategory.FIO: 5}
    assert classify(counts) == ProtectionLevel.UZ_1


def test_uz2_payment():
    counts = {PIICategory.BANK_CARD: 1}
    assert classify(counts) == ProtectionLevel.UZ_2


def test_uz2_state_id_large():
    counts = {PIICategory.SNILS: 15}
    assert classify(counts) == ProtectionLevel.UZ_2


def test_uz3_state_id_small():
    counts = {PIICategory.PASSPORT_RF: 1, PIICategory.FIO: 1}
    assert classify(counts) == ProtectionLevel.UZ_3


def test_uz3_regular_large():
    counts = {PIICategory.FIO: 100}
    assert classify(counts) == ProtectionLevel.UZ_3


def test_uz4_regular_small():
    counts = {PIICategory.FIO: 1, PIICategory.EMAIL: 1}
    assert classify(counts) == ProtectionLevel.UZ_4


def test_thresholds_via_ratio():
    cfg = ClassificationCfg(state_id_large_count=1000, state_id_large_ratio=0.5)
    counts = {PIICategory.SNILS: 60}
    assert classify(counts, rows_processed=100, cfg=cfg) == ProtectionLevel.UZ_2
