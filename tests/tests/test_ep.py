from pathlib import Path

import pandas as pd
import pytest

import scrapping as sc


@pytest.mark.parametrize(
    "value, keep_query, expected",
    [
        # Valid class: IMDb title relative URL
        ("/title/tt1234567/?ref_=x", False, "https://www.imdb.com/title/tt1234567/"),
        # Valid class: non-title absolute URL should pass through
        ("https://example.org/movie?id=1", True, "https://example.org/movie?id=1"),
        # Invalid class: empty-like input
        ("", True, None),
    ],
)
def test_ep_normalize_imdb_url_equivalence_classes(value, keep_query, expected):
    assert sc._normalize_imdb_url(value, keep_query=keep_query) == expected


def test_ep_normalize_imdb_url_invalid_type_raises_type_error():
    # Invalid class: non-string path-like input is not accepted by urljoin
    with pytest.raises(TypeError):
        sc._normalize_imdb_url(123, keep_query=True)


@pytest.mark.parametrize(
    "value, expected",
    [
        # Valid class: supported multiplier
        ("2.5 million", 2_500_000.0),
        # Valid class: plain number with commas
        ("1,234", 1234.0),
        # Invalid class: unsupported unit token -> number parsed without multiplier
        ("2 trillion", 2.0),
        # Invalid class: no numeric token
        ("budget unknown", None),
    ],
)
def test_ep_parse_money_equivalence_classes(value, expected):
    assert sc._parse_money(value) == expected


@pytest.mark.parametrize(
    "frame, expected",
    [
        # Valid class: link column exists, title column missing
        (pd.DataFrame([{"Movie Link": "https://www.imdb.com/title/tt1/"}]), [{"link": "https://www.imdb.com/title/tt1/", "title": None}]),
        # Invalid class: link present but blank values are discarded
        (pd.DataFrame([{"Movie Link": "", "Title": "X"}, {"Movie Link": None, "Title": "Y"}]), []),
    ],
)
def test_ep_links_from_df_equivalence_classes(frame, expected):
    assert sc._links_from_df(frame) == expected


def test_ep_status_records_invalid_numeric_class_maps_to_zero():
    status_df = pd.DataFrame(
        [
            {"link": "https://www.imdb.com/title/tt1/", "attempt_count": "NaN"},
            {"link": "https://www.imdb.com/title/tt2/", "attempt_count": "bad"},
        ]
    )

    out = sc._status_records(status_df)

    assert out["https://www.imdb.com/title/tt1/"]["attempt_count"] == 0
    assert out["https://www.imdb.com/title/tt2/"]["attempt_count"] == 0


def test_ep_parse_release_dates_uses_fallback_partition(monkeypatch):
    calls = {"count": 0}

    real_to_datetime = pd.to_datetime

    def fake_to_datetime(value, *args, **kwargs):
        calls["count"] += 1
        # First call is the vectorized mixed-format branch.
        if calls["count"] == 1:
            raise ValueError("force fallback")
        return real_to_datetime(value, errors="coerce")

    monkeypatch.setattr(sc.pd, "to_datetime", fake_to_datetime)

    out = sc._parse_release_dates(pd.Series(["2020-01-01", "invalid"]))

    assert out.notna().sum() == 1
    assert calls["count"] >= 3


def test_ep_write_csv_safely_accepts_path_string_class(tmp_path):
    df = pd.DataFrame([{"a": 1}])
    path_as_string = str(tmp_path / "ep" / "file.csv")

    sc.write_csv_safely(df, path_as_string)

    reread = pd.read_csv(Path(path_as_string))
    assert len(reread) == 1
