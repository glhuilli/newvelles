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
   entry count, newest entry age. Reuse `newvelles.feed.health.build_health_record`.
   Run feeds in parallel (ThreadPoolExecutor, ~16 workers, socket timeout 20s).
   Do NOT rely on live results alone — a feed can be flaky, not dead.
3. **403s may be user-agent blocking**, not death: retry those with a browser
   User-Agent header (fetch bytes with urllib + UA, then `feedparser.parse` the
   bytes). A feed that works with a UA is *degraded (UA-blocked)*, not dead —
   consider whether the pipeline should send a UA before retiring it.

## Step 2 — Classify

- **healthy**: ok in live test AND ok in >80% of recorded runs.
- **degraded**: intermittent failures, or newest_entry_age_days > 7 (stale), or
  permanent redirect (fix the URL), or UA-blocked per above.
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
   (count active feeds per section; note sections with ≤3 feeds).
2. For thin sections, WebSearch for reputable outlets not yet present
   (compare domains against sources.json). Candidate bar: established outlet,
   working RSS with ≥10 entries, fresh (≤2 days), non-paywalled titles.
3. Validate candidates exactly like replacements; add to `data/rss_source.txt`
   + `data/sources.json` with correct outlet/domain/section.

## Step 6 — Verify and ship

1. `pytest test/test_utils_sources.py -v` — every active feed must be mapped.
2. Smoke the pipeline on the changed list:
   `newvelles --rss_file data/rss_source.txt` (venv) — confirm entry counts and
   no new failing feeds in the `📡 Feed health` summary.
3. `make test` must pass.
4. Branch + PR: list every removal/replacement/addition with its evidence
   (status history + live result). Never force-push; never merge without checks.
5. Remind the operator: the list ships with the next image build
   (`make qa-build && make qa-deploy`, then `make prod-deploy`).
