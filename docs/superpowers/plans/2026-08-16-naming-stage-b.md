# LLM Naming (Stage B / M3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fallback headlines with generated neutral ones via Claude Haiku on Amazon Bedrock, behind a four-provider interface (`bedrock`/`anthropic`/`openai`/`local`, default `local`), with an identity-keyed cache, the >50%-growth rename rule, a per-run call cap, and graceful fallback on any failure.

**Architecture:** `newvelles/models/naming.py`. The pipeline order becomes build_stories → apply_momentum → **name_stories** → emit — naming runs *after* momentum so the cache keys on carried (stable) story ids; a fingerprint-keyed cache would rename on every article change and violate the rename rule. `name_stories(stories_data, cache)` is pure given a provider function; cache I/O helpers mirror momentum's (S3 private `story_names.json` / local `./cache/story_names.json`). Remote calls run 4-wide in a ThreadPoolExecutor with an 8s timeout and 2 retries; the run is capped at 60 new calls, `kind=="story"` first in rank order. All failures leave the existing fallback headline in place and are counted (monitoring: fallback count catches a silent outage).

**Tech Stack:** boto3 `bedrock-runtime` (IAM auth — **no API keys in the Lambda**; the `anthropic`/`openai` providers are dormant escape hatches using `requests` + env keys), spaCy for the offline `local` provider. No new dependencies.

## Global Constraints

- All-AWS in production: provider `bedrock`, model `us.anthropic.claude-haiku-4-5-20251001-v1:0` (inference profile — the bare `anthropic.` id is INFERENCE_PROFILE-only), region from `BEDROCK_REGION` or the Lambda's region. IAM policy `bedrock-invoke-haiku` already on the execution role.
- Default provider `local` → a fresh clone runs offline with zero credentials.
- `headline_source` stays within the schema enum: `"llm"` for remote-provider successes, `"fallback"` otherwise (including the `local` spaCy provider — contract untouched).
- Rename rule (handoff recommendation, flagged for confirmation in the PR): a cached story is re-named only when its article count has grown **>50%** since the naming that produced the current headline.
- Cost guardrails: cap `NEWVELLES_NAMING_MAX_CALLS` (default 60) new calls per run; prompt from the build spec verbatim; 8s timeout, 2 retries; $10/month AWS budget alert on Bedrock spend.
- Naming must never fail a run. Cache only successful namings; error- and cap-fallbacks are retried next run.
- Env vars documented in `docs/ENVIRONMENT.md`: `NEWVELLES_NAMING_PROVIDER`, `NEWVELLES_NAMING_MODEL`, `NEWVELLES_NAMING_TIMEOUT`, `NEWVELLES_NAMING_MAX_CALLS`, `NEWVELLES_NAMING_CACHE`, `BEDROCK_REGION` (+ dormant `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`).
- Branch `redesign/naming`.

## Tasks

### Task 1: naming core — prompt, postprocess, provider registry, local provider
`build_prompt(story)` (spec prompt, up to 12 headlines longest-first with outlets); `_postprocess(text)` (first line, strip quotes/whitespace/trailing period, reject empty or >140 chars via `ValueError`); `_name_via_local(story)` (spaCy: top entities + highest-scoring noun chunks composed into a plain phrase — real implementation, no network); `PROVIDERS` dict; `resolve_provider()` from env. Tests: prompt shape/cap/ordering, postprocess cases, local provider returns non-empty sensible phrase offline, unknown provider raises KeyError.

### Task 2: bedrock/anthropic/openai providers
`_name_via_bedrock(prompt)` via boto3 `bedrock-runtime` `invoke_model` (anthropic_version `bedrock-2023-05-31`, max_tokens 60, botocore Config(connect 3s / read `NEWVELLES_NAMING_TIMEOUT` 8s, retries 2)). `_name_via_anthropic` / `_name_via_openai` via `requests` with env keys (raise if unset). Tests mock boto3/requests at the network boundary: request body shape, response extraction, timeout config, missing-key errors.

### Task 3: `name_stories` orchestration + cache + rename rule
`name_stories(stories_data, cache, provider_name=None) -> (stories_data, new_cache, stats)`. Selection: cache-hit stories reuse cached headline/source unless grown >50%; new/regrown stories are named up to the cap, `kind=="story"` first in list (rank) order, remote calls in `ThreadPoolExecutor(4)`; `local` runs serially (spaCy isn't thread-safe). Failures/cap → keep existing fallback headline, count in `stats` (`llm_named`, `cache_hits`, `fallbacks`, `renamed`). Cache entries `{headline, headline_source, article_count, named_at}`; prune entries not touched in 30 days. Cache I/O: `load_naming_cache_s3/local`, `save_naming_cache_s3/local` (immediate save — cached names remain valid regardless of the publish gate). Tests: cache prevents repeat call, 50% boundary (1.5× exact keeps, above renames), failure→fallback not cached, cap respected with story-kind priority, stats counts, prune.

### Task 4: wiring + docs + guardrails
`handler.py` + `__main__.py`: after momentum, load cache → `name_stories` → save cache → print stats line (fallback count visible in logs). ENVIRONMENT.md + CLAUDE.md. AWS budget alert (`aws budgets create-budget`, $10/month, Amazon Bedrock service filter, notify at 80%/100%). Set QA Lambda env `NEWVELLES_NAMING_PROVIDER=bedrock` + model id (merged with existing bucket vars) so the next QA deploy activates naming. Live smoke test: one real Bedrock naming call on a real story from the archive. Full suite, lint, PR.
