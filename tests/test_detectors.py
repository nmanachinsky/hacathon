"""Юнит-тесты детекторов."""

from pii_scanner.detectors.contacts import detect_emails, detect_phones
from pii_scanner.detectors.payment import detect_bank_cards, detect_bik, detect_cvv
from pii_scanner.detectors.personal import detect_birth_dates, detect_fio_regex
from pii_scanner.detectors.registry import detect_all
from pii_scanner.detectors.sensitive import detect_biometric, detect_health
from pii_scanner.detectors.state_id import (
    detect_inn,
    detect_passports,
    detect_snils,
)
from pii_scanner.types import PIICategory


def _categories(matches) -> set[str]:
    return {m.category.value for m in matches}


class TestContacts:
    def test_email(self):
        text = "связаться: ivan.petrov@example.com или petrov@mail.ru"
        result = list(detect_emails(text))
        assert len(result) == 2
        assert all(m.category == PIICategory.EMAIL for m in result)

    def test_phone_plus7(self):
        text = "Телефон +7 910 245-63-18"
        result = list(detect_phones(text))
        assert len(result) == 1

    def test_phone_eight(self):
        text = "Тел: 8(916)123-45-67"
        result = list(detect_phones(text))
        assert len(result) == 1


class TestStateId:
    def test_passport_with_context(self):
        text = "паспорт серии 52 17 № 118903"
        assert any(m.category == PIICategory.PASSPORT_RF for m in detect_passports(text))

    def test_passport_without_context_skipped(self):
        text = "Просто число 5217 118903 без контекста"
        assert not list(detect_passports(text))

    def test_snils_valid(self):
        text = "СНИЛС: 112-233-445 95"
        result = list(detect_snils(text))
        assert len(result) >= 1

    def test_inn_in_context(self):
        text = "ИНН организации: 7707083893"
        result = list(detect_inn(text))
        assert any(m.category == PIICategory.INN_LEGAL for m in result)


class TestPayment:
    def test_bank_card_luhn(self):
        text = "Карта 4111 1111 1111 1111 действует до 12/29"
        result = list(detect_bank_cards(text))
        assert len(result) == 1

    def test_bank_card_invalid_skipped(self):
        text = "Номер 4111 1111 1111 1112"
        assert not list(detect_bank_cards(text))

    def test_bik_with_context(self):
        text = "БИК банка: 044525225"
        result = list(detect_bik(text))
        assert len(result) == 1

    def test_cvv_in_context(self):
        text = "CVV: 123"
        result = list(detect_cvv(text))
        assert len(result) == 1


class TestPersonal:
    def test_fio_triplet(self):
        text = "Иванов Иван Иванович подписал заявление"
        result = list(detect_fio_regex(text))
        assert len(result) >= 1

    def test_birth_date_with_context(self):
        text = "Дата рождения 17.11.1988"
        result = list(detect_birth_dates(text))
        assert any(m.confidence > 0.7 for m in result)


class TestSensitive:
    def test_biometric(self):
        text = "Согласие на обработку отпечатков пальцев"
        result = list(detect_biometric(text))
        assert len(result) >= 1

    def test_health(self):
        text = "Диагноз: хроническое заболевание"
        result = list(detect_health(text))
        assert len(result) >= 1


class TestRegistry:
    def test_full_consent_doc(self):
        text = (
            "Я, Воронцов Тимур Алексеевич, 17.11.1988 г. рождения,\n"
            "паспорт серии 52 17 № 118903,\n"
            "телефон: +7 910 245-63-18,\n"
            "email: t.test@inbox.test,\n"
            "ИНН: 524817336590"
        )
        cats = _categories(detect_all(text, use_ner=False, min_confidence=0.5))
        assert "fio" in cats
        assert "birth_date" in cats
        assert "passport_rf" in cats
        assert "phone" in cats
        assert "email" in cats
        assert "inn_personal" in cats
