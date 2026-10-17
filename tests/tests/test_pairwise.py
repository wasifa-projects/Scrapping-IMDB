import pandas as pd
import pytest

import scrapping as sc


@pytest.mark.parametrize(
    "budget,gross,rating,json_rating,duration,expected_profit_notna,expected_mismatch,expected_runtime,expect_error",
    [
        # Pairwise case 1
        ("$100", "$300", "8.0", "8.3", "2h 0m", True, True, 120, False),
        # Pairwise case 2
        ("EUR 100", "$300", "8.0", "8.0", "95", False, False, 95, False),
        # Pairwise case 3
        ("unknown", "$300", "bad", "8.0", "bad", False, None, None, True),
        # Pairwise case 4
        ("$100", "unknown", "8.0", "bad", "1h 5m", False, None, 65, False),
        # Pairwise case 5
        ("EUR 100", "EUR 300", "bad", "bad", "0", True, None, 0, False),
        # Pairwise case 6
        ("unknown", "unknown", "8.2", "8.2", "2h", False, False, 120, True),
    ],
)
def test_pairwise_compute_derived_columns_multi_input_matrix(
    fake_loggers,
    budget,
    gross,
    rating,
    json_rating,
    duration,
    expected_profit_notna,
    expected_mismatch,
    expected_runtime,
    expect_error,
):
    error_logger, results_logger = fake_loggers
    df = pd.DataFrame(
        [
            {
                "budget": budget,
                "grossWorldWWide": gross,
                "gross_US_Canada": gross,
                "opening_weekend_Gross": gross,
                "awards_wins_nominations_total": "1 wins & 1 nominations",
                "Duration": duration,
                "release_date": "2020-01-01",
                "stars": [],
                "genres": [],
                "countries_origin": [],
                "Rating": rating,
                "json_ld_rating": json_rating,
            }
        ]
    )

    out = sc.compute_derived_columns(df, error_logger, results_logger)

    if expect_error:
        error_logger.error.assert_called_once()
        assert "rating_mismatch" not in out.columns
        return

    assert bool(pd.notna(out.loc[0, "profit"])) is expected_profit_notna
    if expected_mismatch is None:
        assert pd.isna(out.loc[0, "rating_mismatch"])
    else:
        assert bool(out.loc[0, "rating_mismatch"]) is expected_mismatch
    if expected_runtime is None:
        assert pd.isna(out.loc[0, "runtime_minutes"])
    else:
        assert out.loc[0, "runtime_minutes"] == expected_runtime


@pytest.mark.parametrize(
    "has_movie_link,has_link,has_title,has_title_lower,expect_records,expect_title_value",
    [
        # Pairwise case 1
        (True, False, True, False, 1, "Title A"),
        # Pairwise case 2
        (False, True, False, True, 1, "title b"),
        # Pairwise case 3
        (True, False, False, False, 1, None),
        # Pairwise case 4
        (False, True, False, False, 1, None),
        # Pairwise case 5
        (False, False, True, True, 0, None),
        # Pairwise case 6
        (True, True, True, True, 1, "Title A"),
    ],
)
def test_pairwise_links_from_df_column_interaction_matrix(
    has_movie_link,
    has_link,
    has_title,
    has_title_lower,
    expect_records,
    expect_title_value,
):
    row = {}
    if has_movie_link:
        row["Movie Link"] = "https://www.imdb.com/title/tt1/"
    if has_link:
        row["link"] = "https://www.imdb.com/title/tt2/"
    if has_title:
        row["Title"] = "Title A"
    if has_title_lower:
        row["title"] = "title b"

    df = pd.DataFrame([row])
    out = sc._links_from_df(df)

    assert len(out) == expect_records
    if expect_records:
        assert out[0]["title"] == expect_title_value
