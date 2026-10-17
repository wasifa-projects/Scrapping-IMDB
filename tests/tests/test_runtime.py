import pandas as pd
import pytest

import scrapping as sc


@pytest.mark.parametrize(
    "value, expected",
    [
        ("PT2H5M", 125),
        ("PT1H", 60),
        ("PT45M", 45),
        ("PT", 0),
        ("bad", None),
        (None, None),
    ],
)
def test_iso8601_to_minutes(value, expected):
    assert sc._iso8601_to_minutes(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2h 15m", 135),
        ("2 h 0 m", 120),
        ("95", 95),
        ("bad", None),
        (None, None),
        (float("nan"), None),
    ],
)
def test_parse_runtime_to_minutes(value, expected):
    assert sc._parse_runtime_to_minutes(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("January 10, 2020", True),
        ("2020-01-10", True),
        ("January 2020", False),
        ("2020", False),
        (None, False),
    ],
)
def test_release_date_has_day(value, expected):
    assert sc._release_date_has_day(value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ([1, 2, 3], 3),
        ((1, 2), 2),
        ("['a', 'b']", 2),
        ("not-a-list", 0),
        (None, 0),
        (float("nan"), 0),
    ],
)
def test_safe_list_len(value, expected):
    assert sc._safe_list_len(value) == expected


def test_parse_release_dates_mixed_formats_returns_datetime_series():
    series = pd.Series(["2020-01-10", "March 5, 2021", "invalid", None])

    parsed = sc._parse_release_dates(series)

    assert pd.api.types.is_datetime64_any_dtype(parsed)
    assert parsed.notna().sum() == 2
