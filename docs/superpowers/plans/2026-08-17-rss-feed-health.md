# RSS Feed Health (logging → deploy → review skill → feed cleanup) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record per-feed fetch health every run, deploy it to production and force runs to accumulate data, then build and execute an `rss-feed-review` skill that confirms dead feeds, finds replacements, deactivates the unfixable ones, and proposes net-new sources.

**Architecture:** A new dependency-free module `newvelles/feed/health.py` builds one health record per feed from the feedparser result (status, entries, newest-article age, latency, error). `parse_feed()` gains an optional collector list; `build_data_from_rss_feeds_list()` passes it and emits: summary lines to stdout (CloudWatch) always, and a `feed_health/feed_health_<ts>.json` object to the **private** bucket only when running in Lambda (`AWS_LAMBDA=true`). A health-upload failure must never break the news run. The review is a Claude Code skill plus one actual execution producing a feed-list PR.

**Tech Stack:** Python 3.12, feedparser, boto3 (existing `upload_to_s3`), pytest, jsonschema, aws CLI + Makefile deploy targets, gh CLI.

**Spec:** `docs/NEXT_STEPS.md` §"1. RSS feed health" + user directive 2026-08-17 (forced prod runs after logging; confirm broken feeds; search sites for updated feed URLs; deactivate unfixable feeds; scan for complementary new sources).

## Global Constraints

- Functional style, no classes where avoidable; lowercase_snake file names (CLAUDE.md).
- Only mock external dependencies (network, S3); use real `feedparser.FeedParserDict` objects in tests, not `Mock` attribute soup.
- Health logging must be dependency-free (no new packages).
- The health path must be fail-open: any exception building/uploading health data is printed and swallowed; the news run continues.
- No new env vars (reuse `AWS_LAMBDA`, `AWS_S3_BUCKET`); if any is added, document in `docs/ENVIRONMENT.md`.
- Private bucket only for `feed_health/` objects (prod: `newvelles-data-bucket`, QA: `newvelles-qa-bucket`).
- Retired feeds stay in `data/sources.json` (needed for the historical backfill workstream); deactivation means removal from `data/rss_source.txt` only, with the URL recorded in `data/rss_retired.txt`.
- `test/test_utils_sources.py` must pass after any feed-list change (every active feed mapped).

---

### Task 1: `newvelles/feed/health.py` — pure record/doc/summary builders

**Files:**
- Create: `newvelles/feed/health.py`
- Test: `test/test_feed_health.py`

