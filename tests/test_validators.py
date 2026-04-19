"""Юнит-тесты алгоритмических валидаторов."""

from pii_scanner.detectors.validators import (
    bik_check,
    inn_check,
    is_mrz_line,
    luhn_check,
    mrz_block_valid,
    ogrn_check,
    snils_check,
)


class TestLuhn:
    def test_valid_visa(self):
        assert luhn_check("4111 1111 1111 1111")

    def test_valid_mastercard(self):
        assert luhn_check("5500 0000 0000 0004")

    def test_valid_amex(self):
        assert luhn_check("3400 0000 0000 009")

    def test_invalid(self):
        assert not luhn_check("4111 1111 1111 1112")

    def test_too_short(self):
        assert not luhn_check("4111111")


class TestSnils:
    def test_valid(self):
        # Тестовые валидные СНИЛС
        assert snils_check("112-233-445 95")
        assert snils_check("11223344595")

    def test_invalid_checksum(self):
        assert not snils_check("112-233-445 96")

    def test_wrong_length(self):
        assert not snils_check("11223344")


class TestInn:
    def test_valid_inn10(self):
        assert inn_check("7707083893")  # Сбербанк

    def test_valid_inn12(self):
        # Контрольные цифры посчитаны вручную для синтетических цифр
        assert inn_check("500100732259")

    def test_invalid(self):
        assert not inn_check("1234567890")
        assert not inn_check("123456789012")

    def test_wrong_length(self):
        assert not inn_check("123")


class TestBik:
    def test_valid_format(self):
        assert bik_check("044525225")

    def test_wrong_length(self):
        assert not bik_check("12345")

    def test_wrong_country_code(self):
        assert not bik_check("123456789")


class TestOgrn:
    def test_valid_13(self):
        assert ogrn_check("1027700132195")

    def test_wrong_length(self):
        assert not ogrn_check("123")


class TestMrz:
    def test_mrz_line_recognition(self):
        line = "P<RUSIVANOV<<IVAN<<<<<<<<<<<<<<<<<<<<<<<<<<<"
        assert is_mrz_line(line)

    def test_not_mrz(self):
        assert not is_mrz_line("Hello world this is normal text")

    def test_block_valid(self):
        lines = [
            "P<RUSIVANOV<<IVAN<<<<<<<<<<<<<<<<<<<<<<<<<<<",
            "1234567897RUS8001017M2501017<<<<<<<<<<<<<<00",
        ]
        assert mrz_block_valid(lines)
