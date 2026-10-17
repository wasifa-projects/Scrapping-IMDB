from types import SimpleNamespace

import pandas as pd
import pytest
from bs4 import BeautifulSoup

import scrapping as sc


@pytest.mark.parametrize(
    "html, expected",
    [
        ("<span>  Hello   World  </span>", "Hello   World"),
        ("<span>\n A <b>bold</b> move \t</span>", "A bold move"),
    ],
)
def test_clean_text_normalizes_node_text(html, expected):
    node = BeautifulSoup(html, "lxml").find("span")
    assert sc.clean_text(node) == expected


def test_clean_text_returns_none_for_missing_element():
    assert sc.clean_text(None) is None


@pytest.mark.parametrize(
    "items, expected",
    [
        ([], (None, None, None)),
        (["1924"], ("1924", None, None)),
        (["1924", "1h 30m"], ("1924", "1h 30m", None)),
        (["1924", "1h 30m", "PG"], ("1924", "1h 30m", "PG")),
    ],
)
def test_extract_listing_metadata_handles_missing_values(items, expected):
    lis = "".join(f"<li class='ipc-inline-list__item'>{value}</li>" for value in items)
    html = (
        "<li><ul class='dli-title-metadata'>"
        f"{lis}"
        "</ul></li>"
    )
    film = BeautifulSoup(html, "lxml").find("li")

    assert sc.extract_listing_metadata(film) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, []),
        ("x", ["x"]),
        ([1, 2], [1, 2]),
    ],
)
def test_as_list_converts_values(raw, expected):
    assert sc._as_list(raw) == expected


def test_persons_extracts_only_named_people():
    payload = [
        {"name": "Alice"},
        {"name": "Bob"},
        {"id": 10},
        "not-a-dict",
        {"name": ""},
    ]

    assert sc._persons(payload) == ["Alice", "Bob"]


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, None),
        (float("nan"), None),
        (123, "123"),
        ("abc", "abc"),
    ],
)
def test_string_or_none_handles_none_nan_and_values(value, expected):
    assert sc._string_or_none(value) == expected


@pytest.mark.parametrize(
    "html, expected",
    [
        ("<span class='ipc-rating-star--voteCount'>(1,234)</span>", "1,234"),
        ("<span class='ipc-rating-star--voteCount'>1,234</span>", "1,234"),
        ("", None),
    ],
)
def test_normalize_votes_trims_wrapping_parentheses(html, expected):
    element = BeautifulSoup(html, "lxml").find("span") if html else None
    assert sc._normalize_votes(element) == expected


def test_create_edge_driver_uses_options_and_maximize(monkeypatch):
    class FakeOptions:
        def __init__(self):
            self.arguments = []
            self.experimental = {}

        def add_argument(self, arg):
            self.arguments.append(arg)

        def add_experimental_option(self, key, value):
            self.experimental[key] = value

    class FakeDriver:
        def __init__(self):
            self.maximized = False

        def maximize_window(self):
            self.maximized = True

        def set_window_size(self, *_):
            raise AssertionError("set_window_size should not be called")

    created = {}

    def fake_service(*, executable_path):
        created["service_path"] = executable_path
        return SimpleNamespace(executable_path=executable_path)

    def fake_edge(*, service, options):
        created["service"] = service
        created["options"] = options
        return FakeDriver()

    monkeypatch.setattr(sc.webdriver, "EdgeOptions", FakeOptions)
    monkeypatch.setattr(sc, "Service", fake_service)
    monkeypatch.setattr(sc.webdriver, "Edge", fake_edge)

    driver = sc.create_edge_driver()

    assert driver.maximized is True
    assert created["service_path"].endswith("edgedriver.exe")
    assert "--lang=en-US" in created["options"].arguments
    assert "--disable-gpu" in created["options"].arguments
    assert created["options"].experimental["excludeSwitches"] == ["enable-automation", "enable-logging"]


def test_create_edge_driver_falls_back_to_window_size(monkeypatch):
    class FakeOptions:
        def add_argument(self, _):
            return None

        def add_experimental_option(self, *_):
            return None

    class FakeDriver:
        def __init__(self):
            self.window_size = None

        def maximize_window(self):
            raise RuntimeError("cannot maximize")

        def set_window_size(self, width, height):
            self.window_size = (width, height)

    monkeypatch.setattr(sc.webdriver, "EdgeOptions", FakeOptions)
    monkeypatch.setattr(sc, "Service", lambda **_: object())
    monkeypatch.setattr(sc.webdriver, "Edge", lambda **_: FakeDriver())

    driver = sc.create_edge_driver()

    assert driver.window_size == (1920, 1080)


def test_wait_for_page_ready_uses_footer_and_fallback(monkeypatch):
    calls = []

    class FakeWait:
        def __init__(self, driver, timeout):
            self.driver = driver
            self.timeout = timeout

        def until(self, condition):
            calls.append(condition)
            if condition == "visibility-footer":
                raise RuntimeError("footer missing")
            if callable(condition):
                assert condition(self.driver) is True
            return True

    fake_driver = SimpleNamespace(execute_script=lambda script: "complete")

    monkeypatch.setattr(sc, "WebDriverWait", FakeWait)
    monkeypatch.setattr(sc.EC, "visibility_of_element_located", lambda _: "visibility-footer")
    monkeypatch.setattr(sc.EC, "presence_of_element_located", lambda _: "presence-body")
    monkeypatch.setattr(sc.time, "sleep", lambda _: None)

    sc._wait_for_page_ready(fake_driver, timeout=1, min_pause=0, wait_for_footer=True)

    assert "visibility-footer" in calls
    assert calls.count("presence-body") >= 1


def test_now_iso_is_utc_and_iso8601():
    value = sc.now_iso()
    parsed = pd.Timestamp(value)

    assert parsed.tz is not None
    assert value.endswith("+00:00")
