from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import scrapping as sc


class _NoopDriver:
    def __init__(self, page_source="<ul class='ipc-metadata-list'></ul>"):
        self.page_source = page_source
        self.got_urls = []
        self.quit_called = False

    def get(self, url):
        self.got_urls.append(url)

    def find_elements(self, by=None, value=None):
        return [object()] * 1000

    def execute_script(self, script, *args):
        return None

    def quit(self):
        self.quit_called = True


@pytest.mark.parametrize(
    "max_movies, expect_error, max_len",
    [
        (-1, True, None),   # Below minimum boundary
        (0, False, 0),      # Minimum boundary
        (1, False, 1),      # Just above minimum boundary
        (600, False, 600),  # Typical boundary
        (601, False, 601),  # Just above typical boundary
    ],
)
def test_extract_links_max_movies_bva(monkeypatch, fake_loggers, max_movies, expect_error, max_len):
    error_logger, results_logger = fake_loggers
    driver = _NoopDriver()

    monkeypatch.setattr(sc, "create_edge_driver", lambda: driver)
    monkeypatch.setattr(sc, "_wait_for_page_ready", lambda *args, **kwargs: None)
    monkeypatch.setattr(sc, "WebDriverWait", lambda *args, **kwargs: SimpleNamespace(until=lambda condition: True))
    monkeypatch.setattr(sc.time, "sleep", lambda *_: None)

    if expect_error:
        with pytest.raises(ValueError):
            sc.extract_links(2024, error_logger, results_logger, max_movies=max_movies)
        return

    df = sc.extract_links(2024, error_logger, results_logger, max_movies=max_movies)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == sc.BASIC_COLUMNS
    assert len(df) <= max_len


