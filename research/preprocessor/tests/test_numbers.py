"""Tests for the German-number parser."""
from __future__ import annotations

from stages.numbers import parse_german_number


def test_thousands_and_decimal() -> None:
    assert parse_german_number("1.000,50") == 1000.5


def test_currency_thousands() -> None:
    assert parse_german_number("290.100 €") == 290100.0
    assert parse_german_number("172.549 €") == 172549.0


def test_percent() -> None:
    assert parse_german_number("14%") == 14.0
    assert parse_german_number("50 %") == 50.0


def test_plain_thousands() -> None:
    assert parse_german_number("50.000") == 50000.0
    assert parse_german_number("10.000.000") == 10000000.0


def test_single_dot_decimal_tail_not_three() -> None:
    assert parse_german_number("1.5") == 1.5


def test_comma_decimal() -> None:
    assert parse_german_number("1,5") == 1.5


def test_embedded_in_prose() -> None:
    assert parse_german_number("von 763.840 € pro Jahr") == 763840.0


def test_none_on_garbage() -> None:
    assert parse_german_number("keine Zahl") is None
    assert parse_german_number("") is None
    assert parse_german_number(None) is None  # type: ignore[arg-type]
