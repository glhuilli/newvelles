# Analysis Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the five-year archive dashboard on newvelles.com behind a new Analysis tab in the board header, organized as dated entries, reviewable locally against real data before any deploy.

**Architecture:** The newvelles repo builds one `index.json` plus one `payload.json` per entry and (later) publishes them to the public bucket. The web repo proxies those files through Flask, adds an `analysis` view to the existing state machine, renders a shell with `innerHTML`, and mounts the ported D3 panels imperatively into that shell. Ported renderers keep their code; only element lookup, module state, and CSS scoping change.

**Tech Stack:** Python 3.12 + pandas (builder), jsonschema (tests), Flask (proxy), Vite + vanilla JS + `d3` v7 (front end), vitest + jsdom (unit/integration), Playwright (e2e).

**Spec:** `docs/superpowers/specs/2026-09-19-analysis-tab-design.md` (newvelles repo). Read it first.

## Global Constraints

- Two repos: `/Users/gastonlhuillier/Personal/newvelles` (Tasks 1) and `/Users/gastonlhuillier/Personal/newvelles_web` (Tasks 2 to 8). Branch name `analysis-tab` in both. Never push without the user's explicit OK. Never run `bin/deploy.sh`.
- Entry ids match `^[a-z0-9-]{1,64}$`. Index schema version `0.1.0`. Payload `version` `0.1.0`.
- No new colors. Series `--s1..--s8` = `#3987e5 #008300 #d55181 #c98500 #199e70 #d95926 #9085e9 #6b6f80`. All other colors come from Nocturne `--nv-*` tokens.
- `data/` is gitignored in the web repo. Fixture files are added with `git add -f`.
- Payload files (`analysis/entries/*/payload.json`) are gitignored in the newvelles repo. `entry.json` and `index.json` are committed.
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Existing `data-go-wire` and `data-go-board` attributes keep their names so current handlers and tests keep working.

---

## File map

**newvelles repo**

| File | Responsibility |
|---|---|
| `analysis/entries/five-years/entry.json` (new) | Human-edited entry metadata: title, summary, links, panels |
| `analysis/entries/index.json` (new, generated, committed) | All entries, newest first, merged with computed dates and stats |
| `analysis/build_payload.py` (modify) | `--entry <id>` writes payload and upserts the index |
| `schemas/analysis_index_schema.json` (new) | Contract for `index.json` |
| `scripts/publish_analysis.py` (new) | Validate, gzip, upload index and one payload |
| `test/test_analysis_index_schema.py` (new) | Schema and publish helper tests |
| `Makefile` (modify) | `publish-analysis ENTRY=<id>` |
| `analysis/.gitignore` (modify) | ignore `entries/*/payload.json` |

**newvelles_web repo**

| File | Responsibility |
|---|---|
| `newvelles_web/analysis.py` (new) | Fetch index and entry payload from bucket or local dir, validate id |
| `newvelles_web/app.py` (modify) | Two routes + CORS entries |
| `vite.config.js` (modify) | proxy `/analysis` |
| `package.json` (modify) | dependency `d3` |
| `src/redesign/state.js` (modify) | `analysis` view, `entry`, `panel`, actions, `refresh()` |
| `src/redesign/main.js` (modify) | analysis URLs per data mode, `configureAnalysis` |
| `src/redesign/render.js` (modify) | shared header with tab strip, analysis dispatch, handlers |
| `src/redesign/styles.css` (modify) | tab strip, import analysis styles |
| `src/redesign/analysis/loader.js` (new) | memoized index and payload loading |
| `src/redesign/analysis/view.js` (new) | shell HTML + mount of the active panel |
| `src/redesign/analysis/context.js` (new) | shared helpers the renderers used from the top of the old script |
| `src/redesign/analysis/panels/index.js` (new) | panel registry, labels, placeholder |
| `src/redesign/analysis/panels/{timeline,ledger,lifetimes,archetypes,stats,categories,topstories,learnings}.js` (new) | one `mount(section, ctx)` per panel |
| `src/redesign/analysis/panels/learnings.html` (new) | static Learnings markup |
| `src/redesign/analysis/styles.css` (new) | old dashboard CSS scoped under `.an-root`, tokens mapped |
| `scripts/make_analysis_fixture.py` (new) | trims a real payload into the fixture |
| `data/fixtures/analysis/index.json`, `data/fixtures/analysis/entries/five-years/payload.json` (new, force-added) | test fixture |
| `tests/unit/analysisLoader.test.js`, `tests/integration/analysis.test.js`, `tests/e2e/analysis.spec.js` (new) | tests |
| `docs/REDESIGN_STATUS.md` (modify) | note |

---

### Task 1: Entry metadata, builder `--entry`, index schema, publish script (newvelles)

**Files:**
- Create: `analysis/entries/five-years/entry.json`
- Modify: `analysis/build_payload.py` (bottom of file, the `build()` tail and `__main__`)
- Modify: `analysis/.gitignore`
- Create: `schemas/analysis_index_schema.json`
- Create: `scripts/publish_analysis.py`
- Create: `test/test_analysis_index_schema.py`
- Modify: `Makefile` (after `backfill-momentum:`)

**Interfaces:**
- Produces: `analysis/entries/index.json` with the shape in the spec Part 1; `analysis/entries/five-years/payload.json` = old `data.json` + `version` + `entry`.
- Produces: `scripts/publish_analysis.py` functions `gzip_bytes(data: bytes) -> bytes`, `put_args(key: str, body: bytes, cache_seconds: int) -> dict`.

- [ ] **Step 1: Branch and entry metadata**

```bash
cd /Users/gastonlhuillier/Personal/newvelles && git checkout analysis-tab
mkdir -p analysis/entries/five-years
```

Write `analysis/entries/five-years/entry.json`:

```json
{
  "id": "five-years",
  "number": 1,
  "title": "Five years of news cycles",
  "summary": "How stories start, peak and fade across the whole archive: which categories fill the wire, how long a story lives, the shapes a news cycle takes, and who covers what. Built from every run since the first day of collection.",
  "published": "2026-09-19",
  "links": {
    "post": "",
    "code": "https://github.com/glhuilli/newvelles/tree/main/analysis"
  },
  "panels": ["timeline", "ledger", "lifetimes", "archetypes", "stats", "categories", "topstories", "learnings"]
}
```

Append to `analysis/.gitignore`:

```
entries/*/payload.json
```

- [ ] **Step 2: Write the failing schema and publish-helper tests**

Create `test/test_analysis_index_schema.py`:

