# Kickoff

Two Claude Code sessions, one per repo, plus a short setup step first. Do the
setup yourself — it takes minutes and it is what lets the two sessions run
independently.

## Step 0 — before any code (you, 15 minutes)

1. **Request Bedrock model access** for `anthropic.claude-haiku-4-5` in the
   region your Lambda runs in. It is per-account, per-region, off by default,
   and it is the only item here with an external wait. File it now; build while
   it clears.
2. **Commit the fixtures to both repos:**
   - `newvelles/test/fixtures/stories_v0.3.0.json` (+ momentum, + README)
   - `newvelles_web/data/fixtures/stories_v0.3.0.json` (+ momentum)
3. **Drop this whole folder into both repos** as `docs/design_handoff/`, or keep
   it somewhere both sessions can read. Claude Code can open the `.dc.html`
   files as text; the specs are readable as HTML source.

## Session A — backend (`newvelles`)

Start here. It is the larger half and the front end can proceed without it.

> I'm reworking the Newvelles pipeline. Read `docs/design_handoff/README.md` and
> `docs/design_handoff/specs/Newvelles Build Spec.dc.html` (open it as text — the
> prose is the spec), then read `handler.py`, `newvelles/models/grouping.py` and
> `newvelles/feed/log.py`.
>
> Before writing any feature code, do the refactor the plan calls for:
> `log_visualization()` and `log_s3()` duplicate their upload logic and have
> already drifted — the Lambda path omits `latest_log_reference`. Collapse them
> into one emit function with a writer strategy (local / S3 / both), keeping the
> existing outputs byte-identical. Tests must pass unchanged.
>
> Then implement Stage A and A.5 only — merge, source resolution, sections, and
> the story/roundup/deal classifier — emitting `stories.json` beside the
> existing `latest_news.json`, which must keep being written exactly as it is
> today. No LLM yet: use the fallback naming rule (longest title from the outlet
> with the most articles).
>
> Validate your output against `test/fixtures/stories_v0.3.0.json` — same
> schema, same field names. Write a JSON schema for it in `schemas/`.

Then, in the same session:

> Now sweep the merge threshold. Pull ~30 stored production runs from the
> private bucket, run the merge at 0.3 / 0.4 / 0.5 / 0.6 / 0.7, and report the
> story count distribution at each. Pick the threshold that keeps a normal day
> in the 25-45 band. Note: the 12-feed QA set cannot test this — no article
> appears in two top-level groups there, so the merge is a no-op. Use production
> files.

After that lands, Stage B (naming) and Stage C (momentum) are independent — do
momentum first if Bedrock access is still pending.

## Session B — front end (`newvelles_web`)

Runs in parallel from day one. It needs nothing from Session A.

> I'm rebuilding the Newvelles UI. Read `docs/design_handoff/README.md` in full —
> it has the complete layout, token and interaction spec — and open
> `docs/design_handoff/prototype/Newvelles Wire.dc.html` to see the working
> prototype.
>
> The prototype is a design reference, not code to copy. Rebuild it in this
> repo's existing vanilla-JS module pattern (no framework, no build step),
> reading `data/fixtures/stories_v0.3.0.json` and `momentum_v0.3.0.json` from
> disk for now — the real S3 URLs come later.
>
> Two views, board and wire, with the state model and every interaction listed
> in the README. Match the tokens exactly; they are Nocturne values and there is
> no room to improvise. Keep search working over headlines, article titles,
> outlet names and keywords.
>
> One bug to avoid, found in review of the prototype: filter counts must reflect
> the current result set, not the whole corpus.

## What to do after both land

In milestone order from the delivery plan: momentum (M4), naming (M3), then
cutover (M5). Before the cutover, close the two data-rollback gaps — S3 bucket
versioning on the public bucket with a 30-day noncurrent expiry, and a
`make restore-data TIMESTAMP=...` target beside `rollback-prod`. Add the
pre-publish sanity gate with M1, since M1 is the first release that can move the
story count.

## Decisions already made

- **LLM:** Claude Haiku via Amazon Bedrock. ~$1/month at this volume. No API
  key in the Lambda — the execution role gets `bedrock:InvokeModel`. Behind a
  four-provider interface (`bedrock` / `anthropic` / `openai` / `local`) so the
  choice stays reversible; default is `local`, so a fresh clone runs offline.
- **Schedule:** unchanged, `rate(6 hours)`. A day's momentum datapoint is
  `max(outlets)` across that day's four runs; only the current day is mutated.
- **Old files:** `latest_news.json` keeps being written on schema 0.2.1 through
  every milestone. Delete only after the new site has been stable for weeks.

## Still open

- **Rename rule.** At four runs a day a story's fingerprint can change four
  times and the headline with it. Recommendation: rename only when the article
  set has grown >50% since the naming that produced the current headline.
  Confirm before Stage B ships.
