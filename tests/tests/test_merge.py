from pathlib import Path

import pandas as pd
import pytest

import scrapping as sc


def test_merge_data_success(monkeypatch, fake_loggers):
    error_logger, results_logger = fake_loggers

    basic_df = pd.DataFrame(
        [
            {"Movie Link": "https://www.imdb.com/title/tt1/", "Title": "A"},
            {"Movie Link": "https://www.imdb.com/title/tt2/", "Title": "B"},
        ]
    )
    advanced_df = pd.DataFrame(
        [
            {"link": "https://www.imdb.com/title/tt1/", "budget": "$1M"},
            {"link": "https://www.imdb.com/title/tt3/", "budget": "$3M"},
        ]
    )

    monkeypatch.setattr(sc.pd, "read_csv", lambda _: basic_df.copy())
    monkeypatch.setattr(sc, "read_csv_or_empty", lambda *args, **kwargs: advanced_df.copy())

    merged = sc.merge_data(1920, Path("unused"), error_logger, results_logger)

    assert merged is not None
    assert len(merged) == 2
    assert "budget" in merged.columns
    assert merged.loc[0, "budget"] == "$1M"
    results_logger.info.assert_called_once()


def test_merge_data_missing_join_columns_returns_none(monkeypatch, fake_loggers):
    error_logger, results_logger = fake_loggers

    monkeypatch.setattr(sc.pd, "read_csv", lambda _: pd.DataFrame([{"Title": "A"}]))
    monkeypatch.setattr(sc, "read_csv_or_empty", lambda *args, **kwargs: pd.DataFrame([{"budget": "$1M"}]))

    merged = sc.merge_data(1920, Path("unused"), error_logger, results_logger)

    assert merged is None
    error_logger.error.assert_called_once()


def test_extract_links_rejects_negative_max_movies(fake_loggers):
    error_logger, results_logger = fake_loggers

    with pytest.raises(ValueError):
        sc.extract_links(1920, error_logger, results_logger, max_movies=-1)
