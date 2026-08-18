# Stats tab + 3-level story taxonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Stats tab (core stats + top-10 source breakdown) and a Categories tab (core stats per sub-category) to the history dashboard, backed by a 3-level classification (major category → sub-category → meta tags) of all 114,927 stories.

**Architecture:** (1) Re-run backfill phase A with a v2 cache that keeps per-story outlet lists → `stories.parquet` v2 with an `outlets` column. (2) Compute core stats in `build_payload.py` at three grains (run, day, week), overall and per source. (3) A curated taxonomy file (`analysis/taxonomy.json`, seeded from IPTC Media Topics + user examples). (4) Classification in two passes: a stratified golden sample (~2,000 stories) labeled in-session at frontier quality to validate the taxonomy, then the full corpus by the chosen route → `analysis/data/story_labels.parquet`. (5) Dashboard tabs read the new payload sections.

**Tech Stack:** existing analysis venv; classification route per user decision (Bedrock Haiku batch / in-session Fable / sample+SetFit / qwen3:8b experiment).

**Spec:** User directive 2026-08-18 (this conversation): core-stats definitions, top-10 source breakdown, sub-categories beyond the 7 sections, meta tags (entities + group keywords), classification-route exploration.

## Definitions (locked)

- **Run** — one pipeline execution (one Lambda invocation → one archived snapshot). Median 5/day across the archive (schedule varied 4–6h over the years).
- **Story observation** — one (run, story) row: a story seen in one run. 446,519 total.
- **Distinct story (per day/week)** — unique `story_uid` within the window.
- **New story** — a `story_uid` on its `first_seen` day.
- **Story (the 114,927)** — a cross-run, cross-day identity (articles clustered per run, carried across runs/days by Jaccard ≥ 0.4 over keywords ∪ entities).
- **Source** — an outlet as resolved by `data/sources.json` (NYT, BBC, …).

**Core stats** (each reported as median with p25–p75, at three grains: per run, per day, per week):
1. story observations; 2. distinct stories; 3. new stories; 4. distinct stories per source (median across sources active in the window); 5. observations per source.

## Global Constraints

- Analysis-only: no prod code, no root requirements.txt changes; LLM calls (if any) via Bedrock IAM, never API keys (session preference).
- Taxonomy is versioned data (`analysis/taxonomy.json` with `version`); labels parquet records the taxonomy version and the classifier route per row.
- The golden sample is stratified (by year × section × days_seen bucket) and kept forever as the eval set — whatever route labels the full corpus is measured against it (agreement %, per-level).
- Sub-category list is closed (single label, forced choice + "other"); meta tags are open vocabulary, 2–6 per story, lowercase.

---

### Task 1: parquet v2 with outlets

**Files:** Modify `scripts/backfill_history.py` (STORY_FIELDS += "outlets" as `[{outlet, count}]`; cache dir default `analysis/cache/runs_v2`; parquet gains `outlets` json column). Run: phase A full re-run (~50 min, 10 workers, resumable), phase B, verify row count matches v1 (446,519). Update `analysis/build_payload.py` reader accordingly. Commit.

### Task 2: Stats tab

**Files:** Modify `analysis/build_payload.py` (payload key `stats`: the core-stats matrix + per-source breakdown for the top 10 sources by distinct stories: distinct stories, observations, active days, median distinct/day, share of all story-days), `analysis/site/template.html` (fifth tab "Stats": definitions block up top — run/observation/distinct/new in plain words — then the core-stats table, then the top-10 source table with share bars). Rebuild, screenshot, verify numbers against ad-hoc pandas checks (one assertion script run, not eyeballing). Commit.

### Task 3: taxonomy v1

**Files:** Create `analysis/taxonomy.json` — 12 majors, ~55 subs (seeded from IPTC Media Topics + user examples: war, crime, shooting, job market, housing, stock market, movies, entertainment, sports, …), each sub with a one-line definition + 3 example headlines from the corpus. Include `section_mapping` (major → legacy 7-section) for continuity. Review round with the user before mass labeling. Commit.

### Task 4: golden sample (in-session, frontier quality)

Stratified sample: 2,000 stories across year × section × days-seen buckets. Label in-session (batches of ~100 headlines+keywords via parallel subagents, structured output: major, sub, tags[2–6]) → `analysis/data/golden_sample.parquet` + a taxonomy-fit report (sub-category distribution, % forced into "other", ambiguity notes). One taxonomy iteration if >8% lands in "other" or any sub is empty. Cost: ~0.5M session tokens.

### Task 5: full-corpus classification (route per user decision)

- **Route A — Bedrock Haiku 4.5 batch (recommended):** ~770 batched calls (150 stories each, taxonomy + 10 golden few-shots in the prompt); ≈ $15–30, ~1 h with 10-way concurrency (or Bedrock batch-inference overnight at 50% price). Eval vs golden sample; ship if major ≥ 95%, sub ≥ 85% agreement.
- **Route B — in-session Fable:** same batching by subagents; zero dollars, ~8–10M session tokens (~⅔ of remaining budget), 2–3 h. Highest quality; golden and full labels come from the same model (no cross-check).
- **Route C — sample + trained model:** extend golden to ~5k, train SetFit/embedding classifier for major+sub (tags via separate keyphrase step); cheapest at scale, most moving parts, expect sub agreement ~80–88%.
- **Route D — qwen3:8b (v3 experiment):** run the same prompt on the golden sample only; report agreement vs golden as a model-comparison section. Full corpus ≈ 12–48 h local — only if the sample agreement justifies it.

Output for any route: `analysis/data/story_labels.parquet` (`story_uid, major, sub, tags (json), route, taxonomy_version`). Always run Route D on the sample regardless (cheap, good write-up material); Route C stays documented as the scaling fallback.

### Task 6: Categories tab + integration

**Files:** `build_payload.py` (payload key `categories`: per sub-category — distinct stories, observations, share, median distinct/day when active, top 5 tags, one exemplar headline — ranked by distinct stories; plus per-major rollup), `template.html` (sixth tab "Categories": ranked table with share bars + tag chips; majors as grouping rows). Ledger and Lifetimes gain the sub-category in tooltips. Rebuild, verify, screenshot, commit.

### Task 7: eval + docs

Agreement report (route vs golden) committed as `analysis/data/eval_report.md`; README pipeline updated; NEXT_STEPS updated. Push branch.

## Self-Review
- Core stats ×3 grains + per-source ✓ (Task 2); top-10 breakdown ✓; sub-category table ranked by distinct stories ✓ (Task 6); 3-level classification ✓ (Tasks 3–5); route exploration incl. golden-dataset, ML-scaling, spaCy-as-baseline (subsumed: heuristics not pursued beyond eval), local qwen ✓ (Task 5).
- Per-source stats require outlets → Task 1 precedes Task 2. ✓
