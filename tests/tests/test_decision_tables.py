from pathlib import Path

import pandas as pd
import pytest

import scrapping as sc


@pytest.mark.parametrize(
    "left, right, expected",
    [
        # Rule 1: both unknown -> True
        ("unknown", "not-set", True),
        # Rule 2: left unknown, right known -> True
        ("unknown", "$100", True),
        # Rule 3: left known, right unknown -> True
        ("$100", "none", True),
        # Rule 4: both known and equal -> True
        ("USD 10", "USD 20", True),
        # Rule 5: both known and different -> False
        ("USD 10", "EUR 20", False),
    ],
)
def test_dtt_same_or_unknown_currency_decision_table(left, right, expected):
    assert sc._same_or_unknown_currency(left, right) is expected


@pytest.mark.parametrize(
    "has_budget,gross,has_rating,json_rating,expect_profit_notna,expect_rating_mismatch_na",
    [
        # Rule A: financial columns present + rating columns present
        (True, True, True, True, True, False),
        # Rule B: financial missing + rating present
        (False, False, True, True, False, False),
        # Rule C: financial present + rating missing
        (True, True, False, False, True, True),
        # Rule D: financial missing + rating missing
        (False, False, False, False, False, True),
    ],
)
def test_dtt_compute_derived_columns_presence_decision_table(
    fake_loggers,
    has_budget,
    gross,
    has_rating,
    json_rating,
    expect_profit_notna,
    expect_rating_mismatch_na,
):
    error_logger, results_logger = fake_loggers
    row = {
        "awards_wins_nominations_total": "1 wins & 1 nominations",
        "Duration": "90",
        "release_date": "2020-01-01",
        "stars": [],
        "genres": [],
        "countries_origin": [],
    }
    if has_budget:
        row["budget"] = "$100"
    if gross:
        row["grossWorldWWide"] = "$200"
        row["gross_US_Canada"] = "$100"
        row["opening_weekend_Gross"] = "$50"
    if has_rating:
        row["Rating"] = "8.0"
    if json_rating:
        row["json_ld_rating"] = "8.1"

    out = sc.compute_derived_columns(pd.DataFrame([row]), error_logger, results_logger)

    assert bool(pd.notna(out.loc[0, "profit"])) is expect_profit_notna
    assert bool(pd.isna(out.loc[0, "rating_mismatch"])) is expect_rating_mismatch_na


@pytest.mark.parametrize(
    "retry_failed_only,status_for_link,attempt_plan,expected_attempt_calls,expect_retry_log",
    [
        # Rule 1: initial mode, first attempt fails -> auto_retry executed
        (False, "pending", [([{"link": "https://www.imdb.com/title/tt1/"}], [{"link": "https://www.imdb.com/title/tt1/"}]), ([{"link": "https://www.imdb.com/title/tt1/"}], [])], 2, True),
        # Rule 2: retry mode, first attempt fails -> no auto_retry
        (True, "failed", [([], [{"link": "https://www.imdb.com/title/tt1/"}])], 1, False),
        # Rule 3: retry mode, no failed candidates -> no driver/no attempt
        (True, "completed", [], 0, False),
    ],
)
def test_dtt_extract_advanced_data_retry_decision_table(
    monkeypatch,
    fake_loggers,
    retry_failed_only,
    status_for_link,
    attempt_plan,
    expected_attempt_calls,
    expect_retry_log,
):
    error_logger, results_logger = fake_loggers

    link = "https://www.imdb.com/title/tt1/"
    links_df = pd.DataFrame([{"Movie Link": link, "Title": "One"}])
    existing_advanced = pd.DataFrame(columns=sc.ADVANCED_COLUMNS)
    status_df = pd.DataFrame([
        {
            "link": link,
            "title": "One",
            "status": status_for_link,
            "attempt_count": 0,
            "last_error": None,
            "last_attempted_at": None,
            "completed_at": None,
        }
    ])

    def fake_read_csv_or_empty(path, columns):
        if str(path).endswith("advanced_movies_details_2024.csv"):
            return existing_advanced.copy()
        if str(path).endswith("advanced_scrape_status_2024.csv"):
            return status_df.copy()
        return pd.DataFrame(columns=columns)

    monkeypatch.setattr(sc, "read_csv_or_empty", fake_read_csv_or_empty)

    calls = {"attempt": 0, "driver_created": 0}

    class FakeDriver:
        def quit(self):
            return None

    monkeypatch.setattr(sc, "create_edge_driver", lambda: calls.__setitem__("driver_created", calls["driver_created"] + 1) or FakeDriver())

    plan_iter = iter(attempt_plan)

    def fake_attempt(driver, candidates, status_records, attempt_log_path, error_logger, phase):
        calls["attempt"] += 1
        rows, failures = next(plan_iter)
        return rows, failures

    monkeypatch.setattr(sc, "_attempt_advanced_links", fake_attempt)
    monkeypatch.setattr(sc, "_write_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(sc, "write_csv_safely", lambda *args, **kwargs: None)

    sc.extract_advanced_data(2024, links_df, error_logger, results_logger, retry_failed_only=retry_failed_only)

    assert calls["attempt"] == expected_attempt_calls
    if expected_attempt_calls == 0:
        assert calls["driver_created"] == 0
    if expect_retry_log:
        results_logger.info.assert_any_call("Retrying %s failed advanced links for %s once", 1, 2024)
