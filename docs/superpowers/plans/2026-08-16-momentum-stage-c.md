# Momentum (Stage C / M4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give stories identity across runs and days, emit a public `momentum.json` (rolling 14-day series per live story), keep a private `momentum_state.json`, and seed both from the archive so sparklines aren't empty at launch.

**Architecture:** A pure `apply_momentum(stories_data, state, today)` in `newvelles/models/momentum.py` rewrites story ids by carrying identity from the previous state (Jaccard over keywords∪entities ≥ 0.4 against stories last seen today/yesterday), maintains per-story day series (per-day datapoint = max over that day's runs), derives `peak_date`/`trend`, and returns `(stories', momentum_doc, state')`. State I/O lives beside it (S3 private bucket / local `./cache/`); uploads ride the existing `emit_visualization()` behind the same sanity gate as `stories.json`. A backfill script replays archived runs chronologically to seed QA and production.

**Tech Stack:** Python 3.12, pytest, existing `read_json_from_s3`/`upload_to_s3`, no new dependencies.

## Global Constraints

- Contract: `test/fixtures/momentum_v0.3.0.json` — same field names/shape. `days_running == len(series)`.
- `WINDOW_DAYS = 14`, `CARRY_THRESHOLD = 0.4` (spec: "start at 0.4"), `MOMENTUM_VERSION = "0.3.0"`.
- Trend vocabulary is a UI contract: production emits only `new | climbing | peaked | cooling | steady`. Schema additionally tolerates the fixture-only `single day`.
- Day datapoint rule: a day records its peak — `outlets = max(existing, run)`, `articles = max(existing, run)`; **only the current day is ever mutated**; earlier days are immutable once passed. Dates are UTC.
- Identity: match only against state stories with `last_seen` ≥ yesterday; a match inherits the previous `id`; no match mints a new id. Matching is one-to-one, best-score-first.
- Public `momentum.json` contains **only ids present in the current `stories.json`** (front end joins on id); the private state keeps the full window.
- Momentum uploads and state save are gated by the same pre-publish sanity gate as `stories.json` — a blocked run must not pollute state.
- `latest_news.json` byte-identical guarantee continues to hold.
- Branch `redesign/momentum`, one commit per task.

## File Structure

- `newvelles/models/momentum.py` — new: pure core + state I/O helpers.
- `newvelles/feed/log.py` — modified: emit momentum doc (public) + state (private) inside the gated branch; local writer variants.
- `handler.py`, `newvelles/__main__.py` — modified: load state → `apply_momentum` → pass artifacts to emit.
- `schemas/momentum_schema.json` — new.
- `scripts/backfill_momentum.py`, `Makefile` (`backfill-momentum`) — new.
- Tests: `test/test_models_momentum.py`, `test/test_momentum_schema.py`, additions to `test/test_feed_log.py`.

---

### Task 1: Pure momentum core (`apply_momentum`, trend, matching)

**Files:** Create `newvelles/models/momentum.py`; Test `test/test_models_momentum.py`

**Interfaces — Produces:**
- `apply_momentum(stories_data: dict, state: Optional[dict], today: str) -> tuple[dict, dict, dict]` — returns `(stories_data_with_carried_ids, momentum_doc, new_state)`. Mutates story `id`, `days_running`, `first_seen` from carried identity.
- `derive_trend(series: list, peak_date: str) -> str`
- State shape: `{"version", "updated", "stories": {id: {"keywords": [], "entities": [], "first_seen", "last_seen", "series": [{"date","outlets","articles"}]}}}`
- Momentum doc shape: `{"version", "generated", "window_days", "window_start", "window_end", "stories": {id: {"first_seen","days_running","series","peak_date","trend"}}}`

Key test cases (write first, run red, implement, run green, commit):
- Two consecutive days: story persists (id carried, `days_running` 2, series 2 entries), another dies (absent from doc; retained in state), a new one appears (fresh id, trend `new`).
- Same-day second run: series stays 1 entry with `outlets/articles = max` of the two runs; id stable.
- Story seen Mon, absent Tue, returns Wed → new id (matching window is yesterday only).
- One-to-one matching: two current stories both similar to one previous story → only the better match carries the id.
- Window: simulate 16 days → series never exceeds 14 entries; state prunes stories with `last_seen` older than the window.
- Trend: single entry → `new`; rising last day ≥ mean → `climbing`; drop right after the peak (peak == yesterday) → `peaked`; below-mean decline → `cooling`; flat → `steady`. `peak_date` = earliest date with max outlets.
- Doc contains only current story ids; `window_start = today − 13d`, `window_end = today`.
- `state=None` behaves as first run.

Trend rule (implement exactly):
```python
def derive_trend(series, peak_date):
    if len(series) == 1:
        return "new"
    last, prev = series[-1]["outlets"], series[-2]["outlets"]
    window_mean = sum(p["outlets"] for p in series) / len(series)
    if last > prev and last >= window_mean:
        return "climbing"
    if peak_date == series[-2]["date"] and last < prev:
        return "peaked"
    if last < prev and last < window_mean:
        return "cooling"
    return "steady"
```

Signature for matching: `set(story["keywords"]) | {e.lower() for e in story["entities"]}`; Jaccard `|A∩B| / |A∪B|`; candidates from state where `last_seen >= today - 1 day`; pairs sorted by score desc, each previous id assigned at most once, threshold `>= CARRY_THRESHOLD`.

### Task 2: Momentum schema + fixture validation

**Files:** Create `schemas/momentum_schema.json`; Test `test/test_momentum_schema.py`

- Draft-07, style of the existing schemas. Required top-level: `version` (`^0\.3\.\d+$`), `generated`, `window_days`, `stories`; optional `window_start`, `window_end`, `approximation*` (fixture provenance). Story: required `first_seen`, `days_running` (min 1), `series` (minItems 1, items require `date`/`outlets`/`articles`), `peak_date`, `trend` (enum: new, climbing, peaked, cooling, steady, `single day`).
- Tests: fixture validates; a generated doc (from Task 1's synthetic two-day scenario) validates; missing `trend` rejected; bad trend value rejected.

### Task 3: State I/O + emit wiring + handler/CLI

**Files:** Modify `newvelles/models/momentum.py` (I/O helpers), `newvelles/feed/log.py`, `handler.py`, `newvelles/__main__.py`; Test additions to `test/test_feed_log.py`

- `momentum.py` I/O: `load_state_s3()` (private bucket via `read_json_from_s3`), `load_state_local(path="./cache/momentum_state.json")`. Saving happens through the emit path so it shares the gate.
- `log.py`: constants `_LOG_MOMENTUM_NAME = "momentum"`, `_MOMENTUM_STATE_NAME = "momentum_state"`. `emit_visualization(..., momentum_doc=None, momentum_state=None)`; inside the gate-passing branch of `_emit_stories` (rename to `_emit_stories_and_momentum`): after `stories.json`, upload `momentum.json` (public, `public_read=True`) and `momentum_state.json` (**private** bucket). Local writer: `./momentum.json`, `{_LATEST_PATH}/momentum.json`, and state to `./cache/momentum_state.json` (mkdir). Gate blocked → none of stories/momentum/state written to S3 (locals still written).
- `log_s3(visualization_data, stories_data=None, momentum_doc=None, momentum_state=None)` passthrough.
- `handler.py`: `state = load_state_s3()`; `stories_data, momentum_doc, new_state = apply_momentum(stories_data, state, today=utc_today())`; pass all three to `log_s3`; print carried-id count (monitoring: "stories with carried ids" catches identity churn).
- `__main__.py`: same with `load_state_local()`.
- Tests: upload order/buckets (4th = stories.json public, 5th = momentum.json public, 6th = momentum_state.json private); blocked gate → 3 uploads only; local writer writes momentum + state files; `log_s3` delegation.

### Task 4: Backfill script + seed QA (and production)

**Files:** Create `scripts/backfill_momentum.py`; Modify `Makefile` (`backfill-momentum` target)

- Script: list private bucket archives (`newvelles_visualization_0.2.1_*`), keep runs whose UTC date is within the last `WINDOW_DAYS`, dedupe near-duplicates, process chronologically: download → `build_stories(viz)` → `apply_momentum(..., today=run_date)` threading the state. Then upload `momentum_state.json` (private) + `momentum.json` (public) — `--dry-run` writes to local files instead. `--env qa|prod` selects bucket pairs (qa: `newvelles-qa-bucket`/`public-newvelles-qa-bucket`).
- Makefile: `backfill-momentum: python scripts/backfill_momentum.py --env $(ENV)`.
- Execute: dry-run on prod archives first (inspect output sanity: carried ids exist, series lengths > 1 for persistent stories), then seed **QA** buckets (M4's done-when), then seed **production** buckets (producer-before-consumer: file sits unused until M5).

### Task 5: Docs, suite, PR

- `CLAUDE.md`: momentum stage bullet in Core Data Flow; `momentum.json`/`momentum_state.json` in S3 upload list; key files.
- Full suite + lint; push `redesign/momentum`; PR.

## Self-Review notes
- Spec coverage: identity match (§4 match_previous, threshold 0.4) ✓; rollup shape ✓; max-per-day rule + current-day-only mutation ✓; trend derived not stored ✓ vocabulary contract ✓; backfill seeding ✓ (M4 done-when includes the seeded window); gate interaction defined (not in spec — decision recorded: anomalous runs must not pollute identity state).
- Deviation from spec noted for review: public momentum.json filtered to current stories (keeps the file small and matches the fixture, which carries exactly the 41 current stories).
