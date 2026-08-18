# Newvelles — Status & Next Steps

_Last updated: 2026-08-17, at the completion of the redesign cutover._

## Where the project stands (shipped 2026-08-16/17)

The full redesign (see `docs/design_handoff_newvelles/`) is **live in production**:

- **newvelles.com's front page is the new board** (dense wire at "Full wire"); the
  previous three-level UI is kept at `/classic` during the transition.
- **Backend pipeline** (all in `RunNewvelles`, image `py312-qa-20260816-221002`):
  RSS → cluster → **merge/classify into stories** (`newvelles/models/stories.py`,
  schema 0.3.0) → **momentum** (cross-day identity, 14-day rollup,
  `newvelles/models/momentum.py`) → **Claude Haiku naming via Bedrock**
  (`newvelles/models/naming.py`, IAM-only, no API keys) → gated S3 publish.
  `latest_news.json` (0.2.1) continues unchanged for `/classic`.
- **Safety rails**: pre-publish sanity gate (`newvelles/utils/publish_gate.py`),
  `make restore-data`, S3 versioning + 30d noncurrent expiry on the public
  bucket, `make rollback-prod`, Bedrock $10/mo alert + **$15/mo hard-stop**
  budget action (auto-attaches `newvelles-bedrock-deny` to the Lambda role;
  reverse command in `docs/ENVIRONMENT.md`).

### Operational notes learned the hard way

- **Prod deploys**: `bin/deploy-to-environment.sh` now preserves the naming env
  vars (a deploy once wiped them → silent fallback to local naming; fixed).
  The deploy script runs its own test invocations — extra Lambda runs right
  after a deploy are normal.
- **Web deploys** (`newvelles_web/bin/deploy.sh`) need: Flask running on
  **:5001** for the Playwright e2e gate (`run.py` listens on 5000 — mismatch),
  and `PATH="/opt/homebrew/bin:$PATH"` so **aws CLI v2** wins over the backend
  venv's v1 (v1 lacks `lightsail push-container-image`).
- The coverage perf test needs `NEWVELLES_TEST_UPLOAD_TIMEOUT=900` on this
  machine (`make test-local-complete` documents itself when it fails without).
- Bedrock required the **Anthropic use-case form** (submitted via
  `PutUseCaseForModelAccess`, `intendedUsers` must be a numeric string).

### Deliberate leftovers from the cutover

- After `/classic` traffic dies out (give it weeks): retire it, then stop
  writing `latest_news.json` — but only after the historical backfill below
  exists, so no information is lost.
- Naming cache converges over runs (cap is 60 new calls/run); expect the
  llm/fallback mix in `stories.json` to keep improving for a few days.

---

## Next steps (three workstreams, in intended order)

### 1. RSS feed health: logging → review skill → recurring runs

**Motivation (observed, not hypothetical):** recent prod runs fetched articles
from only **65 of 84 configured feeds**; the 2021 archive shows long-dead feeds
(HuffPost, CNN top stories, CBS locals, old NY Daily News URLs) that silently
rotted out of the corpus. Nothing currently records *which* feeds fail or why.

**Step 1 — build fetch logging (prerequisite). ✅ DONE (2026-08-17).**
`newvelles/feed/health.py` builds one record per feed per run (url,
http_status, resolved_url, entry_count, newest_entry_age_days, latency_ms,
bozo, error, ok). `parse_feed(..., health=[])` collects them;
`build_data_from_rss_feeds_list` emits: summary lines to stdout/CloudWatch
always, full doc to the private bucket at
`feed_health/feed_health_<ts>.json` when `AWS_LAMBDA=true`. Fail-open —
health problems never break a news run. Schema:
`schemas/feed_health_schema.json`; tests: `test/test_feed_health.py`.

**Step 2 — a Claude Code skill. ✅ DONE (2026-08-17).**
`.claude/skills/rss-feed-review/SKILL.md` (checked in; `.gitignore` now
excludes only `.claude/*` except `skills/`). First execution ran the same day:
PR #38 retired 4 feeds + a duplicate, replaced 7 dead ones (all confirmed
across 3 forced prod runs + live tests with browser-UA retry), fixed 3
redirected URLs, and added 7 net-new sources (Guardian World; Ars/Verge/
TechCrunch; Hill/NPR/PBS politics). Result: 86/86 feeds ok on a local smoke
run. Retirements recorded in `data/rss_retired.txt`; retired feeds stay in
`data/sources.json` for the historical backfill. The skill's original spec
(kept for reference):
- Live-test every feed in `data/rss_source.txt` + `data/rss_qa_reliable.txt`
  (status, redirects, parseability, article freshness).
- Read the accumulated `feed_health.json` history and classify feeds:
  healthy / degraded / dead (e.g. dead = no articles for N days).
- Propose replacements and **new sources** (research current equivalents for
  dead feeds; suggest net-new outlets for under-covered sections).
- Produce a PR updating `data/rss_source.txt` + `data/sources.json`
  (the coverage test in `test/test_utils_sources.py` keeps the table honest).