```python
"""Contract tests for analysis/entries/index.json and the publish helper."""
import gzip
import json
import os

import jsonschema
import pytest

SCHEMA_PATH = "schemas/analysis_index_schema.json"
INDEX_PATH = "analysis/entries/index.json"


@pytest.fixture
def schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _valid_index():
    return {
        "version": "0.1.0",
        "generated": "2026-09-19T20:00:00Z",
        "entries": [
            {
                "id": "five-years",
                "number": 1,
                "title": "Five years of news cycles",
                "summary": "How stories start, peak and fade.",
                "first_day": "2021-07-10",
                "last_day": "2026-08-18",
                "published": "2026-09-19",
                "links": {"post": "", "code": "https://github.com/glhuilli/newvelles/tree/main/analysis"},
                "panels": ["timeline", "ledger"],
                "payload": "/analysis/entries/five-years/payload.json",
                "stats": {"runs": 9311, "stories": 114927, "days": 1832, "majors": 13},
            }
        ],
    }


def test_valid_index_passes(schema):
    jsonschema.validate(_valid_index(), schema)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["entries"][0].update(id="Five Years"),
        lambda d: d["entries"][0].update(id="../etc"),
        lambda d: d["entries"][0].pop("payload"),
        lambda d: d["entries"][0].update(panels=[]),
        lambda d: d["entries"][0].update(first_day="2021/07/10"),
        lambda d: d.update(version="1.0"),
        lambda d: d["entries"][0]["stats"].update(runs="9311"),
    ],
)
def test_invalid_index_rejected(schema, mutate):
    doc = _valid_index()
    mutate(doc)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)


def test_checked_in_index_validates(schema):
    assert os.path.exists(INDEX_PATH), "run: analysis/.venv/bin/python analysis/build_payload.py --entry five-years"
    with open(INDEX_PATH, encoding="utf-8") as f:
        doc = json.load(f)
    jsonschema.validate(doc, schema)
    assert doc["entries"][0]["id"] == "five-years"
    numbers = [e["number"] for e in doc["entries"]]
    assert numbers == sorted(numbers, reverse=True), "entries must be newest first"


def test_publish_helpers_gzip_and_headers():
    from scripts.publish_analysis import gzip_bytes, put_args

    raw = json.dumps({"a": 1}).encode()
    gz = gzip_bytes(raw)
    assert gzip.decompress(gz) == raw
    args = put_args("analysis/index.json", gz, cache_seconds=300)
    assert args["Key"] == "analysis/index.json"
    assert args["Body"] == gz
    assert args["ContentType"] == "application/json"
    assert args["ContentEncoding"] == "gzip"
    assert args["CacheControl"] == "public, max-age=300"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `source .python/newvelles/bin/activate && pytest test/test_analysis_index_schema.py -q`
Expected: FAIL. `FileNotFoundError` for the schema and `ModuleNotFoundError` for `scripts.publish_analysis`.

- [ ] **Step 4: Write the schema**

Create `schemas/analysis_index_schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Newvelles analysis index",
  "type": "object",
  "required": ["version", "generated", "entries"],
  "additionalProperties": false,
  "properties": {
    "version": { "type": "string", "pattern": "^0\\.1\\.\\d+$" },
    "generated": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$" },
    "entries": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["id", "number", "title", "summary", "first_day", "last_day", "published", "links", "panels", "payload", "stats"],
        "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^[a-z0-9-]{1,64}$" },
          "number": { "type": "integer", "minimum": 1 },
          "title": { "type": "string", "minLength": 1 },
          "summary": { "type": "string" },
          "first_day": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" },
          "last_day": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" },
          "published": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" },
          "links": {
            "type": "object",
            "required": ["post", "code"],
            "additionalProperties": false,
            "properties": { "post": { "type": "string" }, "code": { "type": "string" } }
          },
          "panels": { "type": "array", "minItems": 1, "items": { "type": "string", "pattern": "^[a-z]+$" } },
          "payload": { "type": "string", "pattern": "^/analysis/entries/[a-z0-9-]{1,64}/payload\\.json$" },
          "stats": {
            "type": "object",
            "required": ["runs", "stories", "days", "majors"],
            "additionalProperties": false,
            "properties": {
              "runs": { "type": "integer", "minimum": 0 },
              "stories": { "type": "integer", "minimum": 0 },
              "days": { "type": "integer", "minimum": 0 },
              "majors": { "type": "integer", "minimum": 0 }
            }
          }
        }
      }
    }
  }
}
```

- [ ] **Step 5: Write the publish script**

Create `scripts/publish_analysis.py`:

```python
"""Publish one analysis entry (index.json + payload.json) to the public bucket.

Usage: python scripts/publish_analysis.py --entry five-years [--bucket public-newvelles-data-bucket] [--dry-run]

Never runs inside the Lambda. Validates the index against the schema first.
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "analysis" / "entries"
SCHEMA = ROOT / "schemas" / "analysis_index_schema.json"
DEFAULT_BUCKET = "public-newvelles-data-bucket"


def gzip_bytes(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=9, mtime=0)


def put_args(key: str, body: bytes, cache_seconds: int) -> dict:
    return {
        "Key": key,
        "Body": body,
        "ContentType": "application/json",
        "ContentEncoding": "gzip",
        "CacheControl": f"public, max-age={cache_seconds}",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry", required=True)
    ap.add_argument("--bucket", default=DEFAULT_BUCKET)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    index_path = ENTRIES / "index.json"
    payload_path = ENTRIES / args.entry / "payload.json"
    if not payload_path.exists():
        print(f"missing {payload_path}; run build_payload.py --entry {args.entry}", file=sys.stderr)
        return 2
    index = json.loads(index_path.read_text(encoding="utf-8"))
    jsonschema.validate(index, json.loads(SCHEMA.read_text(encoding="utf-8")))
    if args.entry not in {e["id"] for e in index["entries"]}:
        print(f"entry {args.entry} is not in index.json", file=sys.stderr)
        return 2

    uploads = [
        put_args("analysis/index.json", gzip_bytes(index_path.read_bytes()), 300),
        put_args(f"analysis/entries/{args.entry}/payload.json", gzip_bytes(payload_path.read_bytes()), 86400),
    ]
    for u in uploads:
        print(f"{'DRY ' if args.dry_run else ''}put s3://{args.bucket}/{u['Key']} ({len(u['Body']) / 1024:.0f} KB gzip)")
    if args.dry_run:
        return 0
    import boto3  # imported here so tests never need AWS

    s3 = boto3.client("s3")
    for u in uploads:
        s3.put_object(Bucket=args.bucket, **u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Check `scripts/__init__.py` exists (the test imports `scripts.publish_analysis`). If it does not: `touch scripts/__init__.py`.

- [ ] **Step 6: Extend the builder**

In `analysis/build_payload.py`, replace the tail from `out = HERE / "site" / "data.json"` through the end of the file with:

```python
    out = HERE / "site" / "data.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(payload), encoding="utf-8")
    print(f"data.json: {out.stat().st_size / 1e6:.2f} MB · "
          f"{payload['meta']['stories']:,} stories · {payload['meta']['runs']:,} runs · "
          f"archetype silhouette {payload['archetypes']['silhouette']}")

    if site:
        template = (HERE / "site" / "template.html").read_text(encoding="utf-8")
        html = (template
                .replace("/*__D3__*/", D3_MIN.read_text(encoding="utf-8"))
                .replace("/*__DATA__*/", "window.DATA = " + json.dumps(payload) + ";"))
        (HERE / "site" / "index.html").write_text(html, encoding="utf-8")
        print(f"site/index.html: {(HERE / 'site' / 'index.html').stat().st_size / 1e6:.2f} MB")

    if entry:
        write_entry(payload, entry)


ENTRIES = HERE / "entries"
PAYLOAD_VERSION = "0.1.0"
INDEX_VERSION = "0.1.0"


def write_entry(payload: dict, entry_id: str) -> None:
    """Write entries/<id>/payload.json and upsert entries/index.json.

    entry.json (checked in) carries the human-edited fields. Dates and stats
    come from the payload so they can never drift from the data.
    """
    edir = ENTRIES / entry_id
    meta_path = edir / "entry.json"
    if not meta_path.exists():
        raise SystemExit(f"missing {meta_path}: create it first (see docs/superpowers/specs/2026-09-19-analysis-tab-design.md)")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("id") != entry_id:
        raise SystemExit(f"{meta_path} id {meta.get('id')!r} != {entry_id!r}")

    doc = {"version": PAYLOAD_VERSION, "entry": entry_id, **payload}
    (edir / "payload.json").write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")

    majors = payload.get("categories", {}).get("majors_order", [])
    record = {
        "id": entry_id,
        "number": int(meta["number"]),
        "title": meta["title"],
        "summary": meta.get("summary", ""),
        "first_day": payload["meta"]["first_day"],
        "last_day": payload["meta"]["last_day"],
        "published": meta["published"],
        "links": {"post": meta.get("links", {}).get("post", ""), "code": meta.get("links", {}).get("code", "")},
        "panels": list(meta["panels"]),
        "payload": f"/analysis/entries/{entry_id}/payload.json",
        "stats": {
            "runs": int(payload["meta"]["runs"]),
            "stories": int(payload["meta"]["stories"]),
            "days": int(len(payload["daily"])),
            "majors": int(len(majors)),
        },
    }

    index_path = ENTRIES / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"entries": []}
    entries = [e for e in index.get("entries", []) if e["id"] != entry_id] + [record]
    entries.sort(key=lambda e: e["number"], reverse=True)
    index = {
        "version": INDEX_VERSION,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entries": entries,
    }
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"entries/{entry_id}/payload.json: {(edir / 'payload.json').stat().st_size / 1e6:.2f} MB · index.json: {len(entries)} entries")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", action="store_true")
    ap.add_argument("--entry", default=None, help="entry id, e.g. five-years; writes entries/<id>/payload.json + index.json")
    a = ap.parse_args()
    build(a.site, a.entry)
```

Change the `build` signature at its definition from `def build(site):` (or whatever the current name of the boolean parameter is; read it) to `def build(site, entry=None):`. `datetime` and `timezone` are already imported at the top of the file.

- [ ] **Step 7: Build the entry**

Run: `analysis/.venv/bin/python analysis/build_payload.py --entry five-years`
Expected: prints the `data.json` line, then `entries/five-years/payload.json: 1.4x MB · index.json: 1 entries`. Takes a few minutes.

Check: `python3 -c "import json;d=json.load(open('analysis/entries/five-years/payload.json'));print(d['version'],d['entry'],sorted(d)[:5])"` prints `0.1.0 five-years [...]`.

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest test/test_analysis_index_schema.py -q`
Expected: all pass.

- [ ] **Step 9: Makefile target**

Add after the `backfill-momentum` target in `Makefile`:

```make
# Publish one analysis entry (index.json + payload.json, gzipped) to the public
# bucket. Build it first: analysis/.venv/bin/python analysis/build_payload.py --entry <id>
# Add DRY=1 to print what would upload without touching S3.
publish-analysis:
	@if [ -z "$(ENTRY)" ]; then echo "Usage: make publish-analysis ENTRY=five-years [DRY=1]"; exit 1; fi
	@$(VENV_ACTIVATE) && python scripts/publish_analysis.py --entry $(ENTRY) $(if $(DRY),--dry-run,)
```

Run: `make publish-analysis ENTRY=five-years DRY=1`
Expected: two `DRY put s3://public-newvelles-data-bucket/analysis/...` lines. No upload.

- [ ] **Step 10: Commit**

```bash
git add analysis/entries/five-years/entry.json analysis/entries/index.json analysis/.gitignore analysis/build_payload.py schemas/analysis_index_schema.json scripts/publish_analysis.py scripts/__init__.py test/test_analysis_index_schema.py Makefile
git status --short   # payload.json must NOT appear
git commit -m "feat: analysis entries — builder --entry, index.json schema, publish script

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Flask proxy, dev proxy, local data (newvelles_web)

**Files:**
- Create: `newvelles_web/analysis.py`
- Modify: `newvelles_web/app.py` (imports, CORS dict, routes after `momentum()`)
- Modify: `vite.config.js` (proxy map)

**Interfaces:**
- Produces: `GET /analysis/index.json`, `GET /analysis/entries/<entry_id>/payload.json`. Python: `is_valid_entry_id(s) -> bool`, `get_index(local: bool) -> dict`, `get_entry_payload(entry_id: str, local: bool) -> dict` (raises `ValueError` on a bad id).

- [ ] **Step 1: Branch and local data**

```bash
cd /Users/gastonlhuillier/Personal/newvelles_web && git checkout -b analysis-tab
mkdir -p data/local/analysis/entries/five-years
cp ../newvelles/analysis/entries/index.json data/local/analysis/index.json
cp ../newvelles/analysis/entries/five-years/payload.json data/local/analysis/entries/five-years/payload.json
```

- [ ] **Step 2: Write the proxy module**

Create `newvelles_web/analysis.py`:

```python
"""Fetch the Analysis tab's data files from the public S3 bucket — the same
origin-proxy pattern as stories.py — so the front end can fetch same-origin
/analysis/index.json and /analysis/entries/<id>/payload.json.

Entry ids are validated before any path or URL is built."""
import json
import re
import urllib.request

BASE_URI = 'https://public-newvelles-data-bucket.s3-us-west-2.amazonaws.com/analysis'
LOCAL_BASE = './data/local/analysis'
ENTRY_ID = re.compile(r'^[a-z0-9-]{1,64}$')


def is_valid_entry_id(entry_id) -> bool:
    return isinstance(entry_id, str) and ENTRY_ID.match(entry_id) is not None


def _fetch(uri: str):
    with urllib.request.urlopen(uri) as response:
        return json.loads(response.read().decode('utf-8'))


def _load_local(path: str):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def get_index(local: bool = False):
    """The analysis index (schema 0.1.0), verbatim."""
    return _load_local(f'{LOCAL_BASE}/index.json') if local else _fetch(f'{BASE_URI}/index.json')


def get_entry_payload(entry_id: str, local: bool = False):
    """One entry's payload, verbatim. ValueError for an id outside ^[a-z0-9-]{1,64}$."""
    if not is_valid_entry_id(entry_id):
        raise ValueError(f'invalid entry id: {entry_id!r}')
    rel = f'entries/{entry_id}/payload.json'
    return _load_local(f'{LOCAL_BASE}/{rel}') if local else _fetch(f'{BASE_URI}/{rel}')
```

- [ ] **Step 3: Check the id guard by hand**

Run: `python3 -c "from newvelles_web.analysis import is_valid_entry_id as v; assert v('five-years'); assert not v('../x'); assert not v('Five'); assert not v(''); assert not v('a'*65); print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Routes**

In `newvelles_web/app.py`: add `from newvelles_web.analysis import get_entry_payload, get_index` next to the other imports. Extend the CORS dict with `r"/analysis/*": {"origins": "*"}`. Add after the `momentum()` route:

```python
@app.route("/analysis/index.json")
def analysis_index():
    """The Analysis tab's entry index (schema 0.1.0) from the public bucket"""
    return jsonify(get_index(local=CONFIG['PARAMS']['local'] == 'True'))


@app.route("/analysis/entries/<entry_id>/payload.json")
def analysis_entry(entry_id):
    """One analysis entry's payload from the public bucket"""
    try:
        doc = get_entry_payload(entry_id, local=CONFIG['PARAMS']['local'] == 'True')
    except ValueError:
        return jsonify({"error": "invalid entry id"}), 400
    except FileNotFoundError:
        return jsonify({"error": "unknown entry"}), 404
    return jsonify(doc)
```

- [ ] **Step 5: Vite proxy**

In `vite.config.js`, add to `server.proxy` after the `/momentum.json` entry:

```js
      '/analysis': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
```

- [ ] **Step 6: Verify with the Flask app in local mode**

Set `local: True` in `newvelles_web/config/newvelles-web.ini` for this check only. Start Flask on 5001 the way the repo does for the e2e gate (read `run.py`; if it listens on 5000, run `PORT=5001` or pass the port the way `docs/REDESIGN_STATUS.md` describes). Then:

```bash
curl -s localhost:5001/analysis/index.json | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['version'],[e['id'] for e in d['entries']])"
curl -s -o /dev/null -w '%{http_code}\n' localhost:5001/analysis/entries/five-years/payload.json
curl -s -o /dev/null -w '%{http_code}\n' localhost:5001/analysis/entries/nope/payload.json
curl -s -o /dev/null -w '%{http_code}\n' 'localhost:5001/analysis/entries/..%2Fx/payload.json'
```

Expected: `0.1.0 ['five-years']`, `200`, `404`, `400` or `404`. Stop Flask. Revert `local` to `False` before committing.

- [ ] **Step 7: Commit**

