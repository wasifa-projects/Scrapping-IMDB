import pandas as pd
import pytest

import scrapping as sc


@pytest.mark.parametrize(
    "value, expected",
    [
        ("$1,234", 1234.0),
        ("EUR 2.5 million", 2_500_000.0),
        ("3bn", 3_000_000_000.0),
        ("45k", 45_000.0),
        ("$0.5M", 500_000.0),
        ("not available", None),
        (None, None),
        (float("nan"), None),
    ],
)
def test_parse_money_parses_supported_formats(value, expected):
    result = sc._parse_money(value)
    if expected is None:
        assert result is None
    else:
        assert result == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("$1M", "$"),
        ("eur 10", "EUR"),
        ("GBP 25", "GBP"),
        ("unknown", None),
        (None, None),
        (float("nan"), None),
    ],
)
def test_currency_symbol_detects_symbols_and_codes(value, expected):
    assert sc._currency_symbol(value) == expected


@pytest.mark.parametrize(
    "left, right, expected",
    [
        ("$1M", "$2M", True),
        ("$1M", "EUR 2M", False),
        ("unknown", "$2M", True),
        (None, "EUR 2M", True),
    ],
)
def test_same_or_unknown_currency_behavior(left, right, expected):
    assert sc._same_or_unknown_currency(left, right) is expected