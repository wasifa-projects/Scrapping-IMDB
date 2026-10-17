import json

import pandas as pd

import scrapping as sc


def test_status_records_parses_attempt_count_and_skips_missing_link():
    status_df = pd.DataFrame(
        [
            {"link": "https://www.imdb.com/title/tt1/", "title": "A", "attempt_count": "2", "status": "failed"},
            {"link": "https://www.imdb.com/title/tt2/", "title": "B", "attempt_count": "bad", "status": "pending"},
            {"link": None, "title": "C", "attempt_count": 1, "status": "pending"},
        ]
    )

    records = sc._status_records(status_df)

    assert set(records.keys()) == {"https://www.imdb.com/title/tt1/", "https://www.imdb.com/title/tt2/"}
    assert records["https://www.imdb.com/title/tt1/"]["attempt_count"] == 2
    assert records["https://www.imdb.com/title/tt2/"]["attempt_count"] == 0


def test_write_status_persists_expected_columns(monkeypatch):
    captured = {}

    def fake_write_csv(df, path):
        captured["df"] = df
        captured["path"] = path

    monkeypatch.setattr(sc, "write_csv_safely", fake_write_csv)

    records = {
        "https://www.imdb.com/title/tt1/": {
            "link": "https://www.imdb.com/title/tt1/",
            "title": "A",
            "status": "completed",
            "attempt_count": 1,
            "last_error": None,
            "last_attempted_at": "2026-01-01T00:00:00+00:00",
            "completed_at": "2026-01-01T00:00:01+00:00",
        }
    }

    sc._write_status("status.csv", records)

    assert captured["path"] == "status.csv"
    assert list(captured["df"].columns) == sc.STATUS_COLUMNS
    assert captured["df"].iloc[0]["status"] == "completed"


def test_append_attempt_log_writes_jsonl(tmp_path):
    log_path = tmp_path / "logs" / "attempts.jsonl"
    event = {"k": "v", "n": 1}

    sc.append_attempt_log(log_path, event)

    assert log_path.exists()
    line = log_path.read_text(encoding="utf-8").strip()
    assert json.loads(line) == event


def test_attempt_advanced_links_updates_status_and_logs(monkeypatch, fixed_now_values, fake_loggers):
    error_logger, _ = fake_loggers

    monkeypatch.setattr(sc, "now_iso", lambda: fixed_now_values[0])

    extracted = {
        "https://www.imdb.com/title/tt1/": {"link": "https://www.imdb.com/title/tt1/", "budget": "$1M"}
    }

    def fake_extract(driver, link, logger):
        if link.endswith("tt2/"):
            raise RuntimeError("network error")
        return extracted[link]

    events = []
    monkeypatch.setattr(sc, "_extract_advanced_row", fake_extract)
    monkeypatch.setattr(sc, "append_attempt_log", lambda path, event: events.append(event))

    links = [
        {"link": "https://www.imdb.com/title/tt1/", "title": "One"},
        {"link": "https://www.imdb.com/title/tt2/", "title": "Two"},
    ]
    statuses = {}

    rows, failures = sc._attempt_advanced_links(
        driver=object(),
        link_records=links,
        status_records=statuses,
        attempt_log_path="attempts.jsonl",
        error_logger=error_logger,
        phase="initial",
    )

    assert len(rows) == 1
    assert rows[0]["link"].endswith("tt1/")
    assert len(failures) == 1
    assert failures[0]["link"].endswith("tt2/")
    assert statuses["https://www.imdb.com/title/tt1/"]["status"] == "completed"
    assert statuses["https://www.imdb.com/title/tt2/"]["status"] == "failed"
    assert statuses["https://www.imdb.com/title/tt2/"]["attempt_count"] == 1
    assert len(events) == 2
    error_logger.error.assert_called_once()
