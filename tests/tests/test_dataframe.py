import pandas as pd

import scrapping as sc


def test_read_csv_or_empty_returns_empty_df_for_missing_file(tmp_path):
    path = tmp_path / "missing.csv"
    df = sc.read_csv_or_empty(path, ["a", "b"])

    assert list(df.columns) == ["a", "b"]
    assert df.empty


def test_read_csv_or_empty_adds_missing_columns(monkeypatch, tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("x\n1\n", encoding="utf-8")

    monkeypatch.setattr(sc.pd, "read_csv", lambda _: pd.DataFrame({"x": [1]}))
    df = sc.read_csv_or_empty(path, ["x", "y", "z"])

    assert list(df.columns) == ["x", "y", "z"]
    assert df.loc[0, "y"] is None
    assert df.loc[0, "z"] is None


def test_write_csv_safely_writes_temp_and_replaces_target(tmp_path):
    target = tmp_path / "nested" / "out.csv"
    df = pd.DataFrame([{"a": 1}, {"a": 2}])

    sc.write_csv_safely(df, target)

    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert "a" in content
    assert "1" in content
    assert "2" in content


def test_links_from_df_prefers_movie_link_and_deduplicates_last_record():
    links_df = pd.DataFrame(
        [
            {"Movie Link": "https://www.imdb.com/title/tt1/", "Title": "Old"},
            {"Movie Link": "https://www.imdb.com/title/tt2/", "Title": "Two"},
            {"Movie Link": "https://www.imdb.com/title/tt1/", "Title": "New"},
            {"Movie Link": None, "Title": "Missing"},
        ]
    )

    result = sc._links_from_df(links_df)

    assert result == [
        {"link": "https://www.imdb.com/title/tt1/", "title": "New"},
        {"link": "https://www.imdb.com/title/tt2/", "title": "Two"},
    ]


def test_links_from_df_supports_lowercase_link_column():
    links_df = pd.DataFrame(
        [
            {"link": "https://www.imdb.com/title/tt1/", "title": "One"},
            {"link": "https://www.imdb.com/title/tt2/", "title": "Two"},
        ]
    )

    result = sc._links_from_df(links_df)

    assert result == [
        {"link": "https://www.imdb.com/title/tt1/", "title": "One"},
        {"link": "https://www.imdb.com/title/tt2/", "title": "Two"},
    ]


def test_links_from_df_returns_empty_when_link_column_missing():
    df = pd.DataFrame([{"foo": 1}])
    assert sc._links_from_df(df) == []


def test_combine_advanced_appends_rows_and_keeps_latest_duplicate():
    existing = pd.DataFrame(
        [
            {"link": "https://www.imdb.com/title/tt1/", "budget": "$1M"},
            {"link": "https://www.imdb.com/title/tt2/", "budget": "$2M"},
        ]
    )
    new_rows = [
        {"link": "https://www.imdb.com/title/tt1/", "budget": "$3M"},
        {"link": "https://www.imdb.com/title/tt3/", "budget": "$4M"},
    ]

    combined = sc._combine_advanced(existing, new_rows)

    tt1 = combined[combined["link"] == "https://www.imdb.com/title/tt1/"]
    assert len(tt1) == 1
    assert tt1.iloc[0]["budget"] == "$3M"
    assert set(combined["link"].dropna()) == {
        "https://www.imdb.com/title/tt1/",
        "https://www.imdb.com/title/tt2/",
        "https://www.imdb.com/title/tt3/",
    }
    assert list(combined.columns) == sc.ADVANCED_COLUMNS
