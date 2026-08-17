# Fixtures for schema 0.3.0

Two files, both generated from real Newvelles output. Commit them to **both**
repositories (`newvelles/test/fixtures/`, `newvelles_web/data/fixtures/`) so the
backend has a target to produce and the front end has data to render.

| File | What it is |
| --- | --- |
| `stories_v0.3.0.json` | 41 merged, named, source-resolved stories from 127 articles across 12 feeds |
| `momentum_v0.3.0.json` | 14-day series per story, **approximated** — see the caveat below |

## Provenance

Built from `newvelles/latest_news.json` in the backend repo — a real fetch whose
articles carry published timestamps from 2026-07-28 to 2026-08-09. Every link,
title, outlet and timestamp is real. Nothing was invented.

## How each field was produced

- **Merge** — top-level groups joined by union-find where link containment
  `|A∩B| / min(|A|,|B|) >= 0.5`, links normalised (lowercase host, `www.` and
  trailing slash stripped, tracking query dropped).
- **Outlets and sections** — a 12-entry feed table mapping RSS URL to outlet
  name, domain and section. A story takes the modal section of its articles.
  This table is the seed for `data/sources.json`; production needs all 84 feeds.
- **Headlines** — 21 stories carry a hand-written neutral headline standing in
  for the LLM pass (`headline_source: "llm"`). The other 20 use the fallback
  rule: longest title from the outlet with the most articles
  (`headline_source: "fallback"`). The mix is deliberate — the front end should
  look correct in both states.
- **Keywords** — the bracket phrases from the original group identifiers,
  lowercased and deduplicated. These are the pills, not the name.
- **Entities** — a crude capitalised-sequence frequency heuristic, NOT real NER.
  Production uses the spaCy pass. Treat this field as shape only.
- **kind** — `deal` when a majority of titles match a price/offer pattern;
  `roundup` when the story has one outlet and a contiguous title template of 3+
  words carrying no proper noun; `story` otherwise. Result on this fetch:
  24 stories, 7 roundups, 10 deals. No real news cluster is misclassified as a
  roundup. Two known misses the other way — a movie-recommendation series and
  the daily CD/mortgage rate posts still read as `story`; both are single-outlet
  and rank low anyway. Detecting proper nouns by capitalisation fails on
  title-case headlines, so the proper-noun set is collected only from
  sentence-case titles, and weekday/month names count as generic.

## The momentum caveat

The pipeline does not yet store daily rollups, so a true 14-day series does not
exist anywhere. This file approximates one by bucketing each story's articles by
their **published** date rather than by the run that saw them. That is a real
signal — 30 of 41 stories genuinely span more than one day — but it differs from
production in two ways:

1. It sees only what one fetch retained, so early days are undercounted. A story
   that ran hard on 30 July shows only the articles still in the feed on 9 August.
2. `outlets` per day counts outlets publishing that day, not outlets covering the
   story as of that day. Production accumulates the latter.

In production, `momentum.json` is accumulated one datapoint per day, taking
`max(outlets)` across that day's four runs, and only the current day is ever
mutated. Regenerate this fixture from real rollups once M4 lands.

## What this data revealed

Worth knowing before tuning the merge stage:

- **In this fetch, no article appears in more than one top-level group.** The
  merge is a no-op here (41 groups → 41 stories) because it is the 12-feed QA
  set. Cross-group duplication is a production-scale phenomenon: the 84-feed
  fetch behaves very differently.
- **`data/latest_news_example.json` duplicates on a different axis** — 410
  entries for 121 unique links, with one article appearing in up to 16
  *sub-groups* of a single top-level group. Flattening a story to one level of
  articles removes that automatically, no threshold needed.
- **Template clustering is a real quality problem.** Several clusters here are
  held together by shared headline scaffolding rather than a shared subject:
  "Q2 Earnings Call Highlights", "Five Hacks Every X User Should Know", "This X
  Is $Y Off Right Now". TF-IDF cannot tell a template from a topic. Worth a
  filter: a cluster whose articles all come from one outlet and share a title
  template is a roundup, not a story.
- **Commerce content is a large share of the feed set.** Deals and product
  roundups outnumber news clusters here. A `kind: "story" | "roundup" | "deal"`
  field, derived from the same template check, would let the front page rank
  them separately instead of interleaving them.

## Regenerating

The generator is a single pass: merge → resolve → name → bucket. Port it into
`newvelles/models/stories.py` rather than keeping it as a script; the fixture
should be regenerated from a real run once M1 lands, not maintained by hand.
