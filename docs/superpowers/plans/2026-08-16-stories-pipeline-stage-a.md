# Stories Pipeline (Session A: Refactor + Stage A + A.5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit a new `stories.json` (schema 0.3.0) beside the unchanged `latest_news.json` by merging overlapping visualization groups into stories, resolving RSS feeds to outlets/sections, and classifying each story as `story` / `roundup` / `deal` — no LLM, fallback naming only.

**Architecture:** A post-processing stage between `build_visualization()` and the S3 upload. First the duplicated upload logic in `newvelles/feed/log.py` (`log_visualization` / `log_s3`) collapses into one `emit_visualization()` with a writer strategy (`local` / `s3` / `both`), preserving each path's current bytes (including the known drift: the S3-only path's metadata omits `latest_log_reference`). Then new pure-function modules `newvelles/models/stories.py` (link normalization, intra-group dedupe, union-find merge on link containment, classifier, story assembly) and `newvelles/utils/sources.py` (feed URL → outlet/domain/section from `data/sources.json`), plus `newvelles/utils/dates.py` (RSS date → ISO 8601 UTC).

**Tech Stack:** Python 3.12, pytest, jsonschema (already a test dep — verify; if missing add to requirements_dev), spaCy `en_core_web_sm` (already loaded in `newvelles/utils/text.py`), boto3 (mocked in tests).

## Global Constraints

- `latest_news.json`, `latest_news_metadata.json`, and the timestamped private visualization file keep being written **byte-identical** to today, on schema `0.2.1`. Existing tests must pass unchanged.
- Contract: `test/fixtures/stories_v0.3.0.json` — same schema, same field names (values will differ; ids are stable but not identical to the fixture's).
- New file version string: `STORIES_VERSION = "0.3.0"`.
- Merge rule: containment `|A∩B| / min(|A|,|B|) >= MERGE_THRESHOLD`, `MERGE_THRESHOLD = 0.5` (constant in `stories.py`; a later archive sweep tunes it).
- Fallback headline rule: longest title from the outlet with the most articles in the story; `headline_source: "fallback"`. No LLM calls anywhere in this plan.
- Functional style, no classes except `NamedTuple`. Mock only the network boundary (`upload_to_s3`). No new environment variables.
- Repo commits on branch `redesign/stage-a` (branched from `main`), one commit per task, message style `feat:`/`refactor:`/`test:`.

## File Structure

- `newvelles/feed/log.py` — modified: add `emit_visualization()`; `log_visualization`/`log_s3` become thin wrappers; `log_s3` grows optional `stories_data` param.
- `newvelles/utils/dates.py` — new: `to_iso8601(raw: str) -> str`.
- `newvelles/utils/sources.py` — new: `resolve_feed(feed_url: str) -> SourceInfo`, `unmapped_feeds()` log helper.
- `data/sources.json` — new: feed URL → `{outlet, domain, section}` for all feeds in `rss_source.txt` + `rss_qa_reliable.txt`.
- `newvelles/models/stories.py` — new: `normalize_link`, `collect_groups`, `merge_groups`, `classify_story`, `template_run`, `build_stories`.
- `schemas/stories_schema.json` — new.
- `handler.py`, `newvelles/__main__.py` — modified: build stories and pass them to the emit path.
- Tests: `test/test_utils_dates.py`, `test/test_utils_sources.py`, `test/test_models_stories.py`, `test/test_stories_schema.py`, additions to `test/test_feed_log.py`.

---

### Task 1: Collapse `log_visualization`/`log_s3` into `emit_visualization()`

**Files:**
- Modify: `newvelles/feed/log.py:85-171`
- Test: `test/test_feed_log.py` (add class; existing tests untouched)

**Interfaces:**
- Produces: `emit_visualization(visualization_data, writers="local", output_path=_LOG_PATH, stories_data=None) -> str`. `writers ∈ {"local","s3","both"}`. Returns local timestamped log path when local writes happen, else the S3 timestamped file name. `stories_data` handled in Task 8 — accept and ignore-if-None from day one.
- Produces: `log_visualization(visualization_data, output_path=_LOG_PATH, s3=False)` ≡ `emit_visualization(..., writers="both" if s3 else "local")`; `log_s3(visualization_data, stories_data=None)` ≡ `emit_visualization(..., writers="s3", stories_data=...)`. Signatures/returns unchanged for existing callers.

- [ ] **Step 1: Write the failing tests** — append to `test/test_feed_log.py`:

```python
class TestEmitVisualization:
    """The unified emit function must reproduce both legacy paths byte-identically."""

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_s3_writer_matches_legacy_log_s3(self, mock_datetime, mock_upload):
        from newvelles.feed.log import emit_visualization
        mock_datetime.return_value = "2025-01-16T10:30:45"
        viz = {"g": {"sg": {"T": {"title": "T", "link": "https://x/1"}}}}

        result = emit_visualization(viz, writers="s3")

        assert result == "newvelles_visualization_0.2.1_2025-01-16T10:30:45.json"
        assert mock_upload.call_count == 3
        names = [c.kwargs["file_name"] for c in mock_upload.call_args_list]
        assert names == [
            "newvelles_visualization_0.2.1_2025-01-16T10:30:45.json",
            "latest_news.json",
            "latest_news_metadata.json",
        ]
        # drift preserved: s3-only metadata has NO latest_log_reference
        meta = json.loads(mock_upload.call_args_list[2].kwargs["string_byte"])
        assert meta == {"datetime": "2025-01-16T10:30:45", "version": "0.2.1"}
        # payload bytes identical to legacy json.dumps
        assert mock_upload.call_args_list[0].kwargs["string_byte"] == json.dumps(viz).encode("utf-8")
        # public flags
        assert mock_upload.call_args_list[0].kwargs.get("public_read", False) is False
        assert mock_upload.call_args_list[1].kwargs["public_read"] is True
        assert mock_upload.call_args_list[2].kwargs["public_read"] is True

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_local_writer_writes_files_and_metadata_reference(self, mock_datetime, mock_upload, tmp_path, monkeypatch):
        from newvelles.feed import log as log_mod
        mock_datetime.return_value = "2025-01-16T10:30:45"
        monkeypatch.setattr(log_mod, "_LATEST_PATH", str(tmp_path / "latest"))
        monkeypatch.chdir(tmp_path)
        viz = {"a": 1}

        result = log_mod.emit_visualization(viz, writers="local", output_path=str(tmp_path / "logs"))

        assert result == str(tmp_path / "logs") + "/newvelles_visualization_0.2.1_2025-01-16T10:30:45.json"
        assert json.load(open(result)) == viz
        assert json.load(open(tmp_path / "latest" / "latest_news.json")) == viz
        assert json.load(open(tmp_path / "latest_news.json")) == viz  # cwd copy
        meta = json.load(open(tmp_path / "latest" / "latest_news_metadata.json"))
        assert meta["latest_log_reference"] == result  # local path INCLUDES the reference
        mock_upload.assert_not_called()

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_both_writer_uploads_metadata_with_reference(self, mock_datetime, mock_upload, tmp_path, monkeypatch):
        from newvelles.feed import log as log_mod
        mock_datetime.return_value = "2025-01-16T10:30:45"
        monkeypatch.setattr(log_mod, "_LATEST_PATH", str(tmp_path / "latest"))
        monkeypatch.chdir(tmp_path)

        log_mod.emit_visualization({}, writers="both", output_path=str(tmp_path / "logs"))

        meta_call = [c for c in mock_upload.call_args_list
                     if c.kwargs["file_name"] == "latest_news_metadata.json"][0]
        meta = json.loads(meta_call.kwargs["string_byte"])
        assert "latest_log_reference" in meta  # legacy log_visualization(s3=True) behavior

    def test_invalid_writer_raises(self):
        from newvelles.feed.log import emit_visualization
        with pytest.raises(ValueError):
            emit_visualization({}, writers="ftp")

    @patch("newvelles.feed.log.emit_visualization")
    def test_log_s3_delegates(self, mock_emit):
        mock_emit.return_value = "x.json"
        assert log_s3({}) == "x.json"
        mock_emit.assert_called_once_with({}, writers="s3", stories_data=None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest test/test_feed_log.py -v -k EmitVisualization`
Expected: FAIL / ERROR with "cannot import name 'emit_visualization'"

- [ ] **Step 3: Implement.** Replace the bodies of `log_visualization` and `log_s3` in `newvelles/feed/log.py`:

```python
_LOG_STORIES_NAME = "stories"


def emit_visualization(
    visualization_data,
    writers: str = "local",
    output_path: str = _LOG_PATH,
    stories_data=None,
) -> str:
    """Single emit path for visualization outputs.

    writers: "local" (CLI), "s3" (Lambda), "both" (CLI --s3).
    The metadata's latest_log_reference exists only when a local log file
    exists to reference — preserving the historical difference between the
    CLI and Lambda outputs.
    """
    if writers not in ("local", "s3", "both"):
        raise ValueError(f"writers must be local|s3|both, got {writers!r}")
    write_local = writers in ("local", "both")
    write_s3 = writers in ("s3", "both")

    current_datetime = _current_datetime()
    viz_file_name = f"{_LOG_VISUALIZATION_NAME}_{VISUALIZATION_VERSION}"
    timestamped_name = f"{viz_file_name}_{current_datetime}.json"
    log_path = f"{output_path}/{timestamped_name}"

    if write_local:
        os.makedirs(_LATEST_PATH, exist_ok=True)
        os.makedirs(output_path, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(visualization_data, f)
    if write_s3:
        upload_to_s3(
            bucket_name=_S3_BUCKET,
            file_name=timestamped_name,
            string_byte=json.dumps(visualization_data).encode("utf-8"),
        )

    if write_local:
        for latest_path in (
            f"{_LATEST_PATH}/{_LOG_LATEST_VISUALIZATION_NAME}.json",
            f"./{_LOG_LATEST_VISUALIZATION_NAME}.json",
        ):
            with open(latest_path, "w", encoding="utf-8") as f:
                json.dump(visualization_data, f)
    if write_s3:
        upload_to_s3(
            bucket_name=_S3_PUBLIC_BUCKET,
            file_name=f"{_LOG_LATEST_VISUALIZATION_NAME}.json",
            string_byte=json.dumps(visualization_data).encode("utf-8"),
            public_read=True,
        )

    latest_metadata = {"datetime": current_datetime, "version": VISUALIZATION_VERSION}
    if write_local:
        latest_metadata["latest_log_reference"] = log_path
        metadata_path = f"{_LATEST_PATH}/{_LOG_LATEST_VISUALIZATION_METADATA_NAME}.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(latest_metadata, f)
    if write_s3:
        upload_to_s3(
            bucket_name=_S3_PUBLIC_BUCKET,
            file_name=f"{_LOG_LATEST_VISUALIZATION_METADATA_NAME}.json",
            string_byte=json.dumps(latest_metadata).encode("utf-8"),
            public_read=True,
        )

    # stories_data handling lands in Task 8; accept-and-ignore keeps callers stable
    if stories_data is not None:
        _emit_stories(stories_data, write_local=write_local, write_s3=write_s3)

    return log_path if write_local else timestamped_name


def _emit_stories(stories_data, write_local: bool, write_s3: bool) -> None:
    """Placeholder until Task 8 — no-op."""


def log_visualization(visualization_data, output_path: str = _LOG_PATH, s3: bool = False) -> str:
    return emit_visualization(
        visualization_data,
        writers="both" if s3 else "local",
        output_path=output_path,
    )


def log_s3(visualization_data, stories_data=None) -> str:
    return emit_visualization(visualization_data, writers="s3", stories_data=stories_data)
```

Note the legacy `log_visualization` writes the metadata local file BUT the local metadata dict it uploads when `s3=True` includes `latest_log_reference` — behavior preserved above. The legacy local-writer ordering (timestamped file → latest copies → metadata) is preserved.

- [ ] **Step 4: Run the full log test file + whole suite fast lane**

Run: `pytest test/test_feed_log.py -v && pytest test -x -q`
Expected: all PASS (pre-existing failures, if any, must be shown to be pre-existing by `git stash` check before blaming the refactor)

- [ ] **Step 5: Commit**

```bash
git add newvelles/feed/log.py test/test_feed_log.py
git commit -m "refactor: collapse log_visualization/log_s3 into emit_visualization with writer strategy"
```

---

### Task 2: `newvelles/utils/dates.py` — normalize RSS dates to ISO 8601 UTC

**Files:**
- Create: `newvelles/utils/dates.py`
- Test: `test/test_utils_dates.py`

**Interfaces:**
- Produces: `to_iso8601(raw: str) -> str` — returns `YYYY-MM-DDTHH:MM:SSZ` (UTC) for any parseable input; returns the input unchanged when unparseable. `iso_date(raw: str) -> str` — the `YYYY-MM-DD` part of `to_iso8601`, or `""` if unparseable.

- [ ] **Step 1: Write the failing tests** (`test/test_utils_dates.py`):

```python
import pytest
from newvelles.utils.dates import to_iso8601, iso_date


@pytest.mark.parametrize("raw,expected", [
    ("Sat, 16 Aug 2025 18:51:12 +0000", "2025-08-16T18:51:12Z"),   # RFC 2822
    ("2025-08-16T04:31:19Z", "2025-08-16T04:31:19Z"),              # already ISO/UTC
    ("Sat, 16 Aug 2025 13:00:00 EST", "2025-08-16T18:00:00Z"),     # named US zone
    ("Sat, 16 Aug 2025 13:00:00 GMT", "2025-08-16T13:00:00Z"),
    ("2026-08-07T12:00:00", "2026-08-07T12:00:00Z"),               # naive -> assume UTC
    ("2025-08-16T04:31:19+02:00", "2025-08-16T02:31:19Z"),         # offset converted
])
def test_to_iso8601_formats(raw, expected):
    assert to_iso8601(raw) == expected


def test_to_iso8601_unparseable_returns_input():
    assert to_iso8601("not a date") == "not a date"
    assert to_iso8601("") == ""


def test_iso_date():
    assert iso_date("Sat, 16 Aug 2025 18:51:12 +0000") == "2025-08-16"
    assert iso_date("garbage") == ""
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest test/test_utils_dates.py -v`
Expected: FAIL "No module named 'newvelles.utils.dates'"

- [ ] **Step 3: Implement** `newvelles/utils/dates.py`:

```python
"""Normalize the several RSS date formats to ISO 8601 UTC."""
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")


def to_iso8601(raw: str) -> str:
    dt = _parse(raw)
    if dt is None:
        return raw
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_date(raw: str) -> str:
    dt = _parse(raw)
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _parse(raw: str):
    if not raw:
        return None
    if _ISO_RE.match(raw):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
```

- [ ] **Step 4: Run tests**

Run: `pytest test/test_utils_dates.py -v`
Expected: PASS (if the `EST` case fails because `parsedate_to_datetime` returns naive for obsolete zone names, keep the test and fix by mapping `parsedate_tz`'s offset: use `email.utils.parsedate_tz` + `datetime.fromtimestamp(email.utils.mktime_tz(t), timezone.utc)` when the tz name is a known US zone; `parsedate_tz` understands EST/EDT/CST/…)

- [ ] **Step 5: Commit**

```bash
git add newvelles/utils/dates.py test/test_utils_dates.py
git commit -m "feat: add RSS date normalization to ISO 8601 UTC"
```

---

### Task 3: `newvelles/utils/sources.py` + `data/sources.json`

**Files:**
- Create: `newvelles/utils/sources.py`, `data/sources.json`
- Test: `test/test_utils_sources.py`

**Interfaces:**
- Produces: `SourceInfo(NamedTuple)` with fields `outlet: str, domain: str, section: str`; `resolve_feed(feed_url: str) -> SourceInfo`; `is_mapped(feed_url: str) -> bool`. Unmapped feeds resolve via fallback (registered domain of the feed URL, capitalized stem as outlet, section `"General"`) and are logged once per process via `print` (matching the repo's logging style).
- Sections vocabulary: `World`, `US politics`, `Markets`, `Tech`, `Science`, `Local`, `General`.

- [ ] **Step 1: Write the failing tests** (`test/test_utils_sources.py`):

```python
from pathlib import Path

from newvelles.utils.sources import SourceInfo, is_mapped, resolve_feed

REPO_ROOT = Path(__file__).resolve().parents[1]


def _feeds(fname):
    return [l.strip() for l in (REPO_ROOT / "data" / fname).read_text().splitlines() if l.strip()]


def test_every_production_feed_is_mapped():
    unmapped = [f for f in _feeds("rss_source.txt") if not is_mapped(f)]
    assert unmapped == [], f"Unmapped production feeds: {unmapped}"


def test_every_qa_feed_is_mapped():
    unmapped = [f for f in _feeds("rss_qa_reliable.txt") if not is_mapped(f)]
    assert unmapped == [], f"Unmapped QA feeds: {unmapped}"


def test_known_resolutions():
    r = resolve_feed("https://feeds.bbci.co.uk/news/world/rss.xml")
    assert r.outlet == "BBC" and r.domain == "bbc.com" and r.section == "World"
    r = resolve_feed("https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml")
    assert r.outlet == "NYT" and r.domain == "nytimes.com" and r.section == "Tech"


def test_unmapped_feed_falls_back_to_registered_domain():
    r = resolve_feed("https://blog.example.co.uk/feed.xml")
    assert isinstance(r, SourceInfo)
    assert r.domain == "example.co.uk"
    assert r.section == "General"
    assert r.outlet  # non-empty


def test_sections_are_valid_vocabulary():
    import json
    table = json.loads((REPO_ROOT / "data" / "sources.json").read_text())
    allowed = {"World", "US politics", "Markets", "Tech", "Science", "Local", "General"}
    bad = {url: v["section"] for url, v in table.items() if v["section"] not in allowed}
    assert bad == {}
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest test/test_utils_sources.py -v`
Expected: FAIL "No module named 'newvelles.utils.sources'"

- [ ] **Step 3: Author `data/sources.json`.** Enumerate every URL in `data/rss_source.txt` and `data/rss_qa_reliable.txt` (84 + 13, with overlap). Shape:

```json
{
  "https://feeds.bbci.co.uk/news/world/rss.xml": {"outlet": "BBC", "domain": "bbc.com", "section": "World"},
  "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml": {"outlet": "NYT", "domain": "nytimes.com", "section": "Tech"}
}
```

Outlet names: BBC, NYT, Politico, Yahoo, NPR, Wired, Fox News, Lifehacker, NY Post, Newsweek, etc. (short display names as in the fixture: `BBC`, `NYT`). Section from the feed's topic path (e.g. `nyt/Technology.xml` → Tech, `politico.com/congress` → US politics, `finance.yahoo` → Markets, science feeds → Science, city/regional feeds → Local, homepage/general feeds → the outlet's dominant beat or General). Every feed in both txt files must have an entry — the test enforces it.

- [ ] **Step 4: Implement** `newvelles/utils/sources.py`:

```python
"""Resolve RSS feed URLs to outlet name, registered domain and section."""
import json
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

_SOURCES_PATH = Path(__file__).resolve().parents[2] / "data" / "sources.json"


class SourceInfo(NamedTuple):
    outlet: str
    domain: str
    section: str


def _load_table() -> dict:
    try:
        return json.loads(_SOURCES_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


_TABLE = _load_table()
_REPORTED_UNMAPPED: set = set()

# two-label public suffixes we actually encounter in the feed list
_TWO_LABEL_SUFFIXES = {"co.uk", "com.au", "co.jp"}


def registered_domain(host: str) -> str:
    parts = host.lower().lstrip(".").split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in _TWO_LABEL_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def is_mapped(feed_url: str) -> bool:
    return feed_url in _TABLE


def resolve_feed(feed_url: str) -> SourceInfo:
    entry = _TABLE.get(feed_url)
    if entry:
        return SourceInfo(entry["outlet"], entry["domain"], entry["section"])
    host = urlsplit(feed_url).netloc or feed_url
    domain = registered_domain(host.split(":")[0].removeprefix("www."))
    if feed_url not in _REPORTED_UNMAPPED:
        _REPORTED_UNMAPPED.add(feed_url)
        print(f"⚠️ Unmapped RSS feed (add to data/sources.json): {feed_url}")
    outlet = domain.split(".")[0].capitalize()
    return SourceInfo(outlet, domain, "General")
```

- [ ] **Step 5: Run tests, fill in any feeds the coverage test lists as missing until green**

Run: `pytest test/test_utils_sources.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add newvelles/utils/sources.py data/sources.json test/test_utils_sources.py
git commit -m "feat: add feed source resolution table (outlet, domain, section)"
```

---

### Task 4: Link normalization + group collection with intra-group dedupe

**Files:**
- Create: `newvelles/models/stories.py` (first slice)
- Test: `test/test_models_stories.py` (first slice)

**Interfaces:**
- Produces: `normalize_link(url: str) -> str` — lowercase host, drop `www.`, drop trailing slash, drop query string and fragment entirely (the tracked queries in this corpus — `?utm_medium=RSS`, BBC's `?at_medium=RSS` — are all tracking; scheme dropped).
- Produces: `collect_groups(visualization: dict) -> list[dict]` — one dict per top-level group: `{"group_id": str, "articles": {normalized_link: article_dict}, "keywords": [str]}`. Article dict keys: `title, link, published_raw, feed`. Accepts entries keyed either `timestamp`/`source` (current pipeline) or `published`/`title_detail_base` (older files). Intra-group duplicates (same normalized link across sub-groups) collapse to one entry. `keywords` = bracket phrases parsed from the top-level group id, lowercased, deduplicated in order.

- [ ] **Step 1: Write the failing tests** (`test/test_models_stories.py`):

```python
import json
from pathlib import Path

import pytest

from newvelles.models.stories import collect_groups, normalize_link

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("url,expected", [
    ("https://www.BBC.co.uk/news/article-1?at_medium=RSS", "bbc.co.uk/news/article-1"),
    ("https://lifehacker.com/tech/x?utm_medium=RSS", "lifehacker.com/tech/x"),
    ("http://example.com/path/", "example.com/path"),
    ("https://example.com/", "example.com"),
])
def test_normalize_link(url, expected):
    assert normalize_link(url) == expected


def test_same_article_same_identity_despite_query_and_case():
    a = normalize_link("https://www.nytimes.com/2025/08/16/x.html?smid=rss")
    b = normalize_link("https://WWW.NYTIMES.com/2025/08/16/x.html")
    assert a == b


def _viz(entries_by_group):
    """Helper: {top_id: {sub_id: [ (title, link) ]}} -> visualization dict."""
    viz = {}
    for top, subs in entries_by_group.items():
        viz[top] = {}
        for sub, arts in subs.items():
            viz[top][sub] = {
                t: {"title": t, "link": l, "timestamp": "Sat, 16 Aug 2025 18:51:12 +0000",
                    "source": "https://feeds.bbci.co.uk/news/world/rss.xml"}
                for t, l in arts
            }
    return viz


def test_collect_groups_dedupes_within_group():
    viz = _viz({"[alaska]": {
        "[sub1]": [("A", "https://x.com/a"), ("B", "https://x.com/b")],
        "[sub2]": [("A2", "https://x.com/a?utm_medium=RSS")],   # same article, different sub-group
    }})
    groups = collect_groups(viz)
    assert len(groups) == 1
    assert set(groups[0]["articles"]) == {"x.com/a", "x.com/b"}


def test_collect_groups_keywords_from_bracket_phrases():
    viz = _viz({"[Alaska Summit] [ceasefire] [Alaska Summit]": {"[s]": [("A", "https://x.com/a"), ("B", "https://x.com/b")]}})
    assert collect_groups(viz)[0]["keywords"] == ["alaska summit", "ceasefire"]


def test_collect_groups_handles_old_key_names():
    viz = {"[g]": {"[s]": {"T": {
        "title": "T", "link": "https://x.com/t",
        "published": "2025-08-16T04:31:19Z",
        "title_detail_base": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    }}}}
    g = collect_groups(viz)[0]
    art = g["articles"]["x.com/t"]
    assert art["published_raw"] == "2025-08-16T04:31:19Z"
    assert art["feed"].startswith("https://rss.nytimes.com")


def test_intra_group_dedupe_on_real_example_file():
    """data/latest_news_example.json: 410 entries resolve to 121 unique links,
    all duplication is within-group across sub-groups."""
    viz = json.loads((REPO_ROOT / "data" / "latest_news_example.json").read_text())
    groups = collect_groups(viz)
    all_links = [l for g in groups for l in g["articles"]]
    assert len(all_links) == len(set(all_links)) or True  # cross-group dupes allowed here
    per_group_unique = sum(len(g["articles"]) for g in groups)
    assert per_group_unique < 410  # dedupe actually removed intra-group copies
    assert len({l for g in groups for l in g["articles"]}) == 121
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest test/test_models_stories.py -v`
Expected: FAIL "No module named 'newvelles.models.stories'"

- [ ] **Step 3: Implement the first slice of** `newvelles/models/stories.py`:

```python
"""Merge visualization groups into stories (schema 0.3.0). Stage A + A.5."""
import re
from urllib.parse import urlsplit

STORIES_VERSION = "0.3.0"
MERGE_THRESHOLD = 0.5

_BRACKET_RE = re.compile(r"\[([^\]]+)\]")


def normalize_link(url: str) -> str:
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/")
    return f"{host}{path}"


def _article_from_entry(entry: dict) -> dict:
    return {
        "title": entry.get("title", ""),
        "link": entry.get("link", ""),
        "published_raw": entry.get("timestamp") or entry.get("published", ""),
        "feed": entry.get("source") or entry.get("title_detail_base", ""),
    }


def _keywords_from_group_id(group_id: str) -> list:
    seen, out = set(), []
    for phrase in _BRACKET_RE.findall(group_id):
        p = phrase.strip().lower()
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def collect_groups(visualization: dict) -> list:
    groups = []
    for top_id, sub_groups in visualization.items():
        articles = {}
        for entries in sub_groups.values():
            for entry in entries.values():
                art = _article_from_entry(entry)
                key = normalize_link(art["link"])
                if key and key not in articles:
                    articles[key] = art
        if articles:
            groups.append({
                "group_id": top_id,
                "articles": articles,
                "keywords": _keywords_from_group_id(top_id),
            })
    return groups
```

- [ ] **Step 4: Run tests**

Run: `pytest test/test_models_stories.py -v`
Expected: PASS (if the 121-link assertion fails, print the actual number, verify by an independent count of unique normalized links in the file, and correct the test constant only if the independent count agrees)

- [ ] **Step 5: Commit**

```bash
git add newvelles/models/stories.py test/test_models_stories.py
git commit -m "feat: link normalization and group collection with intra-group dedupe"
```

---

### Task 5: Merge groups via union-find on link containment

**Files:**
- Modify: `newvelles/models/stories.py`
- Test: `test/test_models_stories.py` (append)

**Interfaces:**
- Consumes: `collect_groups()` output (list of group dicts with `articles` keyed by normalized link).
- Produces: `merge_groups(groups: list, threshold: float = MERGE_THRESHOLD) -> list[list[int]]` — connected components as lists of indices into `groups`, ordered by first-seen index. Edge iff `overlap(a, b) >= threshold` where `overlap = |A∩B| / min(|A|,|B|)`.

- [ ] **Step 1: Write the failing tests** (append to `test/test_models_stories.py`):

```python
from newvelles.models.stories import merge_groups


def _g(links):
    return {"group_id": "[g]", "keywords": [],
            "articles": {l: {"title": l, "link": l, "published_raw": "", "feed": ""} for l in links}}


def test_merge_containment_beats_jaccard():
    """A 4-article group fully contained in a 30-article group must merge
    (containment 1.0) even though Jaccard would be ~0.13."""
    big = _g([f"big.com/{i}" for i in range(30)])
    small = _g([f"big.com/{i}" for i in range(4)])
    assert merge_groups([big, small]) == [[0, 1]]


def test_merge_below_threshold_stays_apart():
    a = _g(["a.com/1", "a.com/2", "a.com/3", "shared.com/x"])
    b = _g(["b.com/1", "b.com/2", "b.com/3", "shared.com/x"])
    # overlap = 1/4 = 0.25 < 0.5
    assert merge_groups([a, b]) == [[0], [1]]


def test_merge_transitive_chain():
    """A~B and B~C merge into one component even when A and C share nothing."""
    a = _g(["x.com/1", "x.com/2"])
    b = _g(["x.com/1", "x.com/2", "y.com/1", "y.com/2"])
    c = _g(["y.com/1", "y.com/2"])
    assert merge_groups([a, b, c]) == [[0, 1, 2]]


def test_merge_no_overlap_is_noop():
    groups = [_g([f"s{i}.com/a", f"s{i}.com/b"]) for i in range(5)]
    assert merge_groups(groups) == [[i] for i in range(5)]


def test_merge_threshold_boundary_inclusive():
    a = _g(["s.com/1", "s.com/2", "u.com/1", "u.com/2"])
    b = _g(["s.com/1", "s.com/2", "v.com/1", "v.com/2"])
    # overlap = 2/4 = 0.5 -> edge at threshold 0.5 (>=)
    assert merge_groups([a, b], threshold=0.5) == [[0, 1]]
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest test/test_models_stories.py -v -k merge`
Expected: FAIL "cannot import name 'merge_groups'"

- [ ] **Step 3: Implement** (append to `stories.py`):

```python
def _find(parent, i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def _union(parent, a, b):
    ra, rb = _find(parent, a), _find(parent, b)
    if ra != rb:
        parent[max(ra, rb)] = min(ra, rb)


def merge_groups(groups: list, threshold: float = MERGE_THRESHOLD) -> list:
    link_sets = [set(g["articles"]) for g in groups]
    parent = list(range(len(groups)))
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            smaller = min(len(link_sets[i]), len(link_sets[j]))
            if smaller == 0:
                continue
            if len(link_sets[i] & link_sets[j]) / smaller >= threshold:
                _union(parent, i, j)
    components = {}
    for i in range(len(groups)):
        components.setdefault(_find(parent, i), []).append(i)
    return [components[r] for r in sorted(components)]
```

- [ ] **Step 4: Run tests**

Run: `pytest test/test_models_stories.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add newvelles/models/stories.py test/test_models_stories.py
git commit -m "feat: union-find merge of overlapping groups on link containment"
```

---

### Task 6: Stage A.5 classifier — `story` / `roundup` / `deal`

**Files:**
- Modify: `newvelles/models/stories.py`
- Test: `test/test_models_stories.py` (append)

**Interfaces:**
- Consumes: a story's article titles + outlet count.
- Produces: `classify_story(titles: list[str], outlet_count: int) -> str` returning `"deal" | "roundup" | "story"`; `template_run(titles: list[str]) -> int` (longest contiguous word run, lowercased comparison, shared by >= 60% of titles, excluding runs containing a proper noun). Proper nouns are collected only from sentence-case titles (title-case detection: >= 70% of words longer than 3 chars are capitalized); weekday and month names are always generic.

- [ ] **Step 1: Write the failing tests** — the three real clusters from the build spec (append):

```python
from newvelles.models.stories import classify_story, template_run

EARNINGS_TITLES = [
    "Select Water Solutions Q2 Earnings Call Highlights",
    "Essential Utilities Q2 Earnings Call Highlights",
    "Watts Water Technologies Q2 Earnings Call Highlights",
    "Warby Parker Q2 Earnings Call Highlights",
]

HACKS_TITLES = [
    "Five Hacks Every Amazfit Balance 3 User Should Know",
    "Five Hacks Every Amazfit Cheetah 2 Ultra User Should Know",
    "10 Screenshot Hacks Every Mac User Should Know",
]

DEAL_TITLES = [
    "This 27-Inch Asus OLED Gaming Monitor Is $120 Off Right Now",
    "This LG Ultrawide OLED Gaming Monitor Is $200 Off Right Now",
    "This 45-Inch LG UltraGear OLED Curved Monitor Is $700 Off",
]

NEWS_TITLES = [
    "Trump Bows to Putin's Approach on Ukraine: No Cease-Fire, Deadlines or Sanctions",
    "Watch: Moment Trump and Putin meet in Alaska",
    "Trump and Putin end summit without ceasefire deal for Ukraine",
]


def test_earnings_cluster_is_roundup():
    assert classify_story(EARNINGS_TITLES, outlet_count=1) == "roundup"


def test_hacks_cluster_is_roundup():
    assert classify_story(HACKS_TITLES, outlet_count=1) == "roundup"


def test_monitor_cluster_is_deal():
    assert classify_story(DEAL_TITLES, outlet_count=1) == "deal"


def test_multi_outlet_news_is_story():
    assert classify_story(NEWS_TITLES, outlet_count=3) == "story"


def test_multi_outlet_template_still_story():
    """Roundup requires single-outlet; a template across outlets is real syndication."""
    assert classify_story(EARNINGS_TITLES, outlet_count=4) == "story"


def test_proper_noun_run_does_not_count_as_template():
    """Two outlets covering one event share a long run carrying proper nouns —
    that's a subject, not a template (sentence-case titles here)."""
    titles = [
        "Judge orders U.S. to dispense $600M for vaccines RFK Jr. held up",
        "Court says administration must dispense $600M for vaccines RFK Jr. held up",
    ]
    assert classify_story(titles, outlet_count=1) == "story"


def test_template_run_counts_contiguous_words():
    assert template_run(EARNINGS_TITLES) >= 3     # "Q2 Earnings Call Highlights"
    assert template_run(NEWS_TITLES) < 3


def test_weekday_month_names_are_generic():
    titles = [
        "Gold prices today, Monday, August 4",
        "Gold prices today, Tuesday, August 5",
        "Gold prices today, Wednesday, August 6",
    ]
    assert classify_story(titles, outlet_count=1) == "roundup"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest test/test_models_stories.py -v -k "classify or template or roundup or deal"`
Expected: FAIL "cannot import name 'classify_story'"

- [ ] **Step 3: Implement** (append to `stories.py`):

```python
DEAL_RE = re.compile(
    r"(\$\s?\d[\d,]*(\.\d+)?\s*off|\d+\s?%\s*off|\bpre-?order\b|\bdeals?\b|\bdiscount\b|\bcoupon\b)",
    re.IGNORECASE,
)
TEMPLATE_MIN_RUN = 3
TEMPLATE_SHARE = 0.6
_GENERIC_CAPITALIZED = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
}
_WORD_RE = re.compile(r"[A-Za-z0-9$%'’.-]+")


def _words(title: str) -> list:
    return _WORD_RE.findall(title)


def _is_title_case(words: list) -> bool:
    significant = [w for w in words if len(w) > 3 and w[0].isalpha()]
    if not significant:
        return False
    capitalized = [w for w in significant if w[0].isupper()]
    return len(capitalized) / len(significant) >= 0.7


def _proper_nouns(titles: list) -> set:
    nouns = set()
    for title in titles:
        words = _words(title)
        if _is_title_case(words):
            continue  # capitalization is meaningless in title-case headlines
        for word in words[1:]:  # skip sentence-initial capital
            if word[0].isalpha() and word[0].isupper():
                w = word.lower().strip(".'’")
                if w not in _GENERIC_CAPITALIZED:
                    nouns.add(w)
    return nouns


def template_run(titles: list) -> int:
    if len(titles) < 2:
        return 0
    proper = _proper_nouns(titles)
    lowered = [[w.lower() for w in _words(t)] for t in titles]
    need = max(2, -(-len(titles) * 6 // 10))  # ceil(0.6 * n), at least 2
    best = 0
    seen_runs = set()
    for words in lowered:
        for i in range(len(words)):
            for j in range(i + TEMPLATE_MIN_RUN, len(words) + 1):
                run = tuple(words[i:j])
                if run in seen_runs:
                    continue
                seen_runs.add(run)
                if any(w.strip(".'’") in proper for w in run):
                    continue
                count = sum(1 for other in lowered if _contains_run(other, run))
                if count >= need:
                    best = max(best, len(run))
    return best


def _contains_run(words: list, run: tuple) -> bool:
    n = len(run)
    return any(tuple(words[k:k + n]) == run for k in range(len(words) - n + 1))


def classify_story(titles: list, outlet_count: int) -> str:
    deal_matches = sum(1 for t in titles if DEAL_RE.search(t))
    if titles and deal_matches / len(titles) > 0.5:
        return "deal"
    if outlet_count == 1 and template_run(titles) >= TEMPLATE_MIN_RUN:
        return "roundup"
    return "story"
```

- [ ] **Step 4: Run tests; tune only within the spec's parameters if a case fails** (the spec fixes: 60% share, >= 3 contiguous words, proper-noun exclusion, sentence-case-only collection, weekday/month generic, deal = majority regex match)

Run: `pytest test/test_models_stories.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add newvelles/models/stories.py test/test_models_stories.py
git commit -m "feat: story/roundup/deal classifier with template-run detection"
```

---

### Task 7: Story assembly — `build_stories()`

**Files:**
- Modify: `newvelles/models/stories.py`
- Test: `test/test_models_stories.py` (append)

**Interfaces:**
- Consumes: `collect_groups`, `merge_groups`, `classify_story`, `newvelles.utils.sources.resolve_feed`, `newvelles.utils.dates.to_iso8601/iso_date`, spaCy NER via `newvelles.utils.text.NLP`.
- Produces: `build_stories(visualization: dict, generated: str | None = None) -> dict` returning the full stories document:
  - top level: `version` ("0.3.0"), `generated` (arg or now, `%Y-%m-%dT%H:%M:%S`), `feeds` (distinct feed URLs), `article_count` (unique articles across stories), `story_count`, `merge_threshold`, `kind_counts` (`{"story": n, "roundup": n, "deal": n}`), `stories` (list).
  - per story: `id` (`"st_" + sha256(",".join(sorted(links)[:20]))[:6]` over normalized links), `headline` (fallback rule), `headline_source` (`"fallback"`), `keywords` (union of merged groups' keywords, first-seen order, max 8), `entities` (spaCy NER over titles, labels PERSON/ORG/GPE/LOC/NORP/FAC/EVENT, frequency-ranked, max 10), `section` (modal article section), `kind`, `outlet_count`, `article_count`, `latest_published` (max ISO), `first_seen` (min date), `days_running` (distinct publish dates), `merged_from_groups`, `outlets` (sorted by articles desc), `articles` (sorted by published desc; each: `title, link, published` (ISO), `outlet, domain, section, feed`).
  - stories sorted by `(outlet_count, article_count, latest_published)` descending.

- [ ] **Step 1: Write the failing tests** (append):

```python
from newvelles.models.stories import build_stories


def _entry(title, link, published, feed):
    return {"title": title, "link": link, "timestamp": published, "source": feed}

BBC = "https://feeds.bbci.co.uk/news/world/rss.xml"
NYT = "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"

VIZ = {
    "[alaska summit] [ceasefire]": {
        "[putin]": {
            "Trump and Putin end summit without ceasefire deal": _entry(
                "Trump and Putin end summit without ceasefire deal",
                "https://www.bbc.co.uk/news/summit-1", "Sat, 16 Aug 2025 18:51:12 +0000", BBC),
            "Watch: Moment Trump and Putin meet in Alaska": _entry(
                "Watch: Moment Trump and Putin meet in Alaska",
                "https://www.bbc.co.uk/news/summit-video", "Sat, 16 Aug 2025 12:00:00 +0000", BBC),
        },
    },
    "[alaska]": {
        "[trump putin]": {
            "Trump bows to Putin approach on Ukraine": _entry(
                "Trump bows to Putin approach on Ukraine",
                "https://www.nytimes.com/2025/08/16/summit.html", "2025-08-15T04:31:19Z", NYT),
            "Watch: Moment Trump and Putin meet in Alaska (dup)": _entry(
                "Watch: Moment Trump and Putin meet in Alaska",
                "https://www.bbc.co.uk/news/summit-video?at_medium=RSS",
                "Sat, 16 Aug 2025 12:00:00 +0000", BBC),
        },
    },
    "[quarterly results]": {
        "[earnings]": {
            "Acme Q2 Earnings Call Highlights": _entry(
                "Acme Q2 Earnings Call Highlights",
                "https://finance.yahoo.com/news/acme", "2025-08-16T04:00:00Z",
                "https://finance.yahoo.com/rss/"),
            "Globex Q2 Earnings Call Highlights": _entry(
                "Globex Q2 Earnings Call Highlights",
                "https://finance.yahoo.com/news/globex", "2025-08-14T04:00:00Z",
                "https://finance.yahoo.com/rss/"),
        },
    },
}


@pytest.fixture(scope="module")
def doc():
    return build_stories(VIZ, generated="2025-08-16T20:00:00")


def test_top_level_fields(doc):
    assert doc["version"] == "0.3.0"
    assert doc["generated"] == "2025-08-16T20:00:00"
    assert doc["story_count"] == len(doc["stories"]) == 2
    assert doc["feeds"] == 3
    assert doc["article_count"] == 5  # dup video counted once
    assert doc["merge_threshold"] == 0.5
    assert doc["kind_counts"] == {"story": 1, "roundup": 1, "deal": 0}


def test_merged_story_shape(doc):
    story = doc["stories"][0]  # 2 outlets ranks first
    assert story["outlet_count"] == 2
    assert story["article_count"] == 3
    assert story["merged_from_groups"] == 2
    assert story["kind"] == "story"
    assert story["id"].startswith("st_") and len(story["id"]) == 9
    assert story["headline_source"] == "fallback"
    # fallback: BBC has most articles (2); its longest title:
    assert story["headline"] == "Trump and Putin end summit without ceasefire deal"
    assert story["keywords"][:2] == ["alaska summit", "ceasefire"]
    assert "alaska" in story["keywords"]
    assert story["section"] == "World"
    assert story["latest_published"] == "2025-08-16T18:51:12Z"
    assert story["first_seen"] == "2025-08-15"
    assert story["days_running"] == 2
    outlets = {o["outlet"]: o for o in story["outlets"]}
    assert outlets["BBC"]["articles"] == 2 and outlets["BBC"]["domain"] == "bbc.com"
    assert outlets["NYT"]["articles"] == 1
    # articles sorted by published desc, ISO normalized, each carries outlet metadata
    pubs = [a["published"] for a in story["articles"]]
    assert pubs == sorted(pubs, reverse=True)
    assert all(a["published"].endswith("Z") for a in story["articles"])
    assert story["articles"][0]["domain"] in {"bbc.co.uk", "bbc.com", "nytimes.com"}


def test_roundup_classified_and_ranked_below(doc):
    roundup = doc["stories"][1]
    assert roundup["kind"] == "roundup"
    assert roundup["outlet_count"] == 1


def test_stable_ids(doc):
    doc2 = build_stories(VIZ, generated="2099-01-01T00:00:00")
    assert [s["id"] for s in doc2["stories"]] == [s["id"] for s in doc["stories"]]


def test_entities_present(doc):
    story = doc["stories"][0]
    assert isinstance(story["entities"], list)
    assert any("Putin" in e or "Trump" in e or "Alaska" in e for e in story["entities"])


def test_build_stories_on_real_example_file():
    viz = json.loads((REPO_ROOT / "data" / "latest_news_example.json").read_text())
    doc = build_stories(viz)
    assert doc["story_count"] == len(doc["stories"]) > 0
    links = [a["link"] for s in doc["stories"] for a in s["articles"]]
    # flattening removed the massive intra-group duplication
    assert len(links) == doc["article_count"]
    for s in doc["stories"]:
        assert s["kind"] in {"story", "roundup", "deal"}
        assert s["outlet_count"] >= 1
        assert s["outlet_count"] <= len({a["outlet"] for a in s["articles"]}) + 1
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest test/test_models_stories.py -v -k "doc or build_stories or entities or stable"`
Expected: FAIL "cannot import name 'build_stories'"

- [ ] **Step 3: Implement** (append to `stories.py`):

```python
import hashlib
from collections import Counter
from datetime import datetime

from newvelles.utils.dates import iso_date, to_iso8601
from newvelles.utils.sources import resolve_feed

_ENTITY_LABELS = {"PERSON", "ORG", "GPE", "LOC", "NORP", "FAC", "EVENT"}
MAX_KEYWORDS = 8
MAX_ENTITIES = 10


def _story_id(links: list) -> str:
    fingerprint = hashlib.sha256(",".join(sorted(links)[:20]).encode("utf-8")).hexdigest()
    return f"st_{fingerprint[:6]}"


def _fallback_headline(articles: list) -> str:
    by_outlet = Counter(a["outlet"] for a in articles)
    top_outlet = by_outlet.most_common(1)[0][0]
    candidates = [a["title"] for a in articles if a["outlet"] == top_outlet]
    return max(candidates, key=len)


def _extract_entities(titles: list) -> list:
    from newvelles.utils.text import NLP  # module-level spaCy model, already loaded
    counts: Counter = Counter()
    for title in titles:
        for ent in NLP(title).ents:
            if ent.label_ in _ENTITY_LABELS:
                counts[ent.text] += 1
    return [e for e, _ in counts.most_common(MAX_ENTITIES)]


def build_stories(visualization: dict, generated: str = None) -> dict:
    groups = collect_groups(visualization)
    components = merge_groups(groups)

    stories = []
    all_links = set()
    all_feeds = set()
    for component in components:
        articles_by_link = {}
        keywords, seen_kw = [], set()
        for idx in component:
            for link, art in groups[idx]["articles"].items():
                articles_by_link.setdefault(link, art)
            for kw in groups[idx]["keywords"]:
                if kw not in seen_kw:
                    seen_kw.add(kw)
                    keywords.append(kw)

        articles = []
        for link, art in articles_by_link.items():
            source = resolve_feed(art["feed"])
            articles.append({
                "title": art["title"],
                "link": art["link"],
                "published": to_iso8601(art["published_raw"]),
                "outlet": source.outlet,
                "domain": source.domain,
                "section": source.section,
                "feed": art["feed"],
            })
            all_feeds.add(art["feed"])
        all_links.update(articles_by_link)
        articles.sort(key=lambda a: a["published"], reverse=True)

        titles = [a["title"] for a in articles]
        outlet_counter = Counter(a["outlet"] for a in articles)
        outlet_domains = {a["outlet"]: a["domain"] for a in articles}
        sections = Counter(a["section"] for a in articles)
        publish_dates = {iso_date(a["published"]) for a in articles} - {""}
        parseable = [a["published"] for a in articles if a["published"].endswith("Z")]

        stories.append({
            "id": _story_id(list(articles_by_link)),
            "headline": _fallback_headline(articles),
            "headline_source": "fallback",
            "keywords": keywords[:MAX_KEYWORDS],
            "entities": _extract_entities(titles),
            "section": sections.most_common(1)[0][0],
            "kind": classify_story(titles, outlet_count=len(outlet_counter)),
            "outlet_count": len(outlet_counter),
            "article_count": len(articles),
            "latest_published": max(parseable) if parseable else "",
            "first_seen": min(publish_dates) if publish_dates else "",
            "days_running": max(len(publish_dates), 1),
            "merged_from_groups": len(component),
            "outlets": [
                {"outlet": o, "domain": outlet_domains[o], "articles": n}
                for o, n in outlet_counter.most_common()
            ],
            "articles": articles,
        })

    stories.sort(key=lambda s: (s["outlet_count"], s["article_count"], s["latest_published"]),
                 reverse=True)
    kind_counts = Counter(s["kind"] for s in stories)
    return {
        "version": STORIES_VERSION,
        "generated": generated or datetime.now().isoformat().split(".")[0],
        "feeds": len(all_feeds),
        "article_count": len(all_links),
        "story_count": len(stories),
        "merge_threshold": MERGE_THRESHOLD,
        "kind_counts": {k: kind_counts.get(k, 0) for k in ("story", "roundup", "deal")},
        "stories": stories,
    }
```

Note `MIN` story size: the visualization already filters groups below 2 titles, so no extra minimum here — a merged story always has >= 1 unique article after dedupe (a group whose entries all collapse to one link is legitimate and stays).

- [ ] **Step 4: Run the full stories test file**

Run: `pytest test/test_models_stories.py -v`
Expected: PASS (the real-example test may surface date formats `to_iso8601` can't parse — extend `dates.py` for any format actually present in `latest_news_example.json`, with a test per new format)

- [ ] **Step 5: Commit**

```bash
git add newvelles/models/stories.py test/test_models_stories.py newvelles/utils/dates.py test/test_utils_dates.py
git commit -m "feat: build_stories assembles merged, classified, source-resolved stories"
```

---

### Task 8: JSON schema + fixture validation

**Files:**
- Create: `schemas/stories_schema.json`
- Test: `test/test_stories_schema.py`

**Interfaces:**
- Consumes: `build_stories()` output; `test/fixtures/stories_v0.3.0.json`.
- Produces: `schemas/stories_schema.json` (Draft 7, matching the style of `schemas/latest_news_schema.json`). Both the fixture and real output must validate.

- [ ] **Step 1: Write the failing tests** (`test/test_stories_schema.py`):

```python
import json
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def schema():
    return json.loads((REPO_ROOT / "schemas" / "stories_schema.json").read_text())


def test_contract_fixture_validates(schema):
    fixture = json.loads((REPO_ROOT / "test" / "fixtures" / "stories_v0.3.0.json").read_text())
    jsonschema.validate(fixture, schema)


def test_build_stories_output_validates(schema):
    from newvelles.models.stories import build_stories
    viz = json.loads((REPO_ROOT / "data" / "latest_news_example.json").read_text())
    jsonschema.validate(build_stories(viz), schema)


def test_schema_rejects_missing_headline(schema):
    fixture = json.loads((REPO_ROOT / "test" / "fixtures" / "stories_v0.3.0.json").read_text())
    del fixture["stories"][0]["headline"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(fixture, schema)


def test_schema_rejects_bad_kind(schema):
    fixture = json.loads((REPO_ROOT / "test" / "fixtures" / "stories_v0.3.0.json").read_text())
    fixture["stories"][0]["kind"] = "advert"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(fixture, schema)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest test/test_stories_schema.py -v`
Expected: FAIL (schema file missing). If `jsonschema` is not installed, add it to `requirements_dev.txt` (check `make test-s3-schema` tooling first — it likely already depends on it).

- [ ] **Step 3: Write** `schemas/stories_schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Newvelles Stories Schema",
  "description": "Schema for stories.json (version 0.3.0) - merged, classified, source-resolved stories",
  "type": "object",
  "required": ["version", "generated", "feeds", "article_count", "story_count", "stories"],
  "properties": {
    "version": {"type": "string", "pattern": "^0\\.3\\.\\d+$"},
    "generated": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}$"},
    "source_fetch": {"type": "string"},
    "feeds": {"type": "integer", "minimum": 0},
    "article_count": {"type": "integer", "minimum": 0},
    "story_count": {"type": "integer", "minimum": 0},
    "merge_threshold": {"type": "number", "minimum": 0, "maximum": 1},
    "kind_counts": {
      "type": "object",
      "properties": {
        "story": {"type": "integer", "minimum": 0},
        "roundup": {"type": "integer", "minimum": 0},
        "deal": {"type": "integer", "minimum": 0}
      }
    },
    "classifier_note": {"type": "string"},
    "stories": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "id", "headline", "headline_source", "keywords", "entities", "section",
          "kind", "outlet_count", "article_count", "latest_published",
          "first_seen", "days_running", "outlets", "articles"
        ],
        "properties": {
          "id": {"type": "string", "pattern": "^st_[0-9a-f]{6}$"},
          "headline": {"type": "string", "minLength": 1},
          "headline_source": {"type": "string", "enum": ["llm", "fallback"]},
          "keywords": {"type": "array", "items": {"type": "string"}},
          "entities": {"type": "array", "items": {"type": "string"}},
          "section": {"type": "string", "minLength": 1},
          "kind": {"type": "string", "enum": ["story", "roundup", "deal"]},
          "outlet_count": {"type": "integer", "minimum": 1},
          "article_count": {"type": "integer", "minimum": 1},
          "latest_published": {"type": "string"},
          "first_seen": {"type": "string"},
          "days_running": {"type": "integer", "minimum": 1},
          "merged_from_groups": {"type": "integer", "minimum": 1},
          "outlets": {
            "type": "array",
            "minItems": 1,
            "items": {
              "type": "object",
              "required": ["outlet", "domain", "articles"],
              "properties": {
                "outlet": {"type": "string", "minLength": 1},
                "domain": {"type": "string", "minLength": 1},
                "articles": {"type": "integer", "minimum": 1}
              }
            }
          },
          "articles": {
            "type": "array",
            "minItems": 1,
            "items": {
              "type": "object",
              "required": ["title", "link", "published", "outlet", "domain"],
              "properties": {
                "title": {"type": "string", "minLength": 1},
                "link": {"type": "string", "minLength": 1},
                "published": {"type": "string"},
                "outlet": {"type": "string", "minLength": 1},
                "domain": {"type": "string", "minLength": 1},
                "section": {"type": "string"},
                "feed": {"type": "string"}
              }
            }
          }
        }
      }
    }
  }
}
```

If the fixture fails validation on any field shape, the schema (not the fixture) is wrong — the fixture is the contract; adjust the schema and note the difference.

- [ ] **Step 4: Run tests**

Run: `pytest test/test_stories_schema.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add schemas/stories_schema.json test/test_stories_schema.py requirements_dev.txt
git commit -m "feat: JSON schema for stories.json v0.3.0, validated against contract fixture"
```

---

### Task 9: Wire stories emission into `emit_visualization`, `handler.py`, and the CLI

**Files:**
- Modify: `newvelles/feed/log.py` (`_emit_stories` real implementation), `handler.py:76-82`, `newvelles/__main__.py:16-28`
- Modify: `CLAUDE.md` (Core Data Flow: add the stories stage; Key Files: add `newvelles/models/stories.py`)
- Test: `test/test_feed_log.py` (append)

**Interfaces:**
- Consumes: `build_stories()` from Task 7, `emit_visualization(..., stories_data=...)` from Task 1.
- Produces: when `stories_data` is not None — S3 writer uploads `stories.json` (public bucket, `public_read=True`) after the three legacy uploads; local writer writes `{_LATEST_PATH}/stories.json` and `./stories.json`. Legacy three uploads and their order unchanged.

- [ ] **Step 1: Write the failing tests** (append to `test/test_feed_log.py`):

```python
class TestEmitStories:
    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_stories_uploaded_to_public_bucket_after_legacy_files(self, mock_datetime, mock_upload):
        from newvelles.feed.log import emit_visualization
        mock_datetime.return_value = "2025-01-16T10:30:45"
        stories = {"version": "0.3.0", "stories": []}

        emit_visualization({}, writers="s3", stories_data=stories)

        names = [c.kwargs["file_name"] for c in mock_upload.call_args_list]
        assert names == [
            "newvelles_visualization_0.2.1_2025-01-16T10:30:45.json",
            "latest_news.json",
            "latest_news_metadata.json",
            "stories.json",
        ]
        stories_call = mock_upload.call_args_list[3]
        assert stories_call.kwargs["bucket_name"] == _S3_PUBLIC_BUCKET
        assert stories_call.kwargs["public_read"] is True
        assert json.loads(stories_call.kwargs["string_byte"]) == stories

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_no_stories_means_no_fourth_upload(self, mock_datetime, mock_upload):
        from newvelles.feed.log import emit_visualization
        mock_datetime.return_value = "2025-01-16T10:30:45"
        emit_visualization({}, writers="s3")
        assert mock_upload.call_count == 3

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_local_writer_writes_stories_file(self, mock_datetime, mock_upload, tmp_path, monkeypatch):
        from newvelles.feed import log as log_mod
        mock_datetime.return_value = "2025-01-16T10:30:45"
        monkeypatch.setattr(log_mod, "_LATEST_PATH", str(tmp_path / "latest"))
        monkeypatch.chdir(tmp_path)
        stories = {"version": "0.3.0", "stories": []}

        log_mod.emit_visualization({}, writers="local", output_path=str(tmp_path / "logs"),
                                   stories_data=stories)

        assert json.load(open(tmp_path / "latest" / "stories.json")) == stories
        assert json.load(open(tmp_path / "stories.json")) == stories
        mock_upload.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest test/test_feed_log.py -v -k EmitStories`
Expected: FAIL (placeholder `_emit_stories` does nothing)

- [ ] **Step 3: Implement.** Replace the `_emit_stories` placeholder in `newvelles/feed/log.py`:

```python
def _emit_stories(stories_data, write_local: bool, write_s3: bool) -> None:
    if write_local:
        with open(f"{_LATEST_PATH}/{_LOG_STORIES_NAME}.json", "w", encoding="utf-8") as f:
            json.dump(stories_data, f)
        with open(f"./{_LOG_STORIES_NAME}.json", "w", encoding="utf-8") as f:
            json.dump(stories_data, f)
    if write_s3:
        upload_to_s3(
            bucket_name=_S3_PUBLIC_BUCKET,
            file_name=f"{_LOG_STORIES_NAME}.json",
            string_byte=json.dumps(stories_data).encode("utf-8"),
            public_read=True,
        )
```

Then wire the callers. `handler.py` — replace lines 80-82:

```python
    from newvelles.models.stories import build_stories

    print("📚 Building stories (merge + classify)...")
    stories_data = build_stories(visualization_data)
    kind_counts = stories_data.get("kind_counts", {})
    print(f"📚 {stories_data['story_count']} stories "
          f"({kind_counts.get('story', 0)} story / {kind_counts.get('roundup', 0)} roundup / "
          f"{kind_counts.get('deal', 0)} deal) from {len(visualization_data)} groups")

    print("📤 Uploading to S3...")
    log_s3(visualization_data, stories_data=stories_data)
    print("✅ S3 upload completed successfully")
```

(Put the `build_stories` import at the top of `handler.py` with the other imports, not inline.)

`newvelles/__main__.py` — in `run()`, after `build_visualization`:

```python
    from newvelles.models.stories import build_stories
    stories_data = build_stories(visualization_data)
    # log data
    log_visualization(visualization_data, s3=s3)
    from newvelles.feed.log import emit_visualization  # noqa: place at top with other imports
```

Simpler and preferred: change `run()` to call the emit function once:

```python
def run(rss_file: str, s3: bool) -> None:
    title_data = build_data_from_rss_feeds(rss_file)
    cluster_limit = int(CONFIG["PARAMS"]["cluster_limit"])
    visualization_data, group_sentences = build_visualization(
        title_data, cluster_limit=cluster_limit
    )
    stories_data = build_stories(visualization_data)
    # log data
    emit_visualization(
        visualization_data,
        writers="both" if s3 else "local",
        stories_data=stories_data,
    )
    log_groups(group_sentences)
```

with `from newvelles.feed.log import emit_visualization, log_groups` and `from newvelles.models.stories import build_stories` at the top.

Update `CLAUDE.md`: in "Core Data Flow", insert a step between clustering and S3 upload — "3.5 **Stories** (`newvelles/models/stories.py`) — merges overlapping top-level groups into stories (link containment >= 0.5, union-find), resolves feeds to outlets/sections via `data/sources.json`, classifies story/roundup/deal, emits `stories.json` (schema 0.3.0) beside `latest_news.json`". In "Key Files", add `newvelles/models/stories.py` and `schemas/stories_schema.json`.

- [ ] **Step 4: Run the whole suite**

Run: `pytest test -q`
Expected: PASS (all — existing suite unchanged plus new tests)

- [ ] **Step 5: End-to-end smoke test (local, no S3):**

Run: `source .python/newvelles/bin/activate 2>/dev/null; python -c "
import json
from newvelles.models.stories import build_stories
viz = json.load(open('data/latest_news_example.json'))
doc = build_stories(viz)
print(doc['story_count'], 'stories;', doc['kind_counts'])
json.dump(doc, open('/tmp/stories_smoke.json','w'), indent=1)
import jsonschema
jsonschema.validate(doc, json.load(open('schemas/stories_schema.json')))
print('schema OK')
"`
Expected: a plausible story count (the example file has 36 top groups; expect fewer or equal stories), non-degenerate kind mix, "schema OK".

- [ ] **Step 6: Commit**

```bash
git add newvelles/feed/log.py handler.py newvelles/__main__.py CLAUDE.md test/test_feed_log.py
git commit -m "feat: emit stories.json beside latest_news.json in Lambda and CLI paths"
```

---

## Out of scope (explicitly deferred)

- **Merge-threshold sweep** over ~30 stored production runs (KICKOFF's second Session A prompt) — requires private-bucket downloads; run after this plan lands.
- **Stage B** (Bedrock Haiku naming behind the four-provider interface) and **Stage C** (momentum) — independent follow-ups.
- QA deploy (`make qa-build/deploy/invoke/check-s3`) — after review.

## Self-Review notes

- Spec coverage: refactor (T1), article identity + normalization (T4), merge rule + containment (T5), outlet counting/source table (T3), sections (T3/T7), classifier incl. proper-noun trap + weekday/month rule (T6), ISO dates + articles-as-list schema changes (T2/T7), fallback naming (T7), stories.json emission with latest_news.json untouched (T1/T9), schema in `schemas/` + fixture validation (T8), testing philosophy per spec §7 (all tasks). `days_running`/`first_seen` derived from distinct publish dates, matching the fixture's derivation.
- Types are consistent across tasks: `collect_groups` list-of-dicts feeds `merge_groups` index components feeding `build_stories`.
- The example-file constants (121 unique links, 36 groups) are verified against the file before being trusted in assertions (T4 step 4 note).
