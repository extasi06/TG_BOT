"""Проверка и нормализация ответов пользователя."""

from __future__ import annotations

import re
from fractions import Fraction
from typing import Optional


_NUMERIC_RE = re.compile(
    r"""
    ^\s*
    (?P<sign>[+-]?)\s*
    (?:
        (?P<mixed_whole>\d+)\s+(?P<mixed_num>\d+)\s*/\s*(?P<mixed_den>\d+)
        |
        (?P<fraction_num>\d+)\s*/\s*(?P<fraction_den>\d+)
        |
        (?P<number>\d+(?:[.,]\d+)?)
    )
    (?P<rest>\s*.*)?
    $
    """,
    re.VERBOSE,
)


def normalize_answer(text: str) -> str:
    """Приводит ответ к единому виду для сравнения."""
    s = text.strip().lower().replace(",", ".")
    s = s.replace("−", "-").replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s)
    return s


def _parse_numeric(text: str) -> Optional[Fraction]:
    """Пытается распознать число, дробь или смешанное число."""
    s = normalize_answer(text)
    m = _NUMERIC_RE.match(s)
    if not m:
        return None

    sign = -1 if m.group("sign") == "-" else 1

    if m.group("mixed_whole") is not None:
        whole = int(m.group("mixed_whole"))
        num = int(m.group("mixed_num"))
        den = int(m.group("mixed_den"))
        if den == 0:
            return None
        return sign * Fraction(whole * den + num, den)

    if m.group("fraction_num") is not None:
        num = int(m.group("fraction_num"))
        den = int(m.group("fraction_den"))
        if den == 0:
            return None
        return sign * Fraction(num, den)

    if m.group("number") is not None:
        try:
            return sign * Fraction(m.group("number"))
        except (ValueError, ZeroDivisionError):
            return None

    return None


def try_parse_fraction(s: str) -> Optional[Fraction]:
    """Парсит дробь вида a/b, смешанное число или десятичное число."""
    return _parse_numeric(s)


def answers_equal(user_answer: str, correct_answer: str) -> bool:
    """
    Сравнивает ответы с учётом дробей, целых чисел и десятичных.
    Допускает эквивалентные записи вроде ``1/2`` и ``0.5``, а также ответы с единицами
    измерения после числа (например, ``7 см``).
    """
    u = normalize_answer(user_answer)
    c = normalize_answer(correct_answer)
    if u == c:
        return True

    fu = _parse_numeric(user_answer)
    fc = _parse_numeric(correct_answer)
    if fu is not None and fc is not None:
        if fu == fc:
            return True
        # Для десятичных приближений к дробям допускаем небольшую погрешность.
        return abs(float(fu) - float(fc)) <= 1e-4

    # Ответы с единицами измерения после числа: "7 см", "32 л", "4 года".
    u_num = _parse_numeric(user_answer)
    c_num = _parse_numeric(correct_answer)
    if u_num is not None and c_num is not None:
        return abs(float(u_num) - float(c_num)) <= 1e-4

    # На случай совсем простых строковых совпадений после нормализации.
    try:
        return abs(float(u) - float(c)) <= 1e-4
    except ValueError:
        return False


def is_plausible_answer(text: str) -> bool:
    """Проверяет, что ввод похож на математический ответ."""
    t = text.strip()
    if not t or len(t) > 64:
        return False
    return _parse_numeric(t) is not None
