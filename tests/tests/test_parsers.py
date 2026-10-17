import json
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

import scrapping as sc


@pytest.mark.parametrize(
    "html, expected",
    [
        (
            "<li data-testid='title-boxoffice-budget'><span class='ipc-metadata-list-item__list-content-item'>$10M</span></li>",
            "$10M",
        ),
        ("<div></div>", None),
    ],
)
def test_text_in_extracts_metadata_value(html, expected):
    soup = BeautifulSoup(html, "lxml")
    assert sc._text_in(soup, "title-boxoffice-budget") == expected


def test_extract_principal_credits_reads_directors_and_writers():
    html = """
    <ul>
      <li class='ipc-metadata-list__item'>
        <span class='ipc-metadata-list-item__label'>Director</span>
        <a class='ipc-metadata-list-item__list-content-item'>Dir One</a>
      </li>
      <li class='ipc-metadata-list__item'>
        <span class='ipc-metadata-list-item__label'>Writers</span>
        <a class='ipc-metadata-list-item__list-content-item'>Writer One</a>
        <a class='ipc-metadata-list-item__list-content-item'>Writer Two</a>
      </li>
    </ul>
    """
    soup = BeautifulSoup(html, "lxml")

    result = sc._extract_principal_credits(soup)

    assert result["directors"] == ["Dir One"]
    assert result["writers"] == ["Writer One", "Writer Two"]


def test_extract_cast_returns_stars_and_characters():
    html = """
    <div data-testid='title-cast-item'>
      <a data-testid='title-cast-item__actor'>Actor One</a>
      <a data-testid='cast-item-characters-link'>Hero</a>
    </div>
    <div data-testid='title-cast-item'>
      <a data-testid='title-cast-item__actor'>Actor Two</a>
      <span data-testid='cast-item-characters-link'>Villain</span>
    </div>
    """
    soup = BeautifulSoup(html, "lxml")

    stars, characters = sc._extract_cast(soup)

    assert stars == ["Actor One", "Actor Two"]
    assert characters == ["Hero", "Villain"]


def test_extract_cast_returns_none_lists_when_missing():
    soup = BeautifulSoup("<div></div>", "lxml")
    stars, characters = sc._extract_cast(soup)

    assert stars is None
    assert characters is None


def test_extract_json_ld_reads_graph_movie_payload():
    payload = {
        "@graph": [
            {"@type": "Thing", "name": "ignored"},
            {
                "@type": ["Movie"],
                "aggregateRating": {"ratingValue": "8.2", "ratingCount": "1234"},
                "contentRating": "PG-13",
                "keywords": "adventure,space",
                "image": "https://img.example/poster.jpg",
                "director": [{"name": "Dir One"}],
                "creator": [{"name": "Writer One"}],
                "actor": [{"name": "Actor One"}, {"name": "Actor Two"}],
                "duration": "PT2H5M",
            },
        ]
    }
    html = f"<script type='application/ld+json'>{json.dumps(payload)}</script>"
    soup = BeautifulSoup(html, "lxml")

    result = sc._extract_json_ld(soup)

    assert result["json_ld_rating"] == "8.2"
    assert result["json_ld_vote_count"] == "1234"
    assert result["json_ld_content_rating"] == "PG-13"
    assert result["json_ld_runtime_minutes"] == 125
    assert result["json_ld_directors"] == ["Dir One"]
    assert result["json_ld_writers"] == ["Writer One"]
    assert result["json_ld_actors"] == ["Actor One", "Actor Two"]


def test_extract_json_ld_ignores_invalid_json_and_returns_defaults():
    html = "<script type='application/ld+json'>{invalid-json}</script>"
    soup = BeautifulSoup(html, "lxml")

    result = sc._extract_json_ld(soup)

    assert all(value is None for value in result.values())


def test_page_soup_loads_url_waits_and_parses(monkeypatch):
    seen = {}

    class FakeDriver:
        def __init__(self):
            self.page_source = "<html><body>ok</body></html>"

        def get(self, url):
            seen["url"] = url

    def fake_bs(source, parser):
        seen["source"] = source
        seen["parser"] = parser
        return "SENTINEL_SOUP"

    monkeypatch.setattr(sc, "_wait_for_page_ready", lambda driver: seen.setdefault("waited", driver is not None))
    monkeypatch.setattr(sc, "BeautifulSoup", fake_bs)

    out = sc._page_soup(FakeDriver(), "https://example.test")

    assert out == "SENTINEL_SOUP"
    assert seen["url"] == "https://example.test"
    assert seen["source"] == "<html><body>ok</body></html>"
    assert seen["parser"] == "lxml"
    assert seen["waited"] is True


def test_extract_parental_guide_parses_severity_labels(monkeypatch):
    text = "Sex & Nudity: Mild Violence & Gore Moderate Profanity: Severe"
    monkeypatch.setattr(sc, "_page_soup", lambda *_: SimpleNamespace(get_text=lambda *args, **kwargs: text))

    error_logger = SimpleNamespace(error=lambda *args, **kwargs: None)
    result = sc.extract_parental_guide(driver=object(), base_url="https://x/title/tt1/", error_logger=error_logger)

    assert result["sex_nudity_severity"] == "Mild"
    assert result["violence_gore_severity"] == "Moderate"
    assert result["profanity_severity"] == "Severe"


def test_extract_parental_guide_logs_errors(monkeypatch):
    class Logger:
        def __init__(self):
            self.called = False

        def error(self, *args, **kwargs):
            self.called = True

    monkeypatch.setattr(sc, "_page_soup", lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))
    logger = Logger()

    result = sc.extract_parental_guide(driver=object(), base_url="https://x/title/tt1/", error_logger=logger)

    assert logger.called is True
    assert set(result.keys()) == set(sc.PARENTAL_GUIDE_CATEGORIES.keys())