@pytest.mark.parametrize(
    "links_df, expected_rows, expect_error_log",
    [
        (pd.DataFrame(columns=["Movie Link", "Title"]), 0, True),  # Minimum boundary: 0 links
        (
            pd.DataFrame([{"Movie Link": "https://www.imdb.com/title/tt1/", "Title": "One"}]),
            1,
            False,
        ),  # Just above minimum boundary: 1 link
    ],
)
def test_extract_advanced_data_link_count_bva(monkeypatch, fake_loggers, links_df, expected_rows, expect_error_log):
    error_logger, results_logger = fake_loggers
    fake_driver = _NoopDriver()

    monkeypatch.setattr(
        sc,
        "read_csv_or_empty",
        lambda path, columns: pd.DataFrame(columns=columns),
    )
    monkeypatch.setattr(sc, "create_edge_driver", lambda: fake_driver)
    monkeypatch.setattr(
        sc,
        "_attempt_advanced_links",
        lambda driver, candidates, status_records, attempt_log_path, error_logger, phase: (
            ([{"link": candidates[0]["link"]}] if candidates else []),
            [],
        ),
    )
    monkeypatch.setattr(sc, "_write_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(sc, "write_csv_safely", lambda *args, **kwargs: None)

    out = sc.extract_advanced_data(2024, links_df, error_logger, results_logger)

    assert len(out) == expected_rows
    if expect_error_log:
        error_logger.error.assert_called_once()
    else:
        error_logger.error.assert_not_called()


@pytest.mark.parametrize(
    "columns",
    [
        [],          # Minimum boundary: 0 expected columns
        ["only"],    # Just above minimum boundary: 1 expected column
        ["a", "b"], # Typical boundary
    ],
)
def test_read_csv_or_empty_columns_count_bva(tmp_path, columns):
    missing_path = tmp_path / "missing.csv"

    out = sc.read_csv_or_empty(missing_path, columns)

    assert list(out.columns) == columns
    assert out.empty


@pytest.mark.parametrize(
    "row_count",
    [
        0,  # Minimum boundary: empty DataFrame
        1,  # Just above minimum boundary
        2,  # Typical boundary
    ],
)
def test_write_csv_safely_row_count_bva(tmp_path, row_count):
    target = tmp_path / "bva" / "data.csv"
    df = pd.DataFrame({"x": list(range(row_count))})

    sc.write_csv_safely(df, target)

    reread = pd.read_csv(target)
    assert len(reread) == row_count


@pytest.mark.parametrize(
    "basic_rows, advanced_rows, expected_rows",
    [
        (0, 0, 0),  # Minimum boundary
        (1, 0, 1),  # Just above minimum
        (2, 1, 2),  # Typical boundary
    ],
)
def test_merge_data_row_count_bva(monkeypatch, fake_loggers, basic_rows, advanced_rows, expected_rows):
    error_logger, results_logger = fake_loggers

    basic_df = pd.DataFrame(
        [
            {"Movie Link": f"https://www.imdb.com/title/tt{i}/", "Title": f"T{i}"}
            for i in range(1, basic_rows + 1)
        ],
        columns=["Movie Link", "Title"],
    )
    advanced_df = pd.DataFrame(
        [
            {"link": f"https://www.imdb.com/title/tt{i}/", "budget": "$1"}
            for i in range(1, advanced_rows + 1)
        ],
        columns=["link", "budget"],
    )

    monkeypatch.setattr(sc.pd, "read_csv", lambda *args, **kwargs: basic_df)
    monkeypatch.setattr(sc, "read_csv_or_empty", lambda *args, **kwargs: advanced_df)

    out = sc.merge_data(2024, Path("unused"), error_logger, results_logger)

    assert out is not None
    assert len(out) == expected_rows


@pytest.mark.parametrize(
    "rating, json_ld_rating, expected_mismatch",
    [
        ("8.00", "8.15", True),   # Threshold edge with float representation in current implementation
        ("8.00", "8.14", False),  # Just below threshold
        ("8.00", "8.16", True),   # Just above threshold
    ],
)
def test_compute_derived_columns_rating_mismatch_threshold_bva(fake_loggers, rating, json_ld_rating, expected_mismatch):
    error_logger, results_logger = fake_loggers
    df = pd.DataFrame(
        [
            {
                "budget": "$100",
                "grossWorldWWide": "$200",
                "gross_US_Canada": "$50",
                "opening_weekend_Gross": "$10",
                "awards_wins_nominations_total": "0 wins & 0 nominations",
                "Duration": "0",
                "release_date": "2020-01-10",
                "stars": [],
                "genres": [],
                "countries_origin": [],
                "Rating": rating,
                "json_ld_rating": json_ld_rating,
            }
        ]
    )

    out = sc.compute_derived_columns(df, error_logger, results_logger)

    assert bool(out.loc[0, "rating_mismatch"]) is expected_mismatch


def test_compute_derived_columns_budget_zero_bva(fake_loggers):
    # Minimum boundary for budget denominator: 0 should yield NaN ROI
    error_logger, results_logger = fake_loggers
    df = pd.DataFrame(
        [
            {
                "budget": "$0",
                "grossWorldWWide": "$100",
                "gross_US_Canada": "$50",
                "opening_weekend_Gross": "$10",
                "awards_wins_nominations_total": "1 wins & 1 nominations",
                "Duration": "1",
                "release_date": "2020-01-10",
                "stars": [],
                "genres": [],
                "countries_origin": [],
                "Rating": "8",
                "json_ld_rating": "8",
            }
        ]
    )

    out = sc.compute_derived_columns(df, error_logger, results_logger)

    assert pd.isna(out.loc[0, "roi"])


@pytest.mark.parametrize(
    "value, expected",
    [
        ("no digits", None),  # Below minimum boundary: cannot parse number
        ("0", 0.0),           # Minimum boundary
        ("1", 1.0),           # Just above minimum boundary
        ("999", 999.0),       # Typical boundary
    ],
)
def test_parse_money_numeric_boundary_values(value, expected):
    assert sc._parse_money(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("", None),         # Below minimum boundary: empty input
        ("$", "$"),        # Minimum boundary: smallest valid symbol token
        ("USD", "USD"),    # Just above minimum token size
    ],
)
def test_currency_symbol_token_boundary_values(value, expected):
    assert sc._currency_symbol(value) == expected


