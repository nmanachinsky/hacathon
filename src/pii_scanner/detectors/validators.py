"""Алгоритмические валидаторы (Luhn, СНИЛС, ИНН, БИК, расчётный счёт)."""

from __future__ import annotations

import re

_DIGITS_ONLY = re.compile(r"\D+")


def _digits(value: str) -> str:
    return _DIGITS_ONLY.sub("", value)


def luhn_check(card_number: str) -> bool:
    """Проверка алгоритмом Луна (для банковских карт)."""
    d = _digits(card_number)
    if len(d) < 12 or len(d) > 19:
        return False
    s = 0
    parity = len(d) % 2
    for i, ch in enumerate(d):
        n = ord(ch) - 48
        if i % 2 == parity:
            n *= 2
            if n > 9:
                n -= 9
        s += n
    return s % 10 == 0


def snils_check(snils: str) -> bool:
    """Проверка контрольной суммы СНИЛС (11 цифр)."""
    d = _digits(snils)
    if len(d) != 11:
        return False
    digits = [int(c) for c in d]
    main, control = digits[:9], int(d[-2:])
    s = sum(n * (9 - i) for i, n in enumerate(main))
    if s < 100:
        check = s
    elif s in (100, 101):
        check = 0
    else:
        check = s % 101
        if check in (100, 101):
            check = 0
    return check == control


def inn_check(inn: str) -> bool:
    """Проверка ИНН (10 — юр. лицо, 12 — физ. лицо)."""
    d = _digits(inn)
    if len(d) == 10:
        return _inn10(d)
    if len(d) == 12:
        return _inn12(d)
    return False


def _inn10(d: str) -> bool:
    coefs = (2, 4, 10, 3, 5, 9, 4, 6, 8)
    s = sum(int(d[i]) * coefs[i] for i in range(9))
    return (s % 11) % 10 == int(d[9])


def _inn12(d: str) -> bool:
    coefs1 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    coefs2 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    s1 = sum(int(d[i]) * coefs1[i] for i in range(10))
    s2 = sum(int(d[i]) * coefs2[i] for i in range(11))
    return (s1 % 11) % 10 == int(d[10]) and (s2 % 11) % 10 == int(d[11])


def bik_check(bik: str) -> bool:
    """Проверка БИК РФ (9 цифр; первые 2 — код страны 04, далее проверка диапазона)."""
    d = _digits(bik)
    if len(d) != 9:
        return False
    # Код страны для РФ — 04
    return d.startswith("04")


def account_check(account: str, bik: str) -> bool:
    """Проверка контрольного разряда расчётного счёта по БИК.

    Алгоритм ЦБ РФ: ОПКР = БИК[6:9] + account, контрольный разряд по весовому коду.
    """
    acc = _digits(account)
    bik_d = _digits(bik)
    if len(acc) != 20 or len(bik_d) != 9:
        return False
    s = bik_d[-3:] + acc
    weights = (7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1)
    total = sum(int(c) * w for c, w in zip(s, weights, strict=True))
    return total % 10 == 0


def ogrn_check(value: str) -> bool:
    """Проверка ОГРН (13 или 15 цифр)."""
    d = _digits(value)
    if len(d) == 13:
        return int(d[-1]) == int(d[:-1]) % 11 % 10
    if len(d) == 15:
        return int(d[-1]) == int(d[:-1]) % 13 % 10
    return False


# ---- MRZ (ICAO 9303) ----

_MRZ_WEIGHTS = (7, 3, 1)
_MRZ_VALUE = {chr(c): c - 55 for c in range(ord("A"), ord("Z") + 1)}
for _c in "0123456789":
    _MRZ_VALUE[_c] = int(_c)
_MRZ_VALUE["<"] = 0


def mrz_checkdigit(s: str) -> int:
    total = 0
    for i, ch in enumerate(s):
        v = _MRZ_VALUE.get(ch)
        if v is None:
            return -1
        total += v * _MRZ_WEIGHTS[i % 3]
    return total % 10


def is_mrz_line(line: str) -> bool:
    """Похоже ли на строку MRZ (44 или 36 символов, базовая решётка)."""
    s = line.strip()
    if len(s) not in (30, 36, 44):
        return False
    if not all(c.isalnum() or c == "<" for c in s):
        return False
    return s.count("<") >= 3


def mrz_block_valid(lines: list[str]) -> bool:
    """Поверхностная проверка двух- или трёхстрочного MRZ."""
    if len(lines) < 2:
        return False
    return all(is_mrz_line(line) for line in lines[:3])