```bash
git add newvelles_web/analysis.py newvelles_web/app.py vite.config.js
git commit -m "feat: proxy /analysis/index.json and entry payloads from the public bucket

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: State, header tab strip, dispatch, d3 dependency (newvelles_web)

**Files:**
- Modify: `src/redesign/state.js`
- Modify: `src/redesign/render.js` (`renderBoard` header, `renderWire` header, `render`, `attachHandlers`)
- Modify: `src/redesign/main.js` (SOURCES, init)
- Modify: `src/redesign/styles.css` (header section)
- Modify: `package.json`
- Test: `tests/integration/redesign.test.js` (add a `describe('tab strip')`)

**Interfaces:**
- Produces (state.js): `view: 'board' | 'wire' | 'analysis'`, `entry: string | null`, `panel: string`; `goAnalysis()`, `selectEntry(id)`, `selectPanel(name)`, `refresh()`.
- Produces (render.js): `renderHeader(state, data)` used by both existing views and by Task 4's `renderAnalysis`. Handler attributes: `data-go-board`, `data-go-wire`, `data-go-analysis`, `data-entry`, `data-panel`, `data-analysis-retry`.
- Consumes (Task 4): `renderAnalysis(state)` and `mountAnalysis(container, state)` from `./analysis/view.js`, `configureAnalysis` from `./analysis/loader.js`. Until Task 4 lands, `render.js` imports them from a stub created in this task (Step 4).

- [ ] **Step 1: Write the failing tab-strip tests**

Append to `tests/integration/redesign.test.js` (inside the file, after the existing describes):

```js
describe('tab strip', () => {
  it('renders Today, Wire and Analysis tabs on the board with Today selected', () => {
    const tabs = container.querySelectorAll('.nv-tabs [role="tab"]');
    expect([...tabs].map((t) => t.textContent.trim().split(/\s/)[0])).toEqual(['Today', 'Wire', 'Analysis']);
    expect(container.querySelector('[data-go-board]').getAttribute('aria-selected')).toBe('true');
    expect(container.querySelector('[data-go-wire] .nv-tab-count').textContent).toBe(String(data.stories.filter((s) => s.kind === 'story').length));
  });

  it('has no "Full wire" ghost buttons any more', () => {
    expect(container.textContent).not.toContain('Full wire');
  });

  it('the Wire tab switches to the wire and the tab shows as selected', () => {
    container.querySelector('[data-go-wire]').click();
    expect(getState().view).toBe('wire');
    expect(container.querySelector('[data-go-wire]').getAttribute('aria-selected')).toBe('true');
    expect(container.querySelector('[data-wire-search]')).not.toBeNull();
  });

  it('the Analysis tab switches the view and hides the search box', () => {
    container.querySelector('[data-go-analysis]').click();
    expect(getState().view).toBe('analysis');
    expect(container.querySelector('[data-go-analysis]').getAttribute('aria-selected')).toBe('true');
    expect(container.querySelector('[data-board-search]')).toBeNull();
    expect(container.querySelector('[data-wire-search]')).toBeNull();
    expect(container.querySelector('[data-analysis-root]')).not.toBeNull();
  });
});
```

Also update the `beforeEach` `setState` call in that file to include the new fields: `setState({ view: 'board', query: '', cat: 'All', keyword: null, sort: 'rank', open: {}, entry: null, panel: 'timeline' });`

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run tests/integration/redesign.test.js -t "tab strip"`
Expected: FAIL (no `.nv-tabs`).

- [ ] **Step 3: State**

In `src/redesign/state.js`: update the doc comment to list `view 'board' | 'wire' | 'analysis'`, `entry` and `panel`. Change the initial state to:

```js
let state = {
  view: 'board',
  query: '',
  cat: 'All',
  keyword: null,
  sort: 'rank',
  open: {},
  entry: null,       // analysis entry id; null = newest
  panel: 'timeline', // analysis panel name
};
```

Append:

```js
/** The Analysis tab. Keeps entry and panel so coming back lands where you were. */
export function goAnalysis() {
  setState({ view: 'analysis', query: '', keyword: null });
}

export function selectEntry(entry) {
  setState({ view: 'analysis', entry, panel: 'timeline' });
}

export function selectPanel(panel) {
  setState({ view: 'analysis', panel });
}

/** Re-run listeners without changing state (used when async data arrives). */
export function refresh() {
  setState({});
}
```

- [ ] **Step 4: Stub the analysis view module (replaced in Task 4)**

Create `src/redesign/analysis/view.js`:

```js
export function renderAnalysis() {
  return `<section class="an-root" data-analysis-root><p class="an-stub">Analysis view lands in Task 4.</p></section>`;
}
export function mountAnalysis() {}
```

Create `src/redesign/analysis/loader.js`:

```js
export function configureAnalysis() {}
```

- [ ] **Step 5: Shared header in render.js**

Add `goAnalysis` to the `./state.js` import list. Add `import { mountAnalysis, renderAnalysis } from './analysis/view.js';` after the state import.

Add this function above `renderBoard`:

```js
/**
 * Brand block + tab strip + view-specific actions. One header for all three
 * views so the strip never moves.
 */
export function renderHeader(state, data, { dateline, actions }) {
  const { view } = state;
  const storyCount = data.stories.filter((s) => s.kind === 'story').length;
  const tab = (attr, label, key, count) =>
    `<button class="nv-tab" role="tab" ${attr} aria-selected="${view === key}">${label}${
      count ? `<span class="nv-tab-count">${esc(count)}</span>` : ''
    }</button>`;
  return `
  <header class="nv-header">
    <div class="nv-brand-block">
      <div class="nv-brand">newvelles</div>
      <div class="nv-dateline">${dateline}</div>
    </div>
    <nav class="nv-tabs" role="tablist" aria-label="Views">
      ${tab('data-go-board', 'Today', 'board')}
      ${tab('data-go-wire', 'Wire', 'wire', storyCount)}
      ${tab('data-go-analysis', 'Analysis', 'analysis')}
    </nav>
    <div class="nv-header-actions">${actions}</div>
  </header>`;
}
```

In `renderBoard(data)`: change the signature to `renderBoard(data, state)`. Replace its `<header class="nv-header">…</header>` block with:

```js
  ${renderHeader(state, data, {
    dateline: `${esc(date)} · updated ${esc(time)} · ${newsCount} stories from ${doc.feeds} feeds`,
    actions: `<div class="nv-search">
        <span class="nv-icon" aria-hidden="true">⌕</span>
        <input type="search" data-board-search name="board-search" id="board-search" placeholder="Search all stories" value="" aria-label="Search all stories">
      </div>`,
  })}
```

Delete the `<button class="nv-ghost" data-go-wire>Full wire →</button>` line and the `See all ${newsCount} stories in the wire →` button in the board.

In `renderWire(data, state)`: replace its `<header class="nv-header">…</header>` block with:

```js
  ${renderHeader(state, data, {
    dateline: `${esc(date)} · ${stories.length} stories · ${doc.article_count} articles · ${doc.feeds} feeds · click a story to open its coverage`,
    actions: `<div class="nv-search nv-search--wire">
        <span class="nv-icon" aria-hidden="true">⌕</span>
        <input type="search" data-wire-search name="wire-search" id="wire-search" placeholder="Filter stories, sources, headlines" value="${esc(query)}" aria-label="Filter stories">
        ${query ? '<button class="nv-clear" data-clear-query aria-label="Clear search">×</button>' : ''}
      </div>
      <div class="nv-sort" role="group" aria-label="Sort stories">
        ${sortButton('rank', 'Ranked')}
        ${sortButton('newest', 'Newest')}
        ${sortButton('outlets', 'Most covered')}
      </div>`,
  })}
```

(`sortButton` is defined above that block already. The `← Today` back button goes away; the Today tab replaces it.)

In `render(container, data)`: replace the `container.innerHTML = …` statement with:

```js
  const body =
    state.view === 'board'
      ? renderBoard(data, state)
      : state.view === 'wire'
        ? renderWire(data, state)
        : `${renderHeader(state, data, { dateline: formatAnalysisDateline(data), actions: '' })}${renderAnalysis(state)}`;
  container.innerHTML = `<div class="nv-shell"><div class="nv-page">${body}</div></div>`;
  if (state.view === 'analysis') mountAnalysis(container.querySelector('[data-analysis-root]'), state);
```

Add near `formatDateline`:

```js
function formatAnalysisDateline(data) {
  const { date } = formatDateline(data.doc);
  return `${esc(date)} · the archive since 2021, in numbers`;
}
```

In `attachHandlers`, add before the `data-go-wire` branch:

```js
    } else if (on('data-go-analysis')) {
      goAnalysis();
    } else if ((el = on('data-entry'))) {
      selectEntry(el.getAttribute('data-entry'));
    } else if ((el = on('data-panel'))) {
      selectPanel(el.getAttribute('data-panel'));
    } else if (on('data-analysis-retry')) {
      refresh();
```

and add `selectEntry`, `selectPanel`, `refresh` to the state import.

- [ ] **Step 6: Styles for the strip**

In `src/redesign/styles.css`, after `.nv-header-actions { … }` add:

```css
.nv-header-actions { margin-left: auto; }
.nv-tabs { display: flex; gap: 2px; margin-left: 16px; align-self: flex-end; margin-bottom: -14px; }
.nv-tab { position: relative; background: none; border: 0; padding: 10px 12px 14px; font: 500 13px var(--nv-font); color: var(--nv-text-muted); letter-spacing: -0.005em; transition: color 0.12s ease; }
.nv-tab:hover { color: var(--nv-text); }
.nv-tab[aria-selected="true"] { color: var(--nv-text); }
.nv-tab::after { content: ''; position: absolute; left: 12px; right: 12px; bottom: -1px; height: 2px; background: transparent; border-radius: 1px; }
.nv-tab[aria-selected="true"]::after { background: var(--nv-accent); }
.nv-tab-count { font: 500 10px var(--nv-mono); color: var(--nv-text-faint); margin-left: 6px; letter-spacing: 0.02em; }
.nv-tab[aria-selected="true"] .nv-tab-count { color: var(--nv-accent); }
```

Keep the existing `.nv-header-actions` rule; the added line only adds `margin-left: auto`. Inside the existing `@media (max-width: 760px)` block add:

```css
  .nv-tabs { order: 3; width: 100%; margin-left: -12px; }
  .nv-header-actions { margin-left: 0; width: 100%; }
```

At the top of `styles.css` add `@import './analysis/styles.css';` (Vite inlines it). Create an empty `src/redesign/analysis/styles.css` with the comment `/* Analysis view — filled in Task 4 */`.

- [ ] **Step 7: Data modes and d3**

In `src/redesign/main.js`, add to each `SOURCES` entry an `analysis` object:

```js
  fixture: {
    stories: '/data/fixtures/stories_v0.3.0.json',
    momentum: '/data/fixtures/momentum_v0.3.0.json',
    analysis: { index: '/data/fixtures/analysis/index.json', entry: (id) => `/data/fixtures/analysis/entries/${id}/payload.json` },
  },
  live: {
    stories: '/stories.json',
    momentum: '/momentum.json',
    analysis: { index: '/analysis/index.json', entry: (id) => `/analysis/entries/${id}/payload.json` },
  },
  local: {
    stories: '/data/local/stories.json',
    momentum: '/data/local/momentum.json',
    analysis: { index: '/data/local/analysis/index.json', entry: (id) => `/data/local/analysis/entries/${id}/payload.json` },
  },
```

Import `configureAnalysis` from `./analysis/loader.js` and, in `init()` right after `const source = dataSource();`, add `configureAnalysis({ index: source.analysis.index, entry: source.analysis.entry, fetchJson });`.

Install d3: `npm install d3@7` (adds `dependencies.d3`). Confirm `package-lock.json` changed.

- [ ] **Step 8: Run the integration suite**

