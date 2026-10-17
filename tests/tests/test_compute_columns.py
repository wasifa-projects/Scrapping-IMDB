import pandas as pd

import scrapping as sc


def test_compute_derived_columns_happy_path(fake_loggers):
    error_logger, results_logger = fake_loggers
    df = pd.DataFrame(
        [
            {
                "budget": "$1,000,000",
                "grossWorldWWide": "$2,500,000",
                "gross_US_Canada": "$700,000",
                "opening_weekend_Gross": "$150,000",
                "awards_wins_nominations_total": "10 wins & 5 nominations",
                "Duration": "2h 5m",
                "release_date": "January 10, 2020",
                "stars": ["A", "B", "C"],
                "genres": "['Drama', 'History']",
                "countries_origin": ["US"],
                "Rating": "8.1",
                "json_ld_rating": "8.3",
            },
            {
                "budget": "EUR 1,000,000",
                "grossWorldWWide": "$2,000,000",
                "gross_US_Canada": "$500,000",
                "opening_weekend_Gross": "$100,000",
                "awards_wins_nominations_total": "invalid",
                "Duration": "95",
                "release_date": "March 2020",
                "stars": None,
                "genres": None,
                "countries_origin": "['US', 'UK']",
                "Rating": "7.0",
                "json_ld_rating": "7.0",
            },
        ]
    )

    out = sc.compute_derived_columns(df, error_logger, results_logger)

    assert out.loc[0, "budget_numeric"] == 1_000_000.0
    assert out.loc[0, "grossWorldWWide_numeric"] == 2_500_000.0
    assert out.loc[0, "profit"] == 1_500_000.0
    assert out.loc[0, "roi"] == 1.5
    assert out.loc[1, "profit"] != out.loc[1, "profit"]
    assert out.loc[0, "total_wins"] == 10
    assert out.loc[0, "total_nominations"] == 5
    assert out.loc[0, "runtime_minutes"] == 125
    assert out.loc[1, "runtime_minutes"] == 95
    assert out.loc[0, "cast_size"] == 3
    assert out.loc[0, "genre_count"] == 2
    assert out.loc[1, "country_count"] == 2
    assert bool(out.loc[0, "rating_mismatch"]) is True
    assert bool(out.loc[1, "rating_mismatch"]) is False
    assert out.loc[0, "release_weekday"] == "Friday"
    assert pd.isna(out.loc[1, "release_weekday"])
    results_logger.info.assert_called_once()


def test_compute_derived_columns_handles_missing_source_columns(fake_loggers):
    error_logger, results_logger = fake_loggers
    df = pd.DataFrame([{"Title": "Only title"}])

    out = sc.compute_derived_columns(df, error_logger, results_logger)

    assert "budget_numeric" in out.columns
    assert "profit" in out.columns
    assert "runtime_minutes" in out.columns
    assert "release_month" in out.columns
    assert "rating_mismatch" in out.columns
    assert out.loc[0, "cast_size"] == 0
    results_logger.info.assert_called_once()


def test_compute_derived_columns_logs_errors_if_parsing_crashes(monkeypatch, fake_loggers):
    error_logger, results_logger = fake_loggers
    df = pd.DataFrame([{"budget": "$1", "grossWorldWWide": "$2"}])

    def explode(_):
        raise RuntimeError("boom")

    monkeypatch.setattr(sc, "_parse_money", explode)

    out = sc.compute_derived_columns(df, error_logger, results_logger)

    assert out is df
    error_logger.error.assert_called_once()
    results_logger.info.assert_not_called()
