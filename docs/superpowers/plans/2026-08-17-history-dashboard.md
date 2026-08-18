# Historical dashboard (backfill → payload → tabbed site) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One single-screen tabbed page over the real 2021–2026 archive — Timeline (A+B: zoomable overview strip driving a streamgraph with share toggle, annotated), Ledger (G), Lifetimes (E), Archetypes (H: shape clusters + matrix-profile discords) — kept in `analysis/`, exportable as one HTML file to glhuilli.github.io.

**Architecture:** Three stages. (1) `scripts/backfill_history.py` replays the mirrored archive through `build_stories()` (parallel, per-run cache = resumable) then a sequential identity pass reusing `momentum._signature`/`_jaccard` (Jaccard ≥ 0.4 vs stories seen today/yesterday; gaps reset by design) → `analysis/data/stories.parquet`, one row per (run, story). (2) `analysis/build_payload.py` (own venv) aggregates parquet → all chart payloads + archetype k-means + matrix-profile discords → injects JSON into (3) `analysis/site/template.html` → self-contained `analysis/site/index.html` with inlined D3.

**Tech Stack:** Stage 1: main venv + pyarrow (ad hoc install, NOT in requirements.txt). Stage 2: `analysis/.venv` with pandas, pyarrow, numpy, scikit-learn. Stage 3: D3 v7 inlined, tokens/CSS reused from `analysis/visualization_options.html`.

**Spec:** User directive 2026-08-17 (build G, A+B, E, H as one screen with tabs; keep in repo; export later) + `docs/NEXT_STEPS.md` workstream 3 step 2 (checkpointed replay, full unwindowed series, no LLM naming, identity resets across gaps, extend sources.json with retired historical feeds first).

## Global Constraints

- Nothing in `analysis/` or `scripts/backfill_history.py` touches `requirements.txt` or the Docker image.
- `analysis/data/`, `analysis/cache/`, `analysis/.venv` are gitignored; code, template, and the built `index.html` are committed.
- The built page is a single file: D3 inlined, data inlined, zero network requests; light + dark mode; palette = validated reference set (categorical slots 1–8, sequential ramp flipped in dark).
- Phase A must be resumable (per-run cache); a full re-run after a crash resumes where it stopped.
- Ledger counts only `kind == "story"`; sections capped at top 7 + Other everywhere.

---

### Task 1: sources.json historical coverage scan (prerequisite, cheap)

**Files:** Create `scripts/scan_archive_sources.py`; possibly modify `data/sources.json`.

Fast IO-only pass over `archive/**/*.json`: collect every article `source` feed URL, count occurrences, report URLs where `newvelles.utils.sources.is_mapped()` is false, grouped by registered domain with article counts. Steps: write script (arg: `--archive-dir`, prints top unmapped domains + sample URLs); run on available mirror; add entries to `data/sources.json` for every unmapped domain with ≥ 1000 articles (outlet = proper name, best-guess section, e.g. HuffPost/General, CNN/General, CBS locals/Local); re-run scan to confirm coverage ≥ ~99% of articles; run `pytest test/test_utils_sources.py`; commit.

### Task 2: `scripts/backfill_history.py`

**Files:** Create `scripts/backfill_history.py`; Test `test/test_backfill_history.py` (identity-pass unit tests only — no network, no archive).

**Interfaces:** CLI `python scripts/backfill_history.py --archive-dir archive --out analysis/data/stories.parquet --cache analysis/cache/runs --workers 10 [--since 2021-07] [--until ...]`. Parquet columns: `run_ts (str ISO), day (str YYYY-MM-DD), story_uid (str), headline, section, kind, outlet_count (int16), article_count (int16), keywords (json str), entities (json str)`.

Phase A (parallel, ProcessPoolExecutor): per run file → `build_stories(viz)` → write `cache/<ts>.json.gz` holding per-story dicts `{headline, section, kind, outlet_count, article_count, keywords, entities}`. Skip files whose cache entry exists (resume). Progress line every 200 runs.

Phase B (sequential, in-memory): iterate cached runs chronologically. Identity state = `{uid: {sig, last_day}}` for stories seen on the current or previous archive day (calendar-day comparison on `day`; a gap > 1 day empties the carry — the yesterday-only rule). Match = best Jaccard ≥ 0.4 using `momentum._signature` / `momentum._jaccard` on the story dict. New story → `uid = h_<sha1(day + headline)[:10]>`. Core:

```python
def carry_identity(runs_iter):
    prev: dict = {}   # uid -> {"sig": set, "day": str}
    for day, run_ts, stories in runs_iter:
        alive = {u: s for u, s in prev.items() if _day_delta(day, s["day"]) <= 1}
        for story in stories:
            sig = _signature(story)
            best_uid, best_score = None, 0.0
            for uid, st in alive.items():
                score = _jaccard(sig, st["sig"])
                if score > best_score:
                    best_uid, best_score = uid, score
            uid = best_uid if best_score >= 0.4 else _new_uid(day, story)
            story["story_uid"] = uid
            alive[uid] = {"sig": sig, "day": day}
            yield run_ts, day, story
        prev = alive
```

(Matching is per-run greedy like prod; O(stories × alive) ≈ 240 × 500 set-ops per run — fine.) Tests: same-signature story carries uid across consecutive days; below-threshold gets new uid; 2-day gap resets carry; per-run rows preserved. Then write parquet via pyarrow (`pip install pyarrow` into main venv, ad hoc).