**Interfaces:**
- Produces: `build_health_record(url: str, feed, latency_ms: int) -> dict`, `error_health_record(url: str, error: Exception, latency_ms: int) -> dict`, `build_health_doc(records: list) -> dict`, `health_summary_lines(records: list) -> list[str]`, constant `FEED_HEALTH_VERSION = "0.1.0"`. Record keys: `url, http_status, resolved_url, entry_count, newest_entry_age_days, latency_ms, bozo, error, ok`.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for newvelles.feed.health — per-feed fetch health records."""

from datetime import date, timedelta

import feedparser

from newvelles.feed.health import (
    FEED_HEALTH_VERSION,
    build_health_doc,
    build_health_record,
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


def test_healthy_feed_record():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    feed = _feed(entries=[_entry(yesterday)], href="https://example.com/rss")
    r = build_health_record("https://example.com/rss", feed, latency_ms=120)
    assert r["url"] == "https://example.com/rss"
    assert r["http_status"] == 200
    assert r["entry_count"] == 1
    assert r["newest_entry_age_days"] == 1
    assert r["latency_ms"] == 120
    assert r["error"] is None
    assert r["ok"] is True


def test_http_error_feed_is_not_ok():
    r = build_health_record("https://example.com/rss", _feed(status=404), 50)
    assert r["http_status"] == 404
    assert r["ok"] is False


def test_empty_feed_is_not_ok_even_with_200():
    r = build_health_record("https://example.com/rss", _feed(status=200), 50)
    assert r["entry_count"] == 0
    assert r["ok"] is False


def test_bozo_with_entries_is_still_ok():
    """feedparser flags minor XML issues as bozo; entries still parsed → healthy."""
    feed = _feed(entries=[_entry(date.today().isoformat())], bozo=True,
                 bozo_exception=ValueError("not well-formed"))
    r = build_health_record("u", feed, 10)
    assert r["ok"] is True
    assert r["bozo"] is True
    assert "not well-formed" in r["error"]


def test_missing_status_is_none_and_ok_depends_on_entries():
    """Local files / some failures produce results with no HTTP status."""
    feed = _feed(entries=[_entry(date.today().isoformat())])
    del feed["status"]
    r = build_health_record("u", feed, 10)
    assert r["http_status"] is None
    assert r["ok"] is True


def test_unparseable_dates_yield_none_age():
    feed = _feed(entries=[_entry("not a date")])
    r = build_health_record("u", feed, 10)
    assert r["newest_entry_age_days"] is None
    assert r["ok"] is True


def test_error_health_record():
    r = error_health_record("u", RuntimeError("boom"), 5000)
    assert r["ok"] is False
    assert r["entry_count"] == 0
    assert "boom" in r["error"]
    assert r["latency_ms"] == 5000


def test_build_health_doc_counts():
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


def test_summary_lines_all_ok_is_single_line():
    records = [build_health_record("a", _feed(entries=[_entry(date.today().isoformat())]), 10)]
    lines = health_summary_lines(records)
    assert len(lines) == 1
    assert "1/1" in lines[0]


def test_summary_lines_lists_failing_urls():
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .python/newvelles/bin/activate && pytest test/test_feed_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'newvelles.feed.health'`

- [ ] **Step 3: Write the implementation**

```python
"""Per-feed fetch/parse health records emitted each run (docs/NEXT_STEPS.md §1)."""
import json
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from dateutil import parser as date_parser

from newvelles.config import config
from newvelles.utils.s3 import upload_to_s3

FEED_HEALTH_VERSION = "0.1.0"

_CONFIG = config()


def _feed_attr(feed: Any, name: str, default: Any = None) -> Any:
    try:
        value = getattr(feed, name)
    except AttributeError:
        return default
    return default if value is None else value


def _newest_entry_age_days(entries: List[Any]) -> Optional[int]:
    ages = []
    for entry in entries:
        published = _feed_attr(entry, "published")
        if not published:
            continue
        try:
            ages.append((date.today() - date_parser.parse(published).date()).days)
        except (ValueError, OverflowError, TypeError):
            continue
    return min(ages) if ages else None


def build_health_record(url: str, feed: Any, latency_ms: int) -> Dict[str, Any]:
    entries = list(_feed_attr(feed, "entries", []) or [])
    bozo_exception = _feed_attr(feed, "bozo_exception")
    record = {
        "url": url,
        "http_status": _feed_attr(feed, "status"),
        "resolved_url": _feed_attr(feed, "href"),
        "entry_count": len(entries),
        "newest_entry_age_days": _newest_entry_age_days(entries),
        "latency_ms": latency_ms,
        "bozo": bool(_feed_attr(feed, "bozo", False)),
        "error": str(bozo_exception) if bozo_exception else None,
    }
    record["ok"] = _is_ok(record)
    return record


def error_health_record(url: str, error: Exception, latency_ms: int) -> Dict[str, Any]:
    return {
        "url": url,
        "http_status": None,
        "resolved_url": None,
        "entry_count": 0,
        "newest_entry_age_days": None,
        "latency_ms": latency_ms,
        "bozo": True,
        "error": str(error),
        "ok": False,
    }


def _is_ok(record: Dict[str, Any]) -> bool:
    status = record["http_status"]
    if status is not None and status >= 400:
        return False
    return record["entry_count"] > 0


def build_health_doc(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok_count = sum(1 for r in records if r["ok"])
    return {
        "version": FEED_HEALTH_VERSION,
        "datetime": datetime.now().isoformat(timespec="seconds"),
        "feed_count": len(records),
        "ok_count": ok_count,
        "failed_count": len(records) - ok_count,
        "feeds": records,
    }


def health_summary_lines(records: List[Dict[str, Any]]) -> List[str]:
    failed = [r for r in records if not r["ok"]]
    lines = [
        f"📡 Feed health: {len(records) - len(failed)}/{len(records)} feeds ok, "
        f"{len(failed)} failed"
    ]
    if failed:
        details = ", ".join(
            f"{r['url']} (status={r['http_status']}, entries={r['entry_count']})"
            for r in failed
        )
        lines.append(f"📡 Failing feeds: {details}")
    return lines


def emit_feed_health(records: List[Dict[str, Any]]) -> None:
    """Print CloudWatch summary lines; upload the full doc when in Lambda.

    Fail-open by design: feed health must never break a news run.
    """
    try:
        for line in health_summary_lines(records):
            print(line)
        if os.getenv("AWS_LAMBDA") != "true":
            return
        doc = build_health_doc(records)
        bucket = os.getenv(
            "AWS_S3_BUCKET", _CONFIG.get("S3", "bucket", fallback="newvelles-data-bucket")
        )
        upload_to_s3(
            bucket_name=bucket,
            file_name=f"feed_health/feed_health_{doc['datetime']}.json",
            string_byte=json.dumps(doc).encode("utf-8"),
        )
    except Exception as e:  # pylint: disable=broad-except
        print(f"⚠️ Feed health emit failed (run continues): {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest test/test_feed_health.py -v`
Expected: 11 PASS

- [ ] **Step 5: Commit**

```bash
git add newvelles/feed/health.py test/test_feed_health.py
git commit -m "feat: feed health records module (build/summarize/emit)"
```

---

### Task 2: `parse_feed()` collects health records

**Files:**
- Modify: `newvelles/feed/parser.py`
- Test: `test/test_feed_parser.py` (append)

**Interfaces:**
- Consumes: `build_health_record`, `error_health_record` from Task 1.
- Produces: `parse_feed(feed_paths: List[str], health: Optional[List[dict]] = None)` — same generator semantics; when `health` is a list, exactly one record is appended per feed path (success, empty, or exception).

- [ ] **Step 1: Write the failing tests** (append to `test/test_feed_parser.py`)

```python
class TestParseFeedHealth:
    """parse_feed appends one health record per feed path when given a collector."""

    @patch("newvelles.feed.parser.feedparser.parse")
    def test_health_record_per_feed(self, mock_parse):
        import feedparser as fp

        good = fp.FeedParserDict()
        good["status"] = 200
        good["feed"] = fp.FeedParserDict()
        good["feed"]["title"] = "Good Feed"
        entry = fp.FeedParserDict()
        entry["title"] = "A"
        entry["link"] = "https://example.com/a"
        entry["published"] = "2026-08-16"
        good["entries"] = [entry]

        empty = fp.FeedParserDict()
        empty["status"] = 404
        empty["entries"] = []

        mock_parse.side_effect = [good, empty]
        health = []
        results = list(parse_feed(["https://good.example/rss", "https://dead.example/rss"],
                                  health=health))

        assert len(results) == 1  # empty feed yields no entries
        assert [r["url"] for r in health] == ["https://good.example/rss",
                                              "https://dead.example/rss"]
        assert health[0]["ok"] is True
        assert health[1]["ok"] is False
        assert health[1]["http_status"] == 404

    @patch("newvelles.feed.parser.feedparser.parse")
    def test_health_record_on_exception(self, mock_parse):
        mock_parse.side_effect = RuntimeError("connection reset")
        health = []
        results = list(parse_feed(["https://broken.example/rss"], health=health))
        assert results == []
        assert len(health) == 1
        assert health[0]["ok"] is False
        assert "connection reset" in health[0]["error"]

    @patch("newvelles.feed.parser.feedparser.parse")
    def test_no_collector_keeps_old_behavior(self, mock_parse):
        mock_parse.side_effect = RuntimeError("boom")
        assert list(parse_feed(["https://broken.example/rss"])) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest test/test_feed_parser.py -v -k Health`
Expected: FAIL with `TypeError: parse_feed() got an unexpected keyword argument 'health'`

- [ ] **Step 3: Modify `parse_feed`**

Replace the function in `newvelles/feed/parser.py` (keep `_get_feed_title` unchanged; add imports `import time`, `from typing import Dict, Optional`, and `from newvelles.feed.health import build_health_record, error_health_record`):

```python
def parse_feed(
    feed_paths: List[str],
    health: Optional[List[Dict[str, Any]]] = None,
) -> Iterable[Tuple[str, Any]]:  # pragma: no cover
    """
    Use the feedparser package to load data from a particular RSS feed path.

    When `health` is a list, one fetch-health record is appended per feed path.
    """
    for feed_path in feed_paths:
        started = time.monotonic()
        try:
            feed = feedparser.parse(feed_path)
            latency_ms = int((time.monotonic() - started) * 1000)
            if health is not None:
                health.append(build_health_record(feed_path, feed, latency_ms))

            feed_title = _get_feed_title(feed, feed_path)

            if not hasattr(feed, "entries") or len(feed.entries) == 0:
                logger.warning(f"No entries found for feed: {feed_path}")
                continue

            if DEBUG:
                print(f"{feed_title} entries: {len(feed.entries)}")

            for entry in feed.entries:
                if not hasattr(entry, "title") or not hasattr(entry, "link"):
                    continue
                yield (feed_title, entry)

        except Exception as e:
            if health is not None:
                latency_ms = int((time.monotonic() - started) * 1000)
                health.append(error_health_record(feed_path, e, latency_ms))
            logger.exception(f"Feed path is raising exceptions: {feed_path}\nException: {str(e)}")
```

Note: remove the `# pragma: no cover` marker since the function is now covered by tests.

- [ ] **Step 4: Run the whole parser test file (old + new)**

Run: `pytest test/test_feed_parser.py -v`
Expected: all PASS (existing tests must not regress)

- [ ] **Step 5: Commit**

```bash
git add newvelles/feed/parser.py test/test_feed_parser.py
git commit -m "feat: parse_feed collects per-feed health records"
```

---

### Task 3: wire health into `build_data_from_rss_feeds_list` + blank-line guard

**Files:**
- Modify: `newvelles/feed/load.py`
- Test: `test/test_feed_load.py` (append), `test/test_feed_health.py` (append emit tests)

**Interfaces:**
- Consumes: `parse_feed(..., health=...)` (Task 2), `emit_feed_health` (Task 1).
- Produces: unchanged signature `build_data_from_rss_feeds_list(rss_list, log=True)`; when `log=True` it now also calls `emit_feed_health(records)`.

- [ ] **Step 1: Write the failing tests**

Append to `test/test_feed_load.py`:

```python
class TestFeedHealthWiring:
    @patch("newvelles.feed.load.emit_feed_health")
    @patch("newvelles.feed.load.log_entries")
    @patch("newvelles.feed.load.parse_feed")
    def test_health_emitted_when_logging(self, mock_parse, mock_log, mock_emit):
        def fake_parse(rss_list, health=None):
            if health is not None:
                health.append({"url": rss_list[0], "ok": False})
            return iter([])

        mock_parse.side_effect = fake_parse
        build_data_from_rss_feeds_list(["https://dead.example/rss"], log=True)
        mock_emit.assert_called_once_with([{"url": "https://dead.example/rss", "ok": False}])

    @patch("newvelles.feed.load.emit_feed_health")
    @patch("newvelles.feed.load.parse_feed")
    def test_health_not_emitted_when_log_false(self, mock_parse, mock_emit):
        mock_parse.side_effect = lambda rss_list, health=None: iter([])
        build_data_from_rss_feeds_list(["https://a.example/rss"], log=False)
        mock_emit.assert_not_called()


def test_load_rss_skips_blank_lines(tmp_path):
    rss_file = tmp_path / "rss.txt"
    rss_file.write_text("https://a.example/rss\n\nhttps://b.example/rss\n")
    from newvelles.feed.load import load_rss
    assert list(load_rss(str(rss_file))) == ["https://a.example/rss",
                                             "https://b.example/rss"]
```

Append to `test/test_feed_health.py` (emit gating — mock only the S3 boundary):

```python
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
```

(add `import json` and the `patch`/`emit_feed_health` imports at the top of the test file; `monkeypatch` and `capsys` are pytest fixtures and compose fine with `@patch`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest test/test_feed_load.py -k "Health or blank" test/test_feed_health.py -v`
Expected: wiring tests FAIL (`emit_feed_health` not imported in load.py; blank lines not skipped); emit tests PASS or FAIL depending on Task 1 (they should PASS — if so, only the load.py wiring is new).

- [ ] **Step 3: Modify `newvelles/feed/load.py`**

- Add import: `from newvelles.feed.health import emit_feed_health`
- In `load_rss`, replace the loop body with:

```python
        for line in f.readlines():
            stripped = line.strip()
            if stripped:
                yield stripped
```

(also drop the `# pragma: no cover` on `load_rss` — it now has a test)

- In `build_data_from_rss_feeds_list`, collect and emit:

```python
def build_data_from_rss_feeds_list(rss_list: List[str], log: bool = True) -> Dict[str, NewsEntry]:
    title_data = {}
    news_data: Dict[str, Any] = defaultdict(list)
    health_records: List[Dict[str, Any]] = []
    for feed_title, entry in parse_feed(rss_list, health=health_records):
        ...  # existing body unchanged
    if log:
        log_entries(title_data, news_data)
        emit_feed_health(health_records)
    return title_data
```

- [ ] **Step 4: Run the full unit suite**

Run: `pytest test/test_feed_load.py test/test_feed_health.py test/test_feed_parser.py test/test_handler.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add newvelles/feed/load.py test/test_feed_load.py test/test_feed_health.py
git commit -m "feat: emit feed_health.json per run (private bucket) + CloudWatch summary"
```

---

### Task 4: schema + docs

**Files:**
- Create: `schemas/feed_health_schema.json`
- Modify: `test/test_feed_health.py` (schema validation test), `CLAUDE.md` (data-flow + key-files mentions), `docs/NEXT_STEPS.md` (mark step 1 done)

**Interfaces:**
- Consumes: `build_health_doc` (Task 1).
- Produces: `schemas/feed_health_schema.json` used by the review skill and future validation.

- [ ] **Step 1: Write the failing schema test** (append to `test/test_feed_health.py`)

```python
def test_health_doc_matches_schema():
    import jsonschema
    from pathlib import Path

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
```

- [ ] **Step 2: Run it — FAIL (schema file missing)**

Run: `pytest test/test_feed_health.py::test_health_doc_matches_schema -v`

- [ ] **Step 3: Write `schemas/feed_health_schema.json`**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Newvelles Feed Health",
  "type": "object",
  "required": ["version", "datetime", "feed_count", "ok_count", "failed_count", "feeds"],
  "properties": {
    "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
    "datetime": {"type": "string"},
    "feed_count": {"type": "integer", "minimum": 0},
    "ok_count": {"type": "integer", "minimum": 0},
    "failed_count": {"type": "integer", "minimum": 0},
    "feeds": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["url", "http_status", "entry_count", "newest_entry_age_days",
                     "latency_ms", "bozo", "error", "ok"],
        "properties": {
          "url": {"type": "string"},
          "http_status": {"type": ["integer", "null"]},
          "resolved_url": {"type": ["string", "null"]},
          "entry_count": {"type": "integer", "minimum": 0},
          "newest_entry_age_days": {"type": ["integer", "null"]},
          "latency_ms": {"type": "integer", "minimum": 0},
          "bozo": {"type": "boolean"},
          "error": {"type": ["string", "null"]},
          "ok": {"type": "boolean"}
        }
      }
    }
  }
}
```

- [ ] **Step 4: Run — PASS. Then update docs.**

- `CLAUDE.md`: in "Core Data Flow" step 1, add one line: feed fetches produce per-feed health records emitted as `feed_health/feed_health_<ts>.json` in the private bucket (`newvelles/feed/health.py`); add `schemas/feed_health_schema.json` to Key Files.
- `docs/NEXT_STEPS.md`: under workstream 1, mark Step 1 as **done** with the module path and S3 key layout.

- [ ] **Step 5: Full test suite + lint, then commit**

Run: `make test && make lint`
Expected: PASS (lint clean for changed files)

```bash
git add schemas/feed_health_schema.json test/test_feed_health.py CLAUDE.md docs/NEXT_STEPS.md
git commit -m "feat: feed_health schema + docs"
```

---

### Task 5: PR for the logging code, merge to main

**Files:** none new — branch/PR mechanics.

- [ ] **Step 1:** All previous commits should be on branch `feed-health-logging` (create it at Task 1 start: `git checkout -b feed-health-logging`).
- [ ] **Step 2:** Run `make test-local-quick` for an end-to-end sanity pass (uses local pipeline; expect feed-health summary lines in output).
- [ ] **Step 3:** `git push -u origin feed-health-logging` and open PR with `gh pr create` (title: "Feed health logging (workstream 1, step 1)"); body summarizes record fields, S3 layout, fail-open design. End body with the standard generation footer.
- [ ] **Step 4:** Merge with `gh pr merge --squash --delete-branch` once checks pass; `git checkout main && git pull`.

---

### Task 6: QA deploy + verification

- [ ] **Step 1:** `make qa-build` (writes `.last-qa-build.txt`)
- [ ] **Step 2:** `make qa-deploy`
- [ ] **Step 3:** `make qa-invoke` — watch output for the `📡 Feed health: N/13 feeds ok` line
- [ ] **Step 4:** Verify the object landed: `aws s3 ls s3://newvelles-qa-bucket/feed_health/` → exactly one new `feed_health_<ts>.json`; download it and validate against `schemas/feed_health_schema.json` (`python -c` with jsonschema).
- [ ] **Step 5:** Verify the normal outputs still publish: `make qa-check-s3` (stories.json/momentum.json timestamps advanced).

### Task 7: production deploy + forced runs to accumulate data

- [ ] **Step 1:** `make prod-deploy` (deploys the QA image from `.last-qa-build.txt` to `RunNewvelles`; requires "yes" confirmation and `AWS_ACCOUNT_ID`). Note from NEXT_STEPS: the deploy script preserves naming env vars and runs its own test invocations — extra runs right after deploy are normal.
- [ ] **Step 2:** Force 3 production runs spaced ~2 min apart: `./bin/invoke-lambda-simple.sh RunNewvelles` (×3). These are real publishes — acceptable, they just refresh the live data.
- [ ] **Step 3:** Verify accumulation: `aws s3 ls s3://newvelles-data-bucket/feed_health/` shows ≥3 objects (deploy-script test invocations may add more — fine, more data).
- [ ] **Step 4:** Pull the latest doc, record which feeds fail (`ok: false`) — this is the input dataset for Task 9. Confirm the CloudWatch one-liner: `aws logs filter-log-events --log-group-name /aws/lambda/RunNewvelles --filter-pattern "Feed health" --max-items 5`.
- [ ] **Step 5:** Confirm the sanity gate did not block and `stories.json` is fresh on the public bucket.

---

### Task 8: the `rss-feed-review` skill

**Files:**
- Create: `.claude/skills/rss-feed-review/SKILL.md`

**Interfaces:**
- Consumes: `feed_health/` history (private bucket), `data/rss_source.txt`, `data/rss_qa_reliable.txt`, `data/sources.json`, `data/rss_retired.txt` (created in Task 9), `schemas/feed_health_schema.json`.
- Produces: a repeatable review procedure ending in a PR.

- [ ] **Step 1: Write the skill.** Content (verbatim, adjust only if paths changed):

````markdown
---
name: rss-feed-review
description: Use when reviewing RSS feed health — live-tests every configured feed, reads accumulated feed_health history from S3, classifies feeds healthy/degraded/dead, researches replacements for dead feeds, and produces a PR updating the feed lists. Trigger on "review RSS feeds", "feed health review", or >5 feeds dead for 3+ days.
---

# RSS Feed Review

End state: a PR that (a) removes/replaces feeds confirmed dead, (b) records them
in `data/rss_retired.txt`, (c) keeps `data/sources.json` complete for both active
and retired feeds, (d) optionally adds vetted new sources for under-covered
sections.

## Step 1 — Gather evidence (both sources, always)

1. **History:** list `feed_health/` in the private bucket
   (`aws s3 ls s3://newvelles-data-bucket/feed_health/`), download the last ~14
   days of docs (schema: `schemas/feed_health_schema.json`). Build a per-URL
   table: runs seen, runs ok, last ok datetime, typical http_status,
   newest_entry_age_days.
2. **Live test:** for every URL in `data/rss_source.txt` + `data/rss_qa_reliable.txt`,
   fetch with a Python script using `feedparser` + the repo venv
   (`.python/newvelles/bin/python`): record status, redirects (`href` vs url),
   entry count, newest entry age. Run feeds in parallel (ThreadPoolExecutor,
   ~16 workers, socket timeout 20s). Do NOT rely on live results alone — a feed
   can be flaky, not dead.

## Step 2 — Classify

- **healthy**: ok in live test AND ok in >80% of recorded runs.
- **degraded**: intermittent failures, or newest_entry_age_days > 7 (stale), or
  permanent redirect (fix the URL).
- **dead**: 0 entries or HTTP error in live test AND not ok in any recorded run
  (or all runs for 3+ days). Dead requires BOTH signals — never retire a feed on
  one bad fetch.

## Step 3 — Research replacements for dead/degraded feeds

For each dead feed, in order:
1. Follow redirects; try the resolved URL.
2. Probe common paths on the outlet's domain: `/rss`, `/feed`, `/feeds`,
   `/rss.xml`, `/index.rss`, `/arc/outboundfeeds/rss/`.
3. Check the outlet's HTML for `<link rel="alternate" type="application/rss+xml">`
   (WebFetch the section page).
4. WebSearch "<outlet> RSS feed <year>" for a moved/renamed feed.
Validate every candidate by actually parsing it and checking entry freshness.
If no working equivalent exists → retire.

## Step 4 — Apply changes

- Replacements: swap the URL in `data/rss_source.txt`; add the new URL to
  `data/sources.json` with the same outlet/section (keep the old entry).
- Retirements: delete from `data/rss_source.txt`; append the URL + retirement
  date + reason to `data/rss_retired.txt`; KEEP its `data/sources.json` entry
  (needed by the historical backfill).
- QA list: `data/rss_qa_reliable.txt` must contain only healthy feeds.

## Step 5 — Scan for net-new sources (complementary, not duplicative)

1. Compute section coverage of the active list from `data/sources.json`
   (count feeds per section; note sections with ≤3 feeds).
2. For thin sections, WebSearch for reputable outlets not yet present
   (compare domains against sources.json). Candidate bar: established outlet,
   working RSS with ≥10 entries, fresh (≤2 days), non-paywalled titles.
3. Validate candidates exactly like replacements; add to `data/rss_source.txt`
   + `data/sources.json` with correct outlet/domain/section.

## Step 6 — Verify and ship

1. `pytest test/test_utils_sources.py -v` — every active feed must be mapped.
2. Smoke the pipeline on the changed list:
   `newvelles --rss_file data/rss_source.txt` (venv) — confirm entry counts and
   no new failing feeds in the health summary.
3. `make test` must pass.
4. Branch + PR: list every removal/replacement/addition with its evidence
   (status history + live result). Never force-push; never merge without checks.
````

- [ ] **Step 2: Commit** (direct to main — skill file only, no code):

```bash
git add .claude/skills/rss-feed-review/SKILL.md
git commit -m "feat: rss-feed-review skill (workstream 1, step 2)"
git push
```

---

### Task 9: execute the review end-to-end

**Files:**
- Create: `data/rss_retired.txt`, scratchpad script `check_feeds.py` (not committed)
- Modify: `data/rss_source.txt`, `data/sources.json`, possibly `data/rss_qa_reliable.txt`
- Test: `test/test_utils_sources.py` (must pass; extend `data/sources.json` as needed)

Follow the skill just written (invoke it), using the prod `feed_health/` docs from Task 7 as the history. Concrete acceptance criteria:

- [ ] Every one of the 84 production feeds live-tested; results table produced.
- [ ] Each failing feed cross-checked against ≥3 prod health docs before classification (Task 7 provides ≥3 runs; a feed failing in all of them + live = dead).
- [ ] Replacement research done per dead feed (redirects → common paths → HTML link tag → web search), each candidate validated by parsing.
- [ ] `data/rss_retired.txt` created with header comment + one line per retired feed: `<url>  # retired 2026-08-17: <reason>`.
- [ ] `data/sources.json` entries added for every replacement/new feed; retired entries kept.
- [ ] `pytest test/test_utils_sources.py` and `make test` pass.
- [ ] Local pipeline smoke run on the new list; health summary shows a clearly improved ok ratio (target: every remaining feed ok or transient-degraded).
- [ ] New-source scan: section coverage computed, thin sections identified, candidates vetted; only validated feeds added.
- [ ] PR opened on branch `feed-list-refresh` titled "RSS feed refresh: retire dead feeds, fix moved ones, add new sources" with the per-feed evidence table in the body. Merge after checks; QA-deploy is NOT required for a data-file change to take effect in the next image build, but note in the PR that the list ships with the next deploy.
- [ ] After merge: `make qa-build && make qa-deploy && make qa-invoke` then `make prod-deploy` + one forced run, so production actually runs the cleaned list; verify the new health summary in CloudWatch.

---

## Self-Review

- **Spec coverage:** logging (Tasks 1–4), CloudWatch line (Task 1 `health_summary_lines` + Task 3 wiring), private-bucket upload (Task 1 `emit_feed_health`), deploy + forced prod runs (Tasks 6–7), review skill (Task 8), confirm-broken + replacements + deactivation + new-source scan + PR (Task 9). ✓
- **Placeholder scan:** all code steps carry full code; Task 9 is data-driven by design with explicit acceptance criteria. ✓
- **Type consistency:** record dict keys identical across Tasks 1/2/3/4 schema; `parse_feed(feed_paths, health=None)` consistent between Tasks 2 and 3. ✓
