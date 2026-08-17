"""Tests for newvelles.feed.health — per-feed fetch health records."""

import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import feedparser
import jsonschema

from newvelles.feed.health import (
    FEED_HEALTH_VERSION,
    build_health_doc,
    build_health_record,
    emit_feed_health,
    error_health_record,
    health_summary_lines,
)


def _feed(status=200, entries=None, bozo=False, bozo_exception=None, href=None):
    d = feedparser.FeedParserDict()
    d["status"] = status
    d["entries"] = entries if entries is not None else []
    d["bozo"] = bozo
    if bozo_exception is not None:
        d["bozo_exception"] = bozo_exception
    if href is not None:
        d["href"] = href
    return d


def _entry(published):
    e = feedparser.FeedParserDict()
    e["title"] = "t"
    e["link"] = "https://example.com/a"
    e["published"] = published
    return e


class TestBuildHealthRecord:
    def test_healthy_feed_record(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        feed = _feed(entries=[_entry(yesterday)], href="https://example.com/rss")
        r = build_health_record("https://example.com/rss", feed, latency_ms=120)
        assert r["url"] == "https://example.com/rss"
        assert r["http_status"] == 200
        assert r["resolved_url"] == "https://example.com/rss"
        assert r["entry_count"] == 1
        assert r["newest_entry_age_days"] == 1
        assert r["latency_ms"] == 120
        assert r["error"] is None
        assert r["ok"] is True

    def test_http_error_feed_is_not_ok(self):
        r = build_health_record("https://example.com/rss", _feed(status=404), 50)
        assert r["http_status"] == 404
        assert r["ok"] is False

    def test_empty_feed_is_not_ok_even_with_200(self):
        r = build_health_record("https://example.com/rss", _feed(status=200), 50)
        assert r["entry_count"] == 0
        assert r["ok"] is False

    def test_bozo_with_entries_is_still_ok(self):
        """feedparser flags minor XML issues as bozo; entries still parsed → healthy."""
        feed = _feed(entries=[_entry(date.today().isoformat())], bozo=True,
                     bozo_exception=ValueError("not well-formed"))
        r = build_health_record("u", feed, 10)
        assert r["ok"] is True
        assert r["bozo"] is True
        assert "not well-formed" in r["error"]

    def test_missing_status_is_none_and_ok_depends_on_entries(self):
        """Local files / some failures produce results with no HTTP status."""
        feed = _feed(entries=[_entry(date.today().isoformat())])
        del feed["status"]
        r = build_health_record("u", feed, 10)
        assert r["http_status"] is None
        assert r["ok"] is True

    def test_unparseable_dates_yield_none_age(self):
        feed = _feed(entries=[_entry("not a date")])
        r = build_health_record("u", feed, 10)
        assert r["newest_entry_age_days"] is None
        assert r["ok"] is True

    def test_error_health_record(self):
        r = error_health_record("u", RuntimeError("boom"), 5000)
        assert r["ok"] is False
        assert r["entry_count"] == 0
        assert "boom" in r["error"]
        assert r["latency_ms"] == 5000


class TestHealthDocAndSummary:
    def test_build_health_doc_counts(self):
        records = [
            build_health_record("a", _feed(entries=[_entry(date.today().isoformat())]), 10),
            build_health_record("b", _feed(status=404), 10),
        ]
        doc = build_health_doc(records)
        assert doc["version"] == FEED_HEALTH_VERSION
        assert doc["feed_count"] == 2
        assert doc["ok_count"] == 1
        assert doc["failed_count"] == 1
        assert doc["feeds"] == records
        assert "datetime" in doc

    def test_summary_lines_all_ok_is_single_line(self):
        records = [
            build_health_record("a", _feed(entries=[_entry(date.today().isoformat())]), 10)
        ]
        lines = health_summary_lines(records)
        assert len(lines) == 1
        assert "1/1" in lines[0]

    def test_summary_lines_lists_failing_urls(self):
        records = [
            build_health_record("https://ok.example/rss",
                                _feed(entries=[_entry(date.today().isoformat())]), 10),
            build_health_record("https://dead.example/rss", _feed(status=410), 10),
        ]
        lines = health_summary_lines(records)
        assert len(lines) == 2
        assert "1/2" in lines[0]
        assert "https://dead.example/rss" in lines[1]
        assert "410" in lines[1]


class TestEmitFeedHealth:
    def _records(self):
        return [error_health_record("https://dead.example/rss", RuntimeError("x"), 1)]

    @patch("newvelles.feed.health.upload_to_s3")
    def test_no_upload_outside_lambda(self, mock_upload, monkeypatch, capsys):
        monkeypatch.delenv("AWS_LAMBDA", raising=False)
        emit_feed_health(self._records())
        mock_upload.assert_not_called()
        assert "0/1" in capsys.readouterr().out

    @patch("newvelles.feed.health.upload_to_s3")
    def test_upload_in_lambda_to_private_bucket(self, mock_upload, monkeypatch):
        monkeypatch.setenv("AWS_LAMBDA", "true")
        monkeypatch.setenv("AWS_S3_BUCKET", "newvelles-qa-bucket")
        emit_feed_health(self._records())
        kwargs = mock_upload.call_args.kwargs
        assert kwargs["bucket_name"] == "newvelles-qa-bucket"
        assert kwargs["file_name"].startswith("feed_health/feed_health_")
        doc = json.loads(kwargs["string_byte"])
        assert doc["feed_count"] == 1 and doc["failed_count"] == 1

    @patch("newvelles.feed.health.upload_to_s3", side_effect=RuntimeError("s3 down"))
    def test_upload_failure_never_raises(self, mock_upload, monkeypatch, capsys):
        monkeypatch.setenv("AWS_LAMBDA", "true")
        emit_feed_health(self._records())  # must not raise
        assert "run continues" in capsys.readouterr().out


def test_health_doc_matches_schema():
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas" / "feed_health_schema.json").read_text()
    )
    records = [
        build_health_record("https://ok.example/rss",
                            _feed(entries=[_entry(date.today().isoformat())],
                                  href="https://ok.example/rss"), 10),
        error_health_record("https://dead.example/rss", RuntimeError("x"), 5),
    ]
    jsonschema.validate(build_health_doc(records), schema)