### Task 3: analysis environment + `analysis/build_payload.py`

**Files:** Create `analysis/requirements.txt` (pandas, pyarrow, numpy, scikit-learn), `analysis/build_payload.py`, `analysis/.gitignore` (`.venv/`, `../analysis/data/`… use `analysis/.gitignore` with `data/`, `cache/`, `.venv/`).

Payload builder reads the parquet and emits one JSON object:

- `meta`: date range, run count, story count, generated stamp, data-version.
- `daily`: `[{d, articles, stories}]` — per day, max over runs of Σ article_count, and unique `story_uid` count.
- `weekly`: `[{d, <sec1..sec7>, Other}]` — unique stories per ISO-week × section (top 7 sections by total + Other).
- `ledger`: top 80 `kind=="story"` by peak outlet_count: `{uid, headline (from peak run), section, first, last, days_seen, peak_outlets, peak_articles, curve: [daily max outlets, ≤ 48 pts downsampled], why}` where `why` = "z > 4 spike" / "sustained multi-week run" / "single-day flash" from curve stats.
- `annotations`: from ledger — max 1 story per 45-day window, top ~15 overall, `{d: peak day, label: headline truncated 40 chars, uid}`.
- `lifetimes`: `{base: [...sampled ~3000 {d, span, peak}], named: top 12 by span·peak with headline}` — keep every story with span ≥ 7 or peak ≥ 10; sample the rest.
- `archetypes`: stories with ≥ 5 distinct days: resample each daily-outlets curve to 24 points, scale max = 1; k-means k=5 (n_init=10, seed 0); per cluster: size, medoid curve (member nearest centroid), 12 sampled member curves, auto-name from shape (peak position/count heuristics: flash / slow burn / double peak / late resurgence / plateau); plus `silhouette` score.
- `discords`: matrix profile over `daily.articles` (z-normalized windows, m=14, numpy O(n²), self-match exclusion ±m): top 5 non-overlapping discord windows `{start, end, score}` + the window's own curve.

Then `--build-site` mode: read `analysis/site/template.html`, replace `/*__DATA__*/` with the JSON and `/*__D3__*/` with the minified D3 source (path arg), write `analysis/site/index.html`. Smoke-test the whole chain first on the partial mirror (`--since 2026-08`), assert payload keys present.

### Task 4: `analysis/site/template.html` — the tabbed dashboard

**Files:** Create `analysis/site/template.html`.

One screen: masthead row (title, date-range, run/story counts in mono) + tab bar (`Timeline · Ledger · Lifetimes · Archetypes`) + one panel visible at a time (`hidden` attribute toggling; charts render lazily on first tab open; window resize re-renders active tab). Reuse gallery tokens/CSS (light + dark, serif display confined to the title, mono metadata). Footer: "synthetic-free: real archive data · generated <stamp>".

- **Timeline tab (A+B):** overview strip (daily articles, full range, brush) + detail streamgraph of `weekly` filtered to the brushed window, stream/share toggle, annotation flags from `annotations` drawn on the strip and (when in window) labeled in the detail; hover tooltips per band; legend chips.
- **Ledger tab (G):** the table with sparkline curves, sortable by clicking Peak outlets / Days / Broke headers (simple JS sort, re-render tbody); section chip colored by section slot.
- **Lifetimes tab (E):** scatter as in the gallery but from `lifetimes` payload; named outliers labeled; log y.
- **Archetypes tab (H):** cluster panels (thin members + heavy medoid, cluster name + size + share) in a grid, silhouette note, then the discord strip: 5 red mini-panels with date ranges, titled "days that resemble no other days".

All charts read `window.DATA`; no fetches. Keep every chart function ≤ ~60 lines by reusing shared helpers (`svgIn`, `showTip`, axis styles) copied from the gallery.

### Task 5: full run + verification + ship

- [ ] Wait for the mirror to finish (background task); spot-check file count ≈ 9,294 and year spread 2021–2026.
- [ ] Task 1 scan on the full mirror → extend sources.json → tests.
- [ ] Run phase A with `--workers 10` (background; expect ~30–90 min); then phase B; sanity: row count ~1.5–2.5M, unique stories 150k–300k, days ≈ 1,850.
- [ ] Run payload + build-site on full data; open `analysis/site/index.html` in Chrome via MCP; check console clean, screenshot each tab, fix visual defects (label collisions, overflow).
- [ ] Eyeball the ledger against remembered reality (the G validation step) — flag anything absurd to the user rather than papering over it.
- [ ] Update `analysis/README.md` (pipeline: mirror → backfill → payload → site; export = copy `site/index.html`) and `docs/NEXT_STEPS.md` (workstream 3 step 2 status).
- [ ] Commit on `analysis-viz-exploration`; push; leave PR/merge to the user.

## Self-Review

- Spec coverage: G/A+B/E/H tabs (Task 4), one screen (tab bar), G-first validation (Task 5 eyeball step), keep-in-repo + exportable single file (Task 3 build-site). ✓
- NEXT_STEPS backfill constraints: checkpointed (phase A cache), unwindowed series (payload computes from full parquet), gap resets (carry_identity), no LLM naming (never calls naming), sources.json prerequisite (Task 1). ✓
- Types consistent: parquet columns ↔ payload reader ↔ template payload keys named identically. ✓