**Step 3 — run it on a cadence.** Options: `/loop`-style recurring invocation,
a scheduled cloud agent, or simply triggered when the health log crosses a
threshold (e.g. >5 feeds dead for 3+ days). Health docs now accumulate in
`s3://newvelles-data-bucket/feed_health/` every run (6h schedule) — after a
couple of weeks of data, pick the trigger. This is the only remaining piece
of workstream 1.

**Operational note (2026-08-17):** `make prod-deploy` run from inside the
backend venv fails at the env-var step — the venv's aws CLI v1 can't parse
the `--environment` shorthand (same v1/v2 issue as web deploys). Prefix
`PATH="/opt/homebrew/bin:$PATH"` (aws v2). A failure there is after the image
update, which still lands; env vars are left untouched (verify with
`aws lambda get-function --function-name RunNewvelles`).

### 2. Research vertical: papers alongside news

Extend the pipeline beyond news to research output — arXiv (per-category
Atom feeds + API), journal RSS (Nature, Science, PNAS…), possibly PubMed /
Semantic Scholar for enrichment.

The design handoff already anticipated this (Build Spec, "Deferred" list):
> **Research domain.** A separate corpus with its own weighting — venue,
> citation velocity, distinct groups working on a problem — rather than
> outlet count. Same shell, different ranking. Worth a spec of its own.

Sketch (needs its own spec before building):
- Separate feed list (`data/rss_research.txt`) and source table entries with a
  research-oriented section vocabulary (fields/disciplines, not World/Tech).
- Same merge/identity machinery; **different ranking** (venue weight +
  velocity instead of outlet count) and probably different clustering
  thresholds (paper titles are longer and more distinctive than headlines).
- Separate output (`research.json`) and a board tab/second board — don't mix
  corpora in one ranked list.
- Naming prompt needs a research variant (state the finding, not the event).

### 3. Historical analysis (independent workstream, publishes to glhuilli.github.io)

**Goal:** a multi-year analysis/visualization of the news archive, published
on the personal site. Treated as its own workstream inside this repo.

**Measured facts (2026-08-17):** the private bucket holds **9,294 archived
runs, 1.78 GB, 2021-07-10 → present, all on schema 0.2.1** (no format drift).
A 2021 file runs through today's `build_stories()` unmodified (~0.7-4s/run
incl. spaCy NER). Early-era files carry the heavy intra-group duplication
(e.g. 1,453 entries → 332 unique articles) that the merge logic consolidates.

**Step 1 — done:** `scripts/pull_archive.py` / `make pull-archive` mirrors the
archive to `archive/YYYY/` (gitignored), resumable, ~16-way parallel.
Transfer cost ≈ $0.25, roughly an evening of runtime overall.

**Step 2 — backfill dataset** (`scripts/backfill_history.py`, to build):
replay the mirror chronologically through `build_stories()` (parallel) + the
momentum identity matcher (sequential), emitting an **analysis-ready columnar
dataset**, not per-run JSONs:
- `stories.parquet`: one row per (run, story) — run_ts, story_id, headline,
  kind, section, outlet_count, article_count, keywords, entities,
  first_seen, days_running.
- optionally `articles.parquet` (one row per article occurrence).
- **full unwindowed** per-story coverage series (do not reuse prod's 14-day
  trim) — this is where story-lifetime / coverage-concentration analysis lives.
- Checkpointed/resumable; identity carry resets across archive gaps
  (yesterday-only rule — by design).
- **No LLM naming by default** ($0; fallback headlines are real headlines and
  analysis reads counts/keywords/entities anyway). Optional
  `--name-top-stories` (≥3 outlets ≈ 60-80k unique stories ≈ **$55-75** of
  Haiku); naming everything ≈ 250k stories ≈ $200-250 — not justified.
- Before running: extend `data/sources.json` with the ~10-20 retired
  historical feeds (HuffPost, CNN, CBS locals…) so early years get correct
  outlets/sections instead of the domain fallback.

**Step 3 — the analysis itself:** DuckDB/pandas over the Parquet; candidate
angles: longest-running stories since 2021, coverage concentration by outlet
over time, section drift, story-lifetime distributions, duplication-era vs
current-era corpus shape. Output: visualizations + write-up for
glhuilli.github.io.

---

## Smaller follow-ups

- **Dependabot for Python deps:** spaCy drifts often (we were 12 patch
  releases behind when the entity guard landed). Check whether
  `.github/dependabot.yml` covers the `pip` ecosystem / `requirements.txt`;
  if not, add it so version bumps arrive as PRs automatically.

## Pointers

- Redesign handoff & specs: `docs/design_handoff_newvelles/`
- Implementation plans executed: `docs/superpowers/plans/`
- Env vars & Bedrock guardrails: `docs/ENVIRONMENT.md`
- Data restore / rollback: `docs/PRODUCTION_ROLLBACK_GUIDE.md`
- Web-repo counterpart of this status: `newvelles_web/docs/REDESIGN_STATUS.md`
