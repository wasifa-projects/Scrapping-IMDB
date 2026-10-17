import pytest

import scrapping as sc


@pytest.mark.parametrize(
    "value, keep_query, expected",
    [
        (None, True, None),
        ("/title/tt1234567/?ref_=tt_mv_close", True, "https://www.imdb.com/title/tt1234567/?ref_=tt_mv_close"),
        ("/title/tt1234567/?ref_=tt_mv_close", False, "https://www.imdb.com/title/tt1234567/"),
        ("https://example.com/path?a=1", False, "https://example.com/path?a=1"),
    ],
)
def test_normalize_imdb_url_handles_relative_and_non_title_urls(value, keep_query, expected):
    assert sc._normalize_imdb_url(value, keep_query=keep_query) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.imdb.com/title/tt1234567/?ref_=abc", "https://www.imdb.com/title/tt1234567/"),
        ("/title/tt7654321/?x=y", "https://www.imdb.com/title/tt7654321/"),
        ("https://example.com/not-imdb", "https://example.com/not-imdb"),
        ("", ""),
    ],
)
def test_title_base_url_normalizes_to_canonical_title_root(url, expected):
    assert sc._title_base_url(url) == expected