Run: `npx vitest run --dir tests/integration`
Expected: all pass, including the four new tab-strip tests. If an existing test clicked the removed "See all … in the wire" button, change it to click `[data-go-wire]`.

- [ ] **Step 9: Commit**

```bash
git add package.json package-lock.json src/redesign/state.js src/redesign/render.js src/redesign/main.js src/redesign/styles.css src/redesign/analysis/ tests/integration/redesign.test.js
git commit -m "feat: header tab strip (Today, Wire, Analysis) and analysis view dispatch

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Loader, view shell, styles, fixture, tests (newvelles_web)

**Files:**
- Create: `src/redesign/analysis/loader.js` (replace stub)
- Create: `src/redesign/analysis/view.js` (replace stub)
- Create: `src/redesign/analysis/panels/index.js`
- Create: `src/redesign/analysis/styles.css` (replace empty)
- Create: `scripts/make_analysis_fixture.py`, `data/fixtures/analysis/index.json`, `data/fixtures/analysis/entries/five-years/payload.json`
- Test: `tests/unit/analysisLoader.test.js`, `tests/integration/analysis.test.js`

**Interfaces:**
- Produces (loader.js): `configureAnalysis({ index, entry, fetchJson })`, `resetAnalysisCache()`, `isValidEntryId(id)`, `getIndex()`, `getIndexError()`, `loadIndex()`, `resolveEntry(index, entryId)`, `getEntryPayload(id)`, `getEntryError(id)`, `loadEntry(entry)`.
- Produces (panels/index.js): `PANEL_LABELS`, `mountPanel(name, section, ctx)`. Registry starts empty; Tasks 5 to 8 add panels.
- Consumes: `buildContext(payload, root)` from `./context.js` (Task 5). Until then `view.js` imports a stub created here.

- [ ] **Step 1: Fixture script and fixture**

Create `scripts/make_analysis_fixture.py`:

```python
"""Trim a real analysis payload into the test fixture.

Usage: python3 scripts/make_analysis_fixture.py data/local/analysis/entries/five-years/payload.json
Writes data/fixtures/analysis/index.json and .../entries/five-years/payload.json (< 150 KB).
"""
import json
import sys
from pathlib import Path

src = Path(sys.argv[1])
d = json.loads(src.read_text(encoding="utf-8"))

daily = d["daily"][:120]
weekly = d["weekly"][:20]
events = d["events"][:3]
ledger = d["ledger"][:5]
first_major = next(iter(d["drill"]))
dv = d["drill"][first_major]
drill = {first_major: {"order": dv["order"], "weekly": dv["weekly"][:20], "top": dv["top"][:5], "top_yearly": dv["top_yearly"][:5]}}
uids = {e["uid"] for e in events} | {t["uid"] for t in drill[first_major]["top"] + drill[first_major]["top_yearly"] if "uid" in t}
clusters = {u: d["clusters"][u] for u in uids if u in d["clusters"]}
for c in clusters.values():
    c["members"] = c["members"][:5]
lifetimes = {**d["lifetimes"], "base": d["lifetimes"]["base"][:200], "named": d["lifetimes"]["named"][:10]}
archetypes = {**d["archetypes"], "clusters": [{**c, "members": c["members"][:5]} for c in d["archetypes"]["clusters"]]}
categories = {**d["categories"], "subs": d["categories"]["subs"][:8]}

fixture = {
    "version": d["version"], "entry": d["entry"],
    "meta": {**d["meta"], "first_day": daily[0]["d"], "last_day": daily[-1]["d"]},
    "daily": daily, "weekly": weekly, "sections": d["sections"], "ledger": ledger,
    "annotations": d["annotations"][:2], "events": events, "drill": drill, "clusters": clusters,
    "lifetimes": lifetimes, "archetypes": archetypes, "discords": d["discords"][:1],
    "stats": d["stats"], "categories": categories,
}
out = Path("data/fixtures/analysis/entries") / d["entry"] / "payload.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(fixture, separators=(",", ":")), encoding="utf-8")

index = {
    "version": "0.1.0", "generated": "2026-09-19T00:00:00Z",
    "entries": [{
        "id": d["entry"], "number": 1, "title": "Five years of news cycles",
        "summary": "Fixture entry: a trimmed slice of the real payload.",
        "first_day": daily[0]["d"], "last_day": daily[-1]["d"], "published": "2026-09-19",
        "links": {"post": "", "code": "https://github.com/glhuilli/newvelles/tree/main/analysis"},
        "panels": ["timeline", "ledger", "lifetimes", "archetypes", "stats", "categories", "topstories", "learnings"],
        "payload": f"/analysis/entries/{d['entry']}/payload.json",
        "stats": {"runs": d["meta"]["runs"], "stories": d["meta"]["stories"], "days": len(daily), "majors": len(d["categories"]["majors_order"])},
    }],
}
Path("data/fixtures/analysis/index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
print(f"fixture payload: {out.stat().st_size / 1024:.0f} KB")
```

Run: `python3 scripts/make_analysis_fixture.py data/local/analysis/entries/five-years/payload.json`
Expected: `fixture payload: NN KB` with NN under 150. If over, cut `lifetimes.base` to 100 and `daily` to 90.

If a key named in the script is absent from the real payload (for example `top_yearly` inside a drill view), read the payload's shape with `python3 -c "import json;d=json.load(open(...));print({k:type(v).__name__ for k,v in d['drill'][next(iter(d['drill']))].items()})"` and adjust the script to the real key names. The fixture must be a strict subset of the real shape.

- [ ] **Step 2: Write the failing loader unit test**

Create `tests/unit/analysisLoader.test.js`:

```js
import { describe, it, expect, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import {
  configureAnalysis, resetAnalysisCache, isValidEntryId, getIndex, getIndexError,
  loadIndex, resolveEntry, getEntryPayload, getEntryError, loadEntry,
} from '../../src/redesign/analysis/loader.js';

const index = JSON.parse(readFileSync('data/fixtures/analysis/index.json', 'utf-8'));
const payload = JSON.parse(readFileSync('data/fixtures/analysis/entries/five-years/payload.json', 'utf-8'));

let calls;
beforeEach(() => {
  calls = [];
  resetAnalysisCache();
  configureAnalysis({
    index: '/idx',
    entry: (id) => `/e/${id}`,
    fetchJson: async (url) => {
      calls.push(url);
      if (url === '/idx') return structuredClone(index);
      if (url === '/e/five-years') return structuredClone(payload);
      throw new Error(`404 ${url}`);
    },
  });
});

describe('isValidEntryId', () => {
  it('accepts lowercase ids and rejects everything else', () => {
    expect(isValidEntryId('five-years')).toBe(true);
    expect(isValidEntryId('Five')).toBe(false);
    expect(isValidEntryId('../x')).toBe(false);
    expect(isValidEntryId('')).toBe(false);
    expect(isValidEntryId(null)).toBe(false);
  });
});

describe('loadIndex', () => {
  it('fetches once and memoizes', async () => {
    expect(getIndex()).toBeNull();
    await loadIndex();
    await loadIndex();
    expect(calls.filter((u) => u === '/idx').length).toBe(1);
    expect(getIndex().entries[0].id).toBe('five-years');
  });

  it('records an error and allows a retry', async () => {
    configureAnalysis({ index: '/missing' });
    await loadIndex().catch(() => {});
    expect(getIndexError()).toMatch(/404/);
    configureAnalysis({ index: '/idx' });
    await loadIndex();
    expect(getIndex()).not.toBeNull();
    expect(getIndexError()).toBeNull();
  });
});

describe('resolveEntry', () => {
  it('returns the newest entry for null or an unknown id', () => {
    expect(resolveEntry(index, null).id).toBe('five-years');
    expect(resolveEntry(index, 'nope').id).toBe('five-years');
    expect(resolveEntry(index, 'five-years').id).toBe('five-years');
  });
});

describe('loadEntry', () => {
  it('fetches the payload for a valid entry and memoizes', async () => {
    const entry = index.entries[0];
    await loadEntry(entry);
    await loadEntry(entry);
    expect(calls.filter((u) => u === '/e/five-years').length).toBe(1);
    expect(getEntryPayload('five-years').entry).toBe('five-years');
  });

  it('refuses an invalid id without fetching', async () => {
    await expect(loadEntry({ id: '../x' })).rejects.toThrow(/invalid/);
    expect(calls.length).toBe(0);
    expect(getEntryError('../x')).toMatch(/invalid/);
  });
});
```

- [ ] **Step 3: Run to verify failure**

Run: `npx vitest run tests/unit/analysisLoader.test.js`
Expected: FAIL (exports missing).

- [ ] **Step 4: Loader**

Replace `src/redesign/analysis/loader.js`:

```js
/**
 * Analysis data: an index of entries plus one payload per entry. Nothing is
 * fetched at page load; the index loads on the first switch to the tab and a
 * payload when its entry is opened. Both memoize in module scope.
 */
const ENTRY_ID = /^[a-z0-9-]{1,64}$/;

async function defaultFetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: ${response.status} ${response.statusText}`);
  return response.json();
}

let cfg = {
  index: '/analysis/index.json',
  entry: (id) => `/analysis/entries/${id}/payload.json`,
  fetchJson: defaultFetchJson,
};

let cache;
export function resetAnalysisCache() {
  cache = { index: null, indexError: null, indexPromise: null, payloads: {}, errors: {}, promises: {} };
}
resetAnalysisCache();

export function configureAnalysis(overrides = {}) {
  cfg = { ...cfg, ...overrides };
}

export function isValidEntryId(id) {
  return typeof id === 'string' && ENTRY_ID.test(id);
}

export const getIndex = () => cache.index;
export const getIndexError = () => cache.indexError;
export const getEntryPayload = (id) => cache.payloads[id] || null;
export const getEntryError = (id) => cache.errors[id] || null;

export function loadIndex() {
  if (cache.index) return Promise.resolve(cache.index);
  if (!cache.indexPromise) {
    cache.indexPromise = cfg
      .fetchJson(cfg.index)
      .then((doc) => {
        if (!doc || !Array.isArray(doc.entries)) throw new Error('index.json has no entries');
        cache.index = doc;
        cache.indexError = null;
        return doc;
      })
      .catch((error) => {
        cache.indexError = String(error.message || error);
        throw error;
      })
      .finally(() => {
        cache.indexPromise = null;
      });
  }
  return cache.indexPromise;
}

/** Newest first is the index order; null or an unknown id resolves to entries[0]. */
export function resolveEntry(index, entryId) {
  const entries = (index && index.entries) || [];
  return entries.find((e) => e.id === entryId) || entries[0] || null;
}

export function loadEntry(entry) {
  const id = entry && entry.id;
  if (!isValidEntryId(id)) {
    cache.errors[id] = `invalid entry id: ${id}`;
    return Promise.reject(new Error(cache.errors[id]));
  }
  if (cache.payloads[id]) return Promise.resolve(cache.payloads[id]);
  if (!cache.promises[id]) {
    cache.promises[id] = cfg
      .fetchJson(cfg.entry(id))
      .then((doc) => {
        cache.payloads[id] = doc;
        delete cache.errors[id];
        return doc;
      })
      .catch((error) => {
        cache.errors[id] = String(error.message || error);
        throw error;
      })
      .finally(() => {
        delete cache.promises[id];
      });
  }
  return cache.promises[id];
}
```

- [ ] **Step 5: Run the unit test**

Run: `npx vitest run tests/unit/analysisLoader.test.js`
Expected: PASS.

- [ ] **Step 6: Write the failing view integration test**

Create `tests/integration/analysis.test.js`:

```js
/**
 * Integration: the Analysis view against the trimmed fixture in jsdom.
 * Panel-specific assertions are appended by the panel tasks.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { joinMomentum } from '../../src/redesign/data.js';
import { attachHandlers, render } from '../../src/redesign/render.js';
import { getState, setState, subscribe } from '../../src/redesign/state.js';
import { configureAnalysis, resetAnalysisCache } from '../../src/redesign/analysis/loader.js';

const storiesDoc = JSON.parse(readFileSync('data/fixtures/stories_v0.3.0.json', 'utf-8'));
const momentumDoc = JSON.parse(readFileSync('data/fixtures/momentum_v0.3.0.json', 'utf-8'));
const data = { doc: storiesDoc, stories: joinMomentum(storiesDoc, momentumDoc) };
const index = JSON.parse(readFileSync('data/fixtures/analysis/index.json', 'utf-8'));
const payload = JSON.parse(readFileSync('data/fixtures/analysis/entries/five-years/payload.json', 'utf-8'));
const entry = index.entries[0];

let container;
let failIndex = false;

function mount() {
  document.body.innerHTML = '<div id="app"></div>';
  container = document.getElementById('app');
  attachHandlers(container);
  subscribe(() => render(container, data));
  render(container, data);
}

const q = (sel) => container.querySelector(sel);
const until = (fn) => vi.waitFor(fn, { timeout: 2000 });

beforeEach(() => {
  failIndex = false;
  resetAnalysisCache();
  configureAnalysis({
    index: '/idx',
    entry: (id) => `/e/${id}`,
    fetchJson: async (url) => {
      if (url === '/idx') {
        if (failIndex) throw new Error('503 index');
        return structuredClone(index);
      }
      if (url === '/e/five-years') return structuredClone(payload);
      throw new Error(`404 ${url}`);
    },
  });
  setState({ view: 'analysis', query: '', cat: 'All', keyword: null, sort: 'rank', open: {}, entry: null, panel: 'timeline' });
  mount();
});

describe('analysis shell', () => {
  it('shows a loading state, then the entries row and entry header from the index', async () => {
    expect(q('[data-analysis-root] .an-loading')).not.toBeNull();
    await until(() => expect(q('.an-entry-title')).not.toBeNull());
    expect(q('.an-entry.is-active [data-entry]') || q('.an-entry.is-active')).not.toBeNull();
    expect(q('.an-entry-head h2').textContent).toBe(entry.title);
    expect(q('.an-lede').textContent).toBe(entry.summary);
    expect(q('.an-entry-links a[href="' + entry.links.code + '"]')).not.toBeNull();
    expect([...container.querySelectorAll('.an-entry-stats .nv-stat-value')].map((e) => e.textContent)).toEqual([
      entry.stats.runs.toLocaleString(), entry.stats.stories.toLocaleString(),
      entry.stats.days.toLocaleString(), String(entry.stats.majors),
    ]);
  });

  it('renders one pill per panel in index order, timeline active, and one section per panel', async () => {
    await until(() => expect(q('.an-pills')).not.toBeNull());
    const pills = [...container.querySelectorAll('.an-pills [data-panel]')];
    expect(pills.map((p) => p.getAttribute('data-panel'))).toEqual(entry.panels);
    expect(q('.an-pills [data-panel="timeline"]').classList.contains('nv-pill--active')).toBe(true);
    for (const name of entry.panels) expect(q(`[data-panel-section="${name}"]`)).not.toBeNull();
    expect(q('[data-panel-section="timeline"]').hidden).toBe(false);
    expect(q('[data-panel-section="ledger"]').hidden).toBe(true);
  });

  it('a pill click switches the panel', async () => {
    await until(() => expect(q('.an-pills [data-panel="ledger"]')).not.toBeNull());
    q('.an-pills [data-panel="ledger"]').click();
    expect(getState().panel).toBe('ledger');
    await until(() => expect(q('[data-panel-section="ledger"]').hidden).toBe(false));
    expect(q('[data-panel-section="timeline"]').hidden).toBe(true);
  });

  it('an unknown panel name renders the placeholder, not an error', async () => {
    await until(() => expect(q('.an-pills')).not.toBeNull());
    setState({ panel: 'mystery' });
    await until(() => expect(q('[data-panel-section="mystery"] .an-stub')).not.toBeNull());
  });

  it('an index failure shows an inline retry that recovers', async () => {
    failIndex = true;
    resetAnalysisCache();
    setState({ view: 'analysis' });
    await until(() => expect(q('[data-analysis-retry]')).not.toBeNull());
    failIndex = false;
    q('[data-analysis-retry]').click();
    await until(() => expect(q('.an-entry-title')).not.toBeNull());
  });
});
```

- [ ] **Step 7: Run to verify failure**

Run: `npx vitest run tests/integration/analysis.test.js`
Expected: FAIL (stub view has no `.an-loading`).

- [ ] **Step 8: Panel registry and context stub**

Create `src/redesign/analysis/panels/index.js`:

```js
/**
 * Panel registry. Each panel module exports mount(section, ctx). Names come
 * from the entry's `panels` list; an unknown name gets a placeholder so the
 * index can add or drop panels without a code change here.
 */
export const PANEL_LABELS = {
  timeline: 'Timeline',
  ledger: 'Ledger',
  lifetimes: 'Lifetimes',
  archetypes: 'Archetypes',
  stats: 'Stats',
  categories: 'Categories',
  topstories: 'Top stories',
  learnings: 'Learnings',
};

const PANELS = {};

export function registerPanel(name, mod) {
  PANELS[name] = mod;
}

export function mountPanel(name, section, ctx) {
  const mod = PANELS[name];
  if (!mod) {
    section.innerHTML = `<p class="an-stub">The “${PANEL_LABELS[name] || name}” panel is not available in this build.</p>`;
    return;
  }
  mod.mount(section, ctx);
}
```

Create `src/redesign/analysis/context.js` as a stub (Task 5 fills it):

```js
export function buildContext(payload, root) {
  return { D: payload, root };
}
```

- [ ] **Step 9: View**

Replace `src/redesign/analysis/view.js`:

```js
/**
 * The Analysis view: entries row, entry header, panel pills, one section per
 * panel. renderAnalysis() returns HTML from whatever the loader already has;
 * mountAnalysis() kicks off loads (each completion calls refresh() so the
 * view re-renders) and mounts the active panel into its section.
 */
import { refresh } from '../state.js';
import { buildContext } from './context.js';
import { getEntryError, getEntryPayload, getIndex, getIndexError, loadEntry, loadIndex, resolveEntry } from './loader.js';
import { PANEL_LABELS, mountPanel } from './panels/index.js';

// Local copy of render.js's esc(): view.js must not import render.js (render.js imports this file).
const esc = (text) => String(text ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtRange = (e) => `${monthYear(e.first_day)} – ${monthYear(e.last_day)}`;
function monthYear(iso) {
  const d = new Date(iso + 'T00:00:00Z');
  return d.toLocaleString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' });
}
const pad2 = (n) => String(n).padStart(2, '0');

function renderEntries(index, current) {
  const cards = index.entries
    .map(
      (e) => `<button class="an-entry${e.id === current.id ? ' is-active' : ''}" type="button" data-entry="${esc(e.id)}" ${
        e.id === current.id ? 'aria-current="true"' : ''
      }>
        <span class="an-entry-num">${pad2(e.number)}</span>
        <span class="an-entry-title">${esc(e.title)}</span>
        <span class="an-entry-range">${esc(fmtRange(e))} · published ${esc(monthYear(e.published))}</span>
      </button>`
    )
    .join('');
  return `<div class="an-entries">
    <div class="an-entries-head"><span class="nv-rail-label">Entries</span><span class="an-meta">${index.entries.length} published</span></div>
    <div class="an-entry-list">${cards}
      <div class="an-entry an-entry--next">The next entry appears here when a new analysis is published. Each entry keeps its own panels below.</div>
    </div>
  </div>`;
}

function renderEntryHead(e) {
  const stat = (v, label) => `<div class="nv-stat"><span class="nv-stat-value">${esc(v)}</span><span class="nv-stat-label">${label}</span></div>`;
  const links = [
    e.links.post ? `<a href="${esc(e.links.post)}">Read the methods post →</a>` : '',
    e.links.code ? `<a href="${esc(e.links.code)}" target="_blank" rel="noopener">Analysis code on GitHub →</a>` : '',
  ].join('');
  return `<header class="an-entry-head">
    <div class="nv-kicker">Entry ${pad2(e.number)} · ${esc(fmtRange(e))}</div>
    <h2>${esc(e.title)}</h2>
    <p class="an-lede">${esc(e.summary)}</p>
    <div class="an-entry-stats">
      ${stat(e.stats.runs.toLocaleString(), 'runs replayed')}
      ${stat(e.stats.stories.toLocaleString(), 'unique stories')}
      ${stat(e.stats.days.toLocaleString(), 'days')}
      ${stat(String(e.stats.majors), 'major categories')}
    </div>
    <div class="an-entry-links">${links}</div>
  </header>`;
}

function renderPanels(e, panel, payload) {
  const names = e.panels.includes(panel) ? e.panels : [...e.panels, panel];
  const pills = names
    .map(
      (n) => `<button class="nv-pill${n === panel ? ' nv-pill--active' : ''}" role="tab" data-panel="${esc(n)}" aria-selected="${n === panel}">${esc(
        PANEL_LABELS[n] || n
      )}</button>`
    )
    .join('');
  const meta = payload
    ? `${payload.meta.runs.toLocaleString()} runs · ${payload.meta.stories.toLocaleString()} stories · ${esc(payload.meta.first_day)} → ${esc(payload.meta.last_day)}`
    : '';
  const sections = names
    .map((n) => `<section class="an-panel" data-panel-section="${esc(n)}" ${n === panel ? '' : 'hidden'}></section>`)
    .join('');
  return `<div class="an-strip"><div class="nv-pills" role="tablist" aria-label="Analysis panels">${pills}</div><div class="an-meta">${meta}</div></div>${sections}`;
}

const retry = (msg) => `<div class="an-error"><p>${esc(msg)}</p><button class="nv-ghost" data-analysis-retry>Try again</button></div>`;

export function renderAnalysis(state) {
  const index = getIndex();
  let body;
  if (!index) {
    body = getIndexError() ? retry(`Could not load the analysis index (${getIndexError()}).`) : `<p class="an-loading">Loading the archive…</p>`;
  } else {
    const entry = resolveEntry(index, state.entry);
    if (!entry) body = `<p class="an-stub">No analysis entries published yet.</p>`;
    else {
      const payload = getEntryPayload(entry.id);
      const err = getEntryError(entry.id);
      body =
        renderEntries(index, entry) +
        renderEntryHead(entry) +
        (payload
          ? renderPanels(entry, state.panel, payload)
          : err
            ? retry(`Could not load this entry (${err}).`)
            : `<p class="an-loading">Loading ${esc(entry.title)}…</p>`);
    }
  }
  return `<section class="an-root" data-analysis-root>${body}<div class="an-tooltip" id="tooltip" role="status"></div></section>`;
}

/** A recorded error means "tried and failed"; the retry button clears errors first (retryAnalysis). */
export function mountAnalysis(root, state) {
  if (!root) return;
  const index = getIndex();
  if (!index) {
    if (!getIndexError()) loadIndex().then(refresh, refresh);
    return;
  }
  const entry = resolveEntry(index, state.entry);
  if (!entry) return;
  const payload = getEntryPayload(entry.id);
  if (!payload) {
    if (!getEntryError(entry.id)) loadEntry(entry).then(refresh, refresh);
    return;
  }
  const section = root.querySelector(`[data-panel-section="${state.panel}"]`);
  if (!section) return;
  const ctx = buildContext(payload, root);
  mountPanel(state.panel, section, ctx);
}
```

Retry wiring. In `loader.js` add:

```js
export function clearAnalysisErrors() {
  cache.indexError = null;
  cache.errors = {};
}
```

In `state.js` add (loader.js imports nothing from state.js, so there is no cycle):

```js
import { clearAnalysisErrors } from './analysis/loader.js';

/** Retry button in the analysis view: forget recorded errors, re-render, which re-attempts the load. */
export function retryAnalysis() {
  clearAnalysisErrors();
  setState({});
}
```

In `render.js` `attachHandlers`, the `data-analysis-retry` branch calls `retryAnalysis()` (import it from `./state.js`; the Task 3 stub used `refresh()`).

- [ ] **Step 10: Analysis styles**

Replace `src/redesign/analysis/styles.css` with the shell styles plus the old dashboard CSS scoped under `.an-root` with tokens mapped:

```css
/* ---------- Analysis view: shell ---------- */
.an-root { display: flex; flex-direction: column; gap: 16px; }
.an-loading, .an-stub { font-size: 12.5px; color: var(--nv-text-dim); line-height: 1.6; max-width: 70ch; margin: 0; }
.an-error { display: flex; flex-direction: column; gap: 10px; align-items: flex-start; font-size: 12.5px; color: var(--nv-text-secondary); }
.an-meta { font: 500 10.5px var(--nv-mono); color: var(--nv-text-dim); letter-spacing: 0.02em; white-space: nowrap; }
.an-entries { display: flex; flex-direction: column; gap: 10px; }
.an-entries-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.an-entry-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.an-entry { display: flex; flex-direction: column; gap: 5px; text-align: left; background: var(--nv-raised); border: 1px solid var(--nv-border); border-radius: 10px; padding: 13px 15px; color: var(--nv-text-secondary); transition: border-color 0.12s ease; }
.an-entry:hover { border-color: var(--nv-accent); }
.an-entry.is-active { border-color: var(--nv-accent); background: linear-gradient(160deg, #232532, #1b1d2b); }
.an-entry-num { font: 500 10px var(--nv-mono); letter-spacing: 0.12em; color: var(--nv-accent); }
.an-entry-title { font-size: 14.5px; color: var(--nv-text); line-height: 1.3; }
.an-entry-range { font-size: 11px; color: var(--nv-text-dim); }
.an-entry--next { border-style: dashed; background: transparent; color: var(--nv-text-faint); font-size: 11.5px; line-height: 1.5; justify-content: center; cursor: default; }
.an-entry--next:hover { border-color: var(--nv-border); }
.an-entry-head { display: flex; flex-direction: column; gap: 10px; border-top: 1px solid var(--nv-hairline-12); padding-top: 18px; }
.an-entry-head h2 { font-size: 27px; line-height: 1.18; letter-spacing: -0.022em; font-weight: 400; margin: 0; text-wrap: balance; }
.an-lede { font-size: 14px; line-height: 1.55; color: var(--nv-text-secondary); margin: 0; max-width: 68ch; text-wrap: pretty; }
.an-entry-stats { display: flex; gap: 26px; flex-wrap: wrap; align-items: flex-end; }
.an-entry-stats .nv-stat-value { font-size: 20px; }
.an-entry-links { display: flex; gap: 16px; font-size: 12px; }
.an-strip { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; border-top: 1px solid var(--nv-hairline-12); padding-top: 14px; }
.an-strip .nv-pills { flex: 1; }
.an-panel { display: flex; flex-direction: column; gap: 12px; }
.an-panel[hidden] { display: none; }

/* ---------- Ported dashboard styles, scoped. Old token names map to Nocturne. ---------- */
.an-root {
  --page: var(--nv-page); --surface: var(--nv-surface);
  --ink: var(--nv-text); --ink-2: var(--nv-text-secondary); --muted: var(--nv-text-dim);
  --grid: var(--nv-hairline-10); --baseline: var(--nv-hairline-16); --ring: var(--nv-hairline-12);
  --accent: var(--nv-accent); --dim: var(--nv-track);
  --s1: #3987e5; --s2: #008300; --s3: #d55181; --s4: #c98500; --s5: #199e70; --s6: #d95926; --s7: #9085e9; --s8: #6b6f80;
  font-size: 14px; line-height: 1.5;
}
.an-root .panel-note { color: var(--ink-2); font-size: 13px; margin: 0; max-width: 90ch; }
.an-root .panel-note b { color: var(--ink); }
.an-root .chart-box { background: var(--surface); border: 1px solid var(--ring); border-radius: 10px; padding: 14px 16px 10px; }
.an-root .box-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 6px; }
.an-root .box-title { font-size: 12.5px; font-weight: 500; }
.an-root .legend { display: flex; gap: 12px; flex-wrap: wrap; }
.an-root .legend .li { display: inline-flex; align-items: center; gap: 5px; font: 11px var(--nv-mono); color: var(--ink-2); }
.an-root .legend .sw { width: 9px; height: 9px; border-radius: 2.5px; }
.an-root .controls { display: flex; gap: 6px; flex-wrap: wrap; }
.an-root .controls button { font: 11px var(--nv-mono); letter-spacing: 0.06em; padding: 3px 10px; border-radius: 999px; border: 1px solid var(--nv-border); background: transparent; color: var(--ink-2); cursor: pointer; }
.an-root .controls button[aria-pressed="true"] { background: var(--nv-wash-16); border-color: var(--accent); color: var(--nv-accent-tint); }
.an-root svg { display: block; width: 100%; height: auto; }
.an-root svg text { font-family: var(--nv-font); }
.an-root .axis text { fill: var(--muted); font-size: 11px; }
.an-root .axis line, .an-root .axis path { stroke: var(--baseline); }
.an-root .gridline { stroke: var(--grid); stroke-width: 1; shape-rendering: crispEdges; }
.an-root .an-tooltip { position: fixed; pointer-events: none; z-index: 10; display: none; background: var(--nv-raised); color: var(--ink); border: 1px solid var(--nv-border); border-radius: 8px; padding: 7px 10px; font-size: 12px; line-height: 1.45; box-shadow: 0 6px 20px rgba(0,0,0,0.35); max-width: 280px; }
.an-root .an-tooltip .t-date { font: 10px var(--nv-mono); letter-spacing: 0.08em; color: var(--muted); text-transform: uppercase; }
.an-root .an-tooltip .t-strong { font-weight: 500; }
.an-root .ledger-wrap { max-height: calc(100vh - 260px); overflow: auto; }
.an-root table.ledger { width: 100%; border-collapse: collapse; font-size: 13px; }
.an-root table.ledger th { position: sticky; top: 0; background: var(--surface); z-index: 1; text-align: left; font: 500 10px var(--nv-mono); letter-spacing: 0.11em; text-transform: uppercase; color: var(--muted); padding: 6px 10px 8px; border-bottom: 1px solid var(--baseline); cursor: pointer; white-space: nowrap; }
.an-root table.ledger th.sorted { color: var(--accent); }
.an-root table.ledger td { padding: 7px 10px; border-bottom: 1px solid var(--grid); vertical-align: middle; }
.an-root table.ledger td.num { font-variant-numeric: tabular-nums; text-align: right; }
.an-root table.ledger .headline { font-weight: 500; max-width: 420px; color: var(--ink); }
.an-root table.ledger .why { color: var(--ink-2); font-size: 12px; }
.an-root table.ledger tr:hover td { background: var(--nv-wash-07); }
.an-root .sec-chip { display: inline-flex; align-items: center; gap: 5px; font: 11px var(--nv-mono); color: var(--ink-2); white-space: nowrap; }
.an-root .sec-chip .sw { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }
.an-root .arch-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 12px; }
.an-root .arch-cell { background: var(--surface); border: 1px solid var(--ring); border-radius: 10px; padding: 12px 14px 8px; }
.an-root .arch-name { font-size: 13px; font-weight: 500; }
.an-root .arch-meta { font: 11px var(--nv-mono); color: var(--muted); margin-bottom: 4px; }
.an-root .discord-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin-top: 12px; }
.an-root .discord-cell { background: var(--surface); border: 1px solid var(--ring); border-radius: 10px; padding: 10px 12px 6px; }
.an-root .discord-title { font-size: 15px; font-weight: 500; margin: 16px 0 2px; }
@media (max-width: 700px) { .an-root .ledger-wrap { max-height: none; } }
```

- [ ] **Step 11: Run all vitest suites**

Run: `npx vitest run --dir tests/unit && npx vitest run --dir tests/integration`
Expected: PASS. The five shell tests pass with placeholder panels.

- [ ] **Step 12: Commit (fixtures force-added)**

```bash
git add -f data/fixtures/analysis/index.json data/fixtures/analysis/entries/five-years/payload.json
git add scripts/make_analysis_fixture.py src/redesign/analysis/ src/redesign/state.js src/redesign/render.js tests/unit/analysisLoader.test.js tests/integration/analysis.test.js
git commit -m "feat: analysis view — loader, entries row, entry header, panel pills, fixture

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Porting rules for Tasks 5 to 8

The renderers move from `/Users/gastonlhuillier/Personal/newvelles/analysis/site/template.html` (script at lines 403 to 913; markup per panel at lines 138 to 221; Learnings markup at lines 222 to 262) into one module per panel. Apply exactly these rules, nothing else:

| Rule | Old | New |
|---|---|---|
| R1 | `d3.xxx(` | unchanged; each module starts with `import * as d3 from 'd3';` |
| R2 | `document.getElementById("x")` | `$("x")` where `$` comes from `ctx` and resolves inside the analysis root |
| R3 | `d3.select("#x")`, `svgIn("#x", w, h)` | `d3.select($("x"))`, `svgIn($("x"), w, h)` |
| R4 | `document.querySelectorAll("#x sel")` | `$("x").querySelectorAll("sel")` |
| R5 | module-level `let` state above a renderer (`window0`, `drillTo`, `drillMode`, `pinnedCluster`, `tsSelected`, `tsMode`, `tsSort`, `sortKey`, `sortDir`) | declared inside `mount()` before the inner functions, so each mount starts fresh |
| R6 | shared names `D, P, fmtD, fmtMo, SECTIONS, SCOLOR, daily, weekly, EVENTS, T0, T1, tip, showTip, hideTip, showTipAt, svgIn` | destructured from `ctx` at the top of `mount()` |
| R7 | CSS `var(--surface)`, `var(--muted)`, `var(--ink)`, `var(--s1)`… | unchanged; `.an-root` defines those names |
| R8 | element ids in markup and code | unchanged (only one analysis root exists per page) |

Every panel module has this shape:

```js
import * as d3 from 'd3';

export const html = `…inner markup of <section id="panel-NAME"> from template.html…`;

export function mount(section, ctx) {
  const { D, $, P, fmtD /* only what this panel uses */ } = ctx;
  section.innerHTML = html;
  // R5 state here
  // renderer(s) pasted here with R2–R4 applied
  renderNAME();
}
```

and is registered in `panels/index.js` by adding `import * as NAME from './NAME.js'; registerPanel('NAME', NAME);` at the bottom of that file.

---

### Task 5: Context and the table panels: ledger, stats, categories (newvelles_web)

**Files:**
- Create: `src/redesign/analysis/context.js` (replace stub)
- Create: `src/redesign/analysis/panels/ledger.js`, `stats.js`, `categories.js`
- Modify: `src/redesign/analysis/panels/index.js` (register)
- Test: `tests/integration/analysis.test.js` (append)

**Interfaces:**
- Produces: `buildContext(payload, root)` → `{ D, root, $, P, fmtD, fmtMo, SECTIONS, SCOLOR, daily, weekly, EVENTS, T0, T1, tip, showTip, hideTip, showTipAt, svgIn }`.

- [ ] **Step 1: Failing tests**

Append to `tests/integration/analysis.test.js`:

```js
describe('table panels', () => {
  const open = async (name) => {
    await until(() => expect(q(`.an-pills [data-panel="${name}"]`)).not.toBeNull());
    q(`.an-pills [data-panel="${name}"]`).click();
    await until(() => expect(q(`[data-panel-section="${name}"]`).hidden).toBe(false));
  };

  it('ledger renders one row per ledger entry, sorted by peak outlets desc, with sparklines', async () => {
    await open('ledger');
    const rows = container.querySelectorAll('[data-panel-section="ledger"] table.ledger tbody tr');
    expect(rows.length).toBe(payload.ledger.length);
    const peaks = [...rows].map((r) => Number(r.children[3].textContent));
    expect(peaks).toEqual([...peaks].sort((a, b) => b - a));
    expect(container.querySelectorAll('[data-panel-section="ledger"] tbody svg path').length).toBe(payload.ledger.length);
  });

  it('ledger header click re-sorts', async () => {
    await open('ledger');
    const th = [...container.querySelectorAll('[data-panel-section="ledger"] th')].find((h) => h.textContent === 'Days seen');
    th.click();
    const days = [...container.querySelectorAll('[data-panel-section="ledger"] tbody tr')].map((r) => Number(r.children[4].textContent));
    expect(days).toEqual([...days].sort((a, b) => b - a));
  });

  it('stats renders the grains table and top sources', async () => {
    await open('stats');
    expect(q('[data-panel-section="stats"] #stats-core table')).not.toBeNull();
    expect(container.querySelectorAll('[data-panel-section="stats"] #stats-sources tbody tr').length).toBe(payload.stats.top_sources.length);
    expect(q('[data-panel-section="stats"] #stats-src-title').textContent).toContain(String(payload.stats.n_sources));
  });

  it('categories renders one row per sub-category', async () => {
    await open('categories');
    expect(container.querySelectorAll('[data-panel-section="categories"] #cat-table tbody tr').length).toBe(payload.categories.subs.length);
    expect(q('[data-panel-section="categories"] #cat-note').textContent).toContain(payload.categories.labeled.toLocaleString());
  });
});
```

Run: `npx vitest run tests/integration/analysis.test.js -t "table panels"` → FAIL (placeholders).

- [ ] **Step 2: Context**

Replace `src/redesign/analysis/context.js`:

```js
/**
 * Shared helpers the dashboard renderers used from the top of the old
 * single-file script (template.html lines 405–430), built once per mount.
 * `$` resolves ids inside the analysis root only.
 */
import * as d3 from 'd3';

export function buildContext(payload, root) {
  const D = payload;
  const $ = (id) => root.querySelector('#' + id);
  const P = (d) => d3.timeParse('%Y-%m-%d')(d);
  const fmtD = d3.timeFormat('%b %d, %Y');
  const fmtMo = d3.timeFormat('%b %Y');
  const SECTIONS = D.sections;
  const SCOLOR = Object.fromEntries(SECTIONS.map((s, i) => [s, `var(--s${(i % 8) + 1})`]));
  const daily = D.daily.map((r) => ({ d: P(r.d), a: r.a, s: r.s, x: r.x ?? 1 }));
  const weekly = D.weekly.map((r) => ({ ...r, d: P(r.d) }));
  const EVENTS = (D.events || []).map((e) => ({ ...e, dd: P(e.d) }));
  const T0 = daily[0].d;
  const T1 = daily[daily.length - 1].d;

  const tip = $('tooltip');
  function showTip(html, ev) {
    tip.innerHTML = html;
    tip.style.display = 'block';
    const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
    let x = ev.clientX + pad, y = ev.clientY + pad;
    if (x + w > innerWidth - 8) x = ev.clientX - w - pad;
    if (y + h > innerHeight - 8) y = ev.clientY - h - pad;
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  }
  const hideTip = () => (tip.style.display = 'none');
  function showTipAt(html, cx, cy) {
    tip.innerHTML = html;
    tip.style.display = 'block';
    let x = cx - tip.offsetWidth / 2, y = cy;
    x = Math.max(8, Math.min(x, innerWidth - tip.offsetWidth - 8));
    if (y + tip.offsetHeight > innerHeight - 8) y = cy - tip.offsetHeight - 32;
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  }
  const svgIn = (el, w, h) => d3.select(el).append('svg').attr('viewBox', `0 0 ${w} ${h}`);

  return { D, root, $, P, fmtD, fmtMo, SECTIONS, SCOLOR, daily, weekly, EVENTS, T0, T1, tip, showTip, hideTip, showTipAt, svgIn };
}
```

- [ ] **Step 3: Ledger module (full text, the exemplar for the others)**

Create `src/redesign/analysis/panels/ledger.js`:

```js
import * as d3 from 'd3';

export const html = `
  <p class="panel-note">Every story that ran on 3+ distinct days or peaked at 8+ outlets, with the shape of its coverage. Click a column to sort.</p>
  <div class="chart-box ledger-wrap"><div id="ledger"></div></div>`;

export function mount(section, ctx) {
  const { D, $, P, fmtD, SCOLOR } = ctx;
  section.innerHTML = html;
  let sortKey = 'peak_outlets', sortDir = -1;

  function renderLedger() {
    const cols = [
      ['headline', 'Story'], ['section', 'Section'], ['peak_day', 'Broke'],
      ['peak_outlets', 'Peak outlets'], ['days', 'Days seen'], ['span', 'Span'],
      ['curve', 'Coverage curve'], ['why', 'Why flagged']];
    const wrap = d3.select($('ledger'));
    wrap.selectAll('*').remove();
    const table = wrap.append('table').attr('class', 'ledger');
    table.append('thead').append('tr').selectAll('th').data(cols).join('th')
      .classed('sorted', ([k]) => k === sortKey)
      .text(([, label]) => label)
      .on('click', (ev, [k]) => {
        if (k === 'curve') return;
        sortDir = k === sortKey ? -sortDir : (k === 'headline' || k === 'section' ? 1 : -1);
        sortKey = k; renderLedger();
      });
    const rows = [...D.ledger].sort((p, q) =>
      (p[sortKey] < q[sortKey] ? -1 : p[sortKey] > q[sortKey] ? 1 : 0) * sortDir);
    const tr = table.append('tbody').selectAll('tr').data(rows).join('tr');
    tr.append('td').attr('class', 'headline').text((r) => r.headline);
    tr.append('td').html((r) =>
      `<span class="sec-chip"><span class="sw" style="background:${SCOLOR[r.section] || 'var(--muted)'}"></span>${r.section}</span>` +
      (r.cat ? `<div class="why" style="margin-top:2px">${r.cat}</div>` : ''));
    tr.append('td').text((r) => fmtD(P(r.peak_day)));
    tr.append('td').attr('class', 'num').text((r) => r.peak_outlets);
    tr.append('td').attr('class', 'num').text((r) => r.days);
    tr.append('td').attr('class', 'num').text((r) => r.span + 'd');
    tr.append('td').each(function (r) {
      const s = d3.select(this).append('svg').attr('viewBox', '0 0 120 24').style('width', '120px');
      const sx = d3.scaleLinear().domain([0, r.curve.length - 1]).range([2, 118]);
      const sy = d3.scaleLinear().domain([0, d3.max(r.curve)]).range([21, 3]);
      s.append('path').datum(r.curve)
        .attr('d', d3.line().x((v, i) => sx(i)).y((v) => sy(v)).curve(d3.curveMonotoneX))
        .style('fill', 'none').style('stroke', 'var(--s1)').style('stroke-width', 1.5);
    });
    tr.append('td').attr('class', 'why').text((r) => r.why);
  }

  renderLedger();
}
```

The `panel-note` text: copy the real sentence from `template.html` inside `<section id="panel-ledger">` (lines 168–170) instead of the one above if it differs.

- [ ] **Step 4: Stats and categories modules**

`stats.js`: `html` = inner markup of `<section id="panel-stats">` (template lines 210–221: two `chart-box` blocks with `#stats-core`, `#stats-src-title`, `#stats-sources`). `mount` destructures `{ D, $ }`, pastes `renderStats` (template lines 871–909) with R2 applied to the three `getElementById` calls, then calls `renderStats()`.

`categories.js`: `html` = inner markup of `<section id="panel-categories">` (template lines 205–208: `#cat-note`, `#cat-table`). `mount` destructures `{ D, $ }`, pastes `renderCategories` (template lines 839–869) with R2 applied, then calls `renderCategories()`. Keep the `${'Fable'}` interpolation as the literal word `Fable`.

Register all three at the bottom of `panels/index.js`:

```js
import * as ledger from './ledger.js';
import * as stats from './stats.js';
import * as categories from './categories.js';
registerPanel('ledger', ledger);
registerPanel('stats', stats);
registerPanel('categories', categories);
```

(Put the imports at the top of the file; `registerPanel` calls at the bottom.)

- [ ] **Step 5: Run tests**

Run: `npx vitest run tests/integration/analysis.test.js`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/redesign/analysis/ tests/integration/analysis.test.js
git commit -m "feat: analysis panels — ledger, stats, categories ported onto Nocturne

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Timeline panel (newvelles_web)

**Files:**
- Create: `src/redesign/analysis/panels/timeline.js`
- Modify: `src/redesign/analysis/panels/index.js` (register)
- Test: `tests/integration/analysis.test.js` (append)

- [ ] **Step 1: Failing test**

Append:

```js
describe('timeline panel', () => {
  it('renders the strip with one marker per event and the stream with one band per section', async () => {
    await until(() => expect(q('[data-panel-section="timeline"] #strip svg')).not.toBeNull());
    const strip = q('[data-panel-section="timeline"] #strip svg');
    expect(strip.querySelectorAll('circle').length).toBe(payload.events.length);
    const stream = q('[data-panel-section="timeline"] #stream svg');
    expect(stream).not.toBeNull();
    expect(stream.querySelectorAll('g > path').length).toBeGreaterThanOrEqual(payload.sections.length);
    expect(container.querySelectorAll('[data-panel-section="timeline"] #stream-legend .li').length).toBe(payload.sections.length);
    expect(q('[data-panel-section="timeline"] #stream-back').hidden).toBe(true);
  });

  it('clicking a band drills into that major and back returns', async () => {
    await until(() => expect(q('[data-panel-section="timeline"] #stream svg')).not.toBeNull());
    const major = Object.keys(payload.drill)[0];
    const idx = payload.sections.indexOf(major);
    const band = q('[data-panel-section="timeline"] #stream svg').querySelectorAll('g > path')[idx];
    band.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await until(() => expect(q('[data-panel-section="timeline"] #drill-title').textContent).toBe(major));
    expect(q('[data-panel-section="timeline"] #stream-back').hidden).toBe(false);
    q('[data-panel-section="timeline"] #stream-back').click();
    await until(() => expect(q('[data-panel-section="timeline"] #stream-back').hidden).toBe(true));
  });
});
```

Run: `npx vitest run tests/integration/analysis.test.js -t "timeline panel"` → FAIL.

- [ ] **Step 2: Timeline module**

Create `src/redesign/analysis/panels/timeline.js`:

- `html` = inner markup of `<section id="panel-timeline">` (template lines 138–166; contains `#strip`, `#drill-title`, `#stream-title`, `#stream-legend`, `#drill-mode`, `#stream-back`, `#stream`).
- `mount(section, ctx)` destructures `{ D, $, P, fmtD, fmtMo, SECTIONS, SCOLOR, daily, weekly, EVENTS, T0, T1, showTip, hideTip, showTipAt, svgIn }`, sets `section.innerHTML = html`, then declares (R5):

```js
  const TL = { W: 1180, HS: 96, HD: 380, ML: 8, MR: 8 };
  let window0 = [d3.timeMonth.offset(T1, -18), T1];
  let drillTo = null;
  let drillMode = 'top';
  let pinnedCluster = null;
```

then pastes, in order, `markerDate`, `drawMarker`, `drawClusterLane`, `renderTimeline`, `renderStream` (template lines 456–587) with these exact substitutions:

| Line content | Change |
|---|---|
| `svgIn("#strip", TL.W, TL.HS + 30)` | `svgIn($('strip'), TL.W, TL.HS + 30)` |
| `document.getElementById("stream-back").onclick` | `$('stream-back').onclick` |
| `d3.select("#stream").selectAll("*").remove()` | `d3.select($('stream')).selectAll('*').remove()` |
| `document.getElementById("stream-back").hidden` | `$('stream-back').hidden` |
| `const dt = document.getElementById("drill-title")` | `const dt = $('drill-title')` |
| `const dm = document.getElementById("drill-mode")` | `const dm = $('drill-mode')` |
| `d3.select("#stream-legend")` | `d3.select($('stream-legend'))` |
| `document.getElementById("stream-title")` | `$('stream-title')` |
| `svgIn("#stream", TL.W, TL.HD)` | `svgIn($('stream'), TL.W, TL.HD)` |

and ends with `renderTimeline();`. If the fixture window (`T1 - 18 months`) starts before `T0`, the brush still works: `d3.brushX` clamps to the extent.

Register: `import * as timeline from './timeline.js'; registerPanel('timeline', timeline);`.

- [ ] **Step 3: Run tests, then commit**

Run: `npx vitest run tests/integration/analysis.test.js`
Expected: PASS. If jsdom throws inside `d3.brush` on mount (it uses `getBoundingClientRect`, which jsdom stubs to zeros, and `pointer` events only on interaction), record the exact error in the commit body and wrap only the `svg.append("g").call(brush).call(brush.move, …)` line in `try { … } catch (e) { console.error('brush unavailable', e); }`. Do not skip the test.

```bash
git add src/redesign/analysis/panels/timeline.js src/redesign/analysis/panels/index.js tests/integration/analysis.test.js
git commit -m "feat: analysis timeline panel — era strip, brush, streamgraph, drill-down, event markers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Top stories, lifetimes, archetypes (newvelles_web)

**Files:**
- Create: `src/redesign/analysis/panels/topstories.js`, `lifetimes.js`, `archetypes.js`
- Modify: `src/redesign/analysis/panels/index.js`
- Test: `tests/integration/analysis.test.js` (append)

- [ ] **Step 1: Failing tests**

Append:

```js
describe('top stories, lifetimes, archetypes', () => {
  const open = async (name) => {
    await until(() => expect(q(`.an-pills [data-panel="${name}"]`)).not.toBeNull());
    q(`.an-pills [data-panel="${name}"]`).click();
    await until(() => expect(q(`[data-panel-section="${name}"]`).hidden).toBe(false));
  };

  it('top stories starts on landmark events with one row per event and a chip per drill major', async () => {
    await open('topstories');
    expect(container.querySelectorAll('[data-panel-section="topstories"] #ts-table tbody tr').length).toBe(payload.events.length);
    expect(container.querySelectorAll('[data-panel-section="topstories"] #ts-chips button').length).toBe(1 + Object.keys(payload.drill).length);
    expect(q('[data-panel-section="topstories"] #ts-mode').hidden).toBe(true);
  });

  it('top stories chip switches to a major and shows the mode buttons', async () => {
    await open('topstories');
    const major = Object.keys(payload.drill)[0];
    [...container.querySelectorAll('[data-panel-section="topstories"] #ts-chips button')].find((b) => b.textContent === major).click();
    await until(() => expect(q('[data-panel-section="topstories"] #ts-mode').hidden).toBe(false));
    expect(container.querySelectorAll('[data-panel-section="topstories"] #ts-table tbody tr').length).toBe(payload.drill[major].top.length);
  });

  it('lifetimes draws base and named circles plus labels', async () => {
    await open('lifetimes');
    const svg = q('[data-panel-section="lifetimes"] #lifetimes svg');
    expect(svg.querySelectorAll('circle').length).toBe(payload.lifetimes.base.length + payload.lifetimes.named.length);
    expect(q('[data-panel-section="lifetimes"] #lifetimes-title').textContent).toContain(payload.lifetimes.total.toLocaleString());
  });

  it('archetypes draws one cell per cluster and one per discord', async () => {
    await open('archetypes');
    expect(container.querySelectorAll('[data-panel-section="archetypes"] .arch-cell').length).toBe(payload.archetypes.clusters.length);
    expect(container.querySelectorAll('[data-panel-section="archetypes"] .discord-cell').length).toBe(payload.discords.length);
    expect(q('[data-panel-section="archetypes"] #arch-note').textContent).toContain(String(payload.archetypes.clusters.length));
  });
});
```

Run → FAIL.

- [ ] **Step 2: Modules**

`topstories.js`: `html` = inner markup of `<section id="panel-topstories">` (template lines 193–203: `#ts-chips`, `#ts-mode`, `#ts-table`). `mount` destructures `{ D, $, P, fmtD, EVENTS }`; R5 state `let tsSelected = '__landmark__'; let tsMode = 'top'; let tsSort = { key: 'n', dir: 1 };` plus `const TS_COLS = […]` and `const withCluster = …` (template lines 658–662), then `renderTopStories` (lines 663–711) with: `d3.select("#ts-chips")` → `d3.select($('ts-chips'))`, `document.getElementById("ts-mode").hidden` → `$('ts-mode').hidden`, `d3.select("#ts-mode")` → `d3.select($('ts-mode'))`, `document.getElementById("ts-table").innerHTML` → `$('ts-table').innerHTML`, `document.querySelectorAll("#ts-table th")` → `$('ts-table').querySelectorAll('th')`. Ends `renderTopStories();`.

`lifetimes.js`: `html` = inner markup of `<section id="panel-lifetimes">` (lines 175–182: `#lifetimes-title`, `#lifetimes`). `mount` destructures `{ D, $, P, fmtD, T0, T1, showTip, hideTip, svgIn }`; paste `renderLifetimes` (lines 755–795) with `document.getElementById("lifetimes-title")` → `$('lifetimes-title')` and `svgIn("#lifetimes", W, H)` → `svgIn($('lifetimes'), W, H)`. Ends `renderLifetimes();`.

`archetypes.js`: `html` = inner markup of `<section id="panel-archetypes">` (lines 185–191: `#arch-note`, `#arch-grid`, the discord title, `#discords`). `mount` destructures `{ D, $, P, fmtD }`; paste `renderArchetypes` (lines 797–837) with `document.getElementById("arch-note")` → `$('arch-note')`, `d3.select("#arch-grid")` → `d3.select($('arch-grid'))`, `d3.select("#discords")` → `d3.select($('discords'))`. Ends `renderArchetypes();`.

Register all three in `panels/index.js`.

- [ ] **Step 3: Run tests, commit**

Run: `npx vitest run tests/integration/analysis.test.js` → PASS.

```bash
git add src/redesign/analysis/panels/ tests/integration/analysis.test.js
git commit -m "feat: analysis panels — top stories, lifetimes, archetypes

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Learnings panel, e2e, status note, local run (newvelles_web)

**Files:**
- Create: `src/redesign/analysis/panels/learnings.html`, `learnings.js`
- Modify: `src/redesign/analysis/panels/index.js`
- Create: `tests/e2e/analysis.spec.js`
- Modify: `docs/REDESIGN_STATUS.md`
- Test: `tests/integration/analysis.test.js` (append)

- [ ] **Step 1: Failing test**

Append:

```js
describe('learnings panel', () => {
  it('renders the static learnings content with its three tables', async () => {
    await until(() => expect(q('.an-pills [data-panel="learnings"]')).not.toBeNull());
    q('.an-pills [data-panel="learnings"]').click();
    await until(() => expect(q('[data-panel-section="learnings"]').hidden).toBe(false));
    expect(container.querySelectorAll('[data-panel-section="learnings"] table.ledger').length).toBe(3);
    expect(q('[data-panel-section="learnings"]').textContent).toContain('golden set');
  });
});
```

- [ ] **Step 2: Learnings module**

Copy template.html lines 223 to 261 (everything inside `<section class="panel" id="panel-learnings" hidden>` up to but not including its closing `</section>`) verbatim into `src/redesign/analysis/panels/learnings.html`. Verify with `grep -c '<table class="ledger">' src/redesign/analysis/panels/learnings.html` → `3`.

Create `learnings.js`:

```js
import html from './learnings.html?raw';

export function mount(section) {
  section.innerHTML = html;
}
```

Register in `panels/index.js`. Run: `npx vitest run tests/integration/analysis.test.js` → PASS (Vite's `?raw` import works under vitest).

- [ ] **Step 3: e2e**

Create `tests/e2e/analysis.spec.js`:

```js
import { test, expect } from '@playwright/test';

test.describe('Analysis tab', () => {
  test('is reachable from the header and shows the first entry with panels', async ({ page }) => {
    await page.goto('/');
    const tab = page.locator('.nv-tabs [data-go-analysis]');
    await expect(tab).toBeVisible();
    await tab.click();
    await expect(tab).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('.an-entry-head h2')).toBeVisible();
    await expect(page.locator('#strip svg')).toBeVisible();
    await page.locator('.an-pills [data-panel="ledger"]').click();
    await expect(page.locator('#ledger table.ledger')).toBeVisible();
    await page.locator('.nv-tabs [data-go-board]').click();
    await expect(page.locator('.nv-lead')).toBeVisible();
  });
});
```

Run: `npx playwright test tests/e2e/analysis.spec.js` (the config starts `npm run dev`, fixture mode). Expected: PASS. If browsers are missing: `npx playwright install chromium` once.

- [ ] **Step 4: Full suite and build**

Run: `npm test` and `npm run build`. Expected: all green, `dist/` builds. Note the redesign bundle size printed by Vite in the commit body (d3 adds roughly 100 to 150 KB minified; that is expected).

- [ ] **Step 5: Status note**

Append to `docs/REDESIGN_STATUS.md`:

```markdown
## Analysis tab (2026-09-19, not deployed)

Header tab strip: Today / Wire / Analysis. The Analysis view lists entries from
`/analysis/index.json` and loads one payload per entry on demand
(`/analysis/entries/<id>/payload.json`), both proxied from the public bucket by
`newvelles_web/analysis.py`. Panels are the archive dashboard ported from
`newvelles/analysis/site/template.html` onto Nocturne (`src/redesign/analysis/`).
Design: `newvelles/docs/superpowers/specs/2026-09-19-analysis-tab-design.md`.

Local review with real data:

```
mkdir -p data/local/analysis/entries/five-years
cp ../newvelles/analysis/entries/index.json data/local/analysis/
cp ../newvelles/analysis/entries/five-years/payload.json data/local/analysis/entries/five-years/
VITE_NV_DATA_SOURCE=local npm run dev   # http://localhost:5173 → Analysis
```

Nothing is published to S3 and nothing is deployed until the panels are reviewed.
```

- [ ] **Step 6: Commit**

```bash
git add src/redesign/analysis/panels/ tests/integration/analysis.test.js tests/e2e/analysis.spec.js docs/REDESIGN_STATUS.md
git commit -m "feat: analysis learnings panel, e2e smoke, status note

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [ ] **Step 7: Local run for the user**

```bash
cd /Users/gastonlhuillier/Personal/newvelles_web && VITE_NV_DATA_SOURCE=local npm run dev
```

Open `http://localhost:5173/`, click Analysis. All eight panels render from the real payload. Leave the server running and hand the URL to the user for review. Do not push either branch.
