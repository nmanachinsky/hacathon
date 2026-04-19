"""Тесты строгой фильтрации result.csv (защита от FP)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pii_scanner.reporting.writers import _is_confident_pii, write_result_csv


def _make(level: str, **counts: int) -> dict:
    return {
        "path": "/tmp/test.txt",
        "size": 100,
        "mtime": 1727364660.0,
        "protection_level": level,
        "category_counts": counts,
    }


@pytest.mark.unit
class TestConfidentPiiFilter:
    def test_no_pii_excluded(self) -> None:
        assert _is_confident_pii(_make("Без ПДн")) is False

    def test_empty_counts_excluded(self) -> None:
        assert _is_confident_pii({"protection_level": "УЗ-3", "category_counts": {}}) is False

    def test_state_id_always_included(self) -> None:
        assert _is_confident_pii(_make("УЗ-3", snils=1)) is True
        assert _is_confident_pii(_make("УЗ-2", inn_personal=1)) is True
        assert _is_confident_pii(_make("УЗ-3", passport_rf=1)) is True

    def test_payment_always_included(self) -> None:
        assert _is_confident_pii(_make("УЗ-2", bank_card=1)) is True
        assert _is_confident_pii(_make("УЗ-2", bik=1)) is True

    def test_special_categories_included(self) -> None:
        assert _is_confident_pii(_make("УЗ-1", health=1)) is True
        assert _is_confident_pii(_make("УЗ-1", biometric=1)) is True

    def test_lone_fio_excluded(self) -> None:
        assert _is_confident_pii(_make("УЗ-4", fio=1)) is False
        assert _is_confident_pii(_make("УЗ-4", fio=20)) is False

    def test_lone_address_excluded(self) -> None:
        assert _is_confident_pii(_make("УЗ-4", address=5)) is False

    def test_lone_birth_place_excluded(self) -> None:
        assert _is_confident_pii(_make("УЗ-4", birth_place=3)) is False

    def test_lone_email_requires_volume(self) -> None:
        assert _is_confident_pii(_make("УЗ-4", email=1)) is False
        assert _is_confident_pii(_make("УЗ-4", email=2)) is False
        assert _is_confident_pii(_make("УЗ-4", email=3)) is True

    def test_lone_phone_requires_volume(self) -> None:
        assert _is_confident_pii(_make("УЗ-4", phone=1)) is False
        assert _is_confident_pii(_make("УЗ-4", phone=3)) is True

    def test_two_categories_included(self) -> None:
        assert _is_confident_pii(_make("УЗ-4", fio=1, phone=1)) is True
        assert _is_confident_pii(_make("УЗ-4", email=1, address=1)) is True


@pytest.mark.unit
def test_csv_format_matches_spec(tmp_path: Path) -> None:
    reports = [
        _make("УЗ-3", snils=1),
        _make("Без ПДн"),
        _make("УЗ-4", fio=1),  # отбрасывается
    ]
    reports[0]["path"] = "/data/share/CA01_01.tif"
    reports[0]["size"] = 3068287

    out = tmp_path / "result.csv"
    write_result_csv(reports, out)

    rows = list(csv.reader(out.open()))
    assert rows[0] == ["size", "time", "name"]
    assert len(rows) == 2  # header + 1 confident row
    assert rows[1][0] == "3068287"
    assert rows[1][2] == "CA01_01.tif"
    # формат времени: "sep 26 18:31"
    assert len(rows[1][1].split()) == 3
