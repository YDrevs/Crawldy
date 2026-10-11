"""Мінімальна одиниця валюти — не завжди цент."""

from __future__ import annotations

import pytest

from app.billing.money import DEFAULT_EXPONENT, exponent


@pytest.mark.parametrize("currency", ["JPY", "KRW", "VND", "ISK"])
def test_currencies_without_a_fractional_part(currency):
    """4900 єн — це 4900 єн. Поділені на сто, вони стають сорока девʼятьма."""
    assert exponent(currency) == 0


@pytest.mark.parametrize("currency", ["BHD", "KWD", "OMR", "TND"])
def test_currencies_with_three_places(currency):
    assert exponent(currency) == 3


@pytest.mark.parametrize("currency", ["USD", "EUR", "UAH", "PLN", "GBP"])
def test_the_ordinary_two(currency):
    assert exponent(currency) == DEFAULT_EXPONENT


def test_case_and_spaces_do_not_change_the_answer():
    assert exponent(" jpy ") == 0


def test_an_unknown_currency_gets_the_usual_two():
    """Дефолт — два, а не «невідомо».

    Невідомий показник змусив би сторінку цін мовчати про валюту, якої
    немає в переліку, — гірше, ніж показати її звичним способом.
    """
    assert exponent("XYZ") == DEFAULT_EXPONENT