@pytest.mark.parametrize(
    "left, right, expected",
    [
        ("", "", True),                # Minimum boundary: both unknown currencies
        ("$1", "$2", True),            # Typical matching boundary
        ("$1", "EUR 2", False),        # Just across mismatch boundary
    ],
)
def test_same_or_unknown_currency_boundary_values(left, right, expected):
    assert sc._same_or_unknown_currency(left, right) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("PT-1M", None),  # Below minimum boundary: negative pattern unsupported
        ("PT0M", 0),      # Minimum boundary
        ("PT1M", 1),      # Just above minimum boundary
        ("PT10H", 600),   # Typical boundary
    ],
)
def test_iso8601_to_minutes_boundary_values(value, expected):
    assert sc._iso8601_to_minutes(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("-1", None),    # Below minimum boundary
        ("0", 0),        # Minimum boundary
        ("1", 1),        # Just above minimum boundary
        ("2h 0m", 120),  # Typical boundary
    ],
)
def test_parse_runtime_to_minutes_boundary_values(value, expected):
    assert sc._parse_runtime_to_minutes(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("not-a-list", 0),  # Below valid-collection boundary
        ([], 0),             # Minimum boundary
        (["x"], 1),          # Just above minimum boundary
        (["x", "y"], 2),    # Typical boundary
    ],
)
def test_safe_list_len_boundary_values(value, expected):
    assert sc._safe_list_len(value) == expected


@pytest.mark.parametrize(
    "rows, expected_len",
    [
        ([], 0),  # Minimum boundary
        ([{"Movie Link": "https://www.imdb.com/title/tt1/", "Title": "One"}], 1),  # Just above minimum
        (
            [
                {"Movie Link": "https://www.imdb.com/title/tt1/", "Title": "One"},
                {"Movie Link": "https://www.imdb.com/title/tt1/", "Title": "One-New"},
            ],
            1,
        ),  # Duplicate compression boundary
    ],
)
def test_links_from_df_row_count_boundary_values(rows, expected_len):
    df = pd.DataFrame(rows)
    out = sc._links_from_df(df)

    assert len(out) == expected_len


@pytest.mark.parametrize(
    "existing_rows, new_rows, expected_len",
    [
        ([], [], 0),  # Minimum boundary
        ([], [{"link": "https://www.imdb.com/title/tt1/"}], 1),  # Just above minimum
        (
            [{"link": "https://www.imdb.com/title/tt1/", "budget": "$1"}],
            [{"link": "https://www.imdb.com/title/tt1/", "budget": "$2"}],
            1,
        ),  # Duplicate replacement boundary
    ],
)
def test_combine_advanced_row_boundary_values(existing_rows, new_rows, expected_len):
    existing_df = pd.DataFrame(existing_rows)
    out = sc._combine_advanced(existing_df, new_rows)

    assert len(out) == expected_len


@pytest.mark.parametrize(
    "rows, expected_count",
    [
        ([], 0),  # Minimum boundary
        ([{"link": "https://www.imdb.com/title/tt1/", "attempt_count": "0"}], 1),  # Just above minimum
        (
            [
                {"link": "https://www.imdb.com/title/tt1/", "attempt_count": "-1"},
                {"link": "https://www.imdb.com/title/tt2/", "attempt_count": "bad"},
            ],
            2,
        ),  # Invalid numeric boundary handling
    ],
)
def test_status_records_row_boundary_values(rows, expected_count):
    status_df = pd.DataFrame(rows)
    out = sc._status_records(status_df)

    assert len(out) == expected_count


@pytest.mark.parametrize(
    "values, expected_valid_count",
    [
        ([], 0),  # Minimum boundary
        (["2020-01-01"], 1),  # Just above minimum boundary
        (["2020-01-01", "invalid"], 1),  # Mixed boundary
    ],
)
def test_parse_release_dates_series_length_boundary_values(values, expected_valid_count):
    series = pd.Series(values)
    out = sc._parse_release_dates(series)

    assert len(out) == len(values)
    assert out.notna().sum() == expected_valid_count
