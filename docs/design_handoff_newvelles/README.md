# Handoff: Newvelles redesign

## Overview

Newvelles clusters RSS headlines and publishes the result as JSON to S3; a static
JS front end renders it. The current site shows ~179 overlapping "groupings"
named by shared headline fragments (`[next time]`, `[6 takeaways]`), which reads
as noise even though a day's corpus is only ~30-40 real stories.

This redesign does three things:

1. **Merges** overlapping groupings into stories, ranked by *distinct outlets*.
2. **Names** each story with a generated neutral headline (Claude Haiku via
   Amazon Bedrock), falling back to a real headline on any failure.
3. **Adds momentum** — a 14-day series per story, precomputed into a small
   rollup file, so a story can show how it grew.

The front end becomes two views: a **board** landing page (one lead story,
coverage cards, a "barely covered" rail) that dives into a **wire** (dense
ranked list, expand in place). Search stays, demoted from front door to filter.

## About the design files

The files in `prototype/` are **design references created in HTML** — working
prototypes showing intended look and behaviour, not production code to copy.
The task is to recreate them in `newvelles_web`'s existing environment (vanilla
JS modules, no framework, no build step) using its established patterns.

The prototype is a single self-contained Design Component. Open
`prototype/Newvelles Wire.dc.html` in a browser; no server needed. Its `STORIES`
array is a hardcoded fixture — the real implementation reads `stories.json`.

`prototype/Newvelles Redesign.dc.html` holds the three original front-page
directions (`1a` ranked wire, `1b` morning board, `1c` streaks) plus a mobile
read. `1a` and `1b` were combined into the built prototype; `1c` was not built
and is included as reference for the deferred archive view.

## Fidelity

**High-fidelity.** Final colours, typography, spacing and interactions.
Recreate pixel-accurately. All values come from the Nocturne design system
(dark, low-chroma, single blurple accent) — tokens listed below.

## Two repositories

| Repo | Language | Role |
| --- | --- | --- |
| `newvelles` | Python, Lambda | Produces JSON to S3. Owns all pipeline work. |
| `newvelles_web` | Vanilla JS | Reads JSON from S3. Owns all UI work. |

They meet only at files in a public S3 bucket. **The contract is the fixture in
`fixtures/`** — commit it to both repos and each side can be built without
waiting for the other.

Read `specs/Newvelles Delivery Plan.dc.html` for milestone ordering and
`specs/Newvelles Build Spec.dc.html` for algorithms and schemas. Both open in a
browser and print to PDF.

---

## Screens

### 1. Board (landing)

**Purpose:** a 3-5 minute morning skim. What is biggest today, what else
matters, what nobody else is covering.

**Layout:** page max-width 1180px, 28px padding, `#12141f` page ground on
`#161826` surface. Header row (brand + date line left, search + "Full wire"
button right), 14px bottom padding, 1px `rgba(233,233,237,.16)` bottom border.
Below it a CSS grid: `minmax(0,1fr) 292px`, 26px gap, `align-items: start`.

**Left column** (16px column gap):

- **Lead card.** `linear-gradient(160deg,#232532,#1b1d2b)`, 1px `#3f424d`
  border, 10px radius, 22px padding. Contains: a kicker row (16×1px `#9184d9`
  bar + "BIGGEST STORY TODAY" in 10px JetBrains-Mono-equivalent monospace,
  600 weight, .14em letter-spacing, uppercase, `#9184d9`); headline at 27px /
  1.18 / -.022em in `#e9e9ed`; a stats row (three 22px numbers with 10.5px
  `#75798c` labels — outlets, articles, days running — plus a 190×42 sparkline
  right-aligned); then top 3 articles separated by a 1px top border, each a
  flex row of 13.5px `#cfd3e5` title and 11px `#75798c` source; finally an
  "Open all N articles" line in 11.5px `#9184d9`.
- **Card grid.** `repeat(2, minmax(0,1fr))`, 14px gap. Each card `#232532`,
  1px `#3f424d`, 10px radius, 16px padding: 15.5px headline, 11.5px meta
  (`N outlets · N days` or `new today`), and a full-width 22px sparkline.
- **"See all N stories in the wire"** ghost button, left-aligned.

**Right rail** (26px section gap), three blocks, each headed by the same 10px
uppercase monospace label in `#9397ab`:

- **Covered by everyone** — 4 rows, each a 12.5px label + 11px outlet count on
  a baseline-aligned row, above a 4px `#292b31` track with an accent-ramp fill
  (`#9184d9` ≥9 outlets, `#796cbf` ≥6, else `#5d5294`) at width proportional to
  the lead story.
- **Barely covered** — sub-line "Three outlets or fewer picked these up", then
  rows of 13px headline + 11px meta.
- **By section** — pill row, each `Section N`, 10.5px, `#232532` fill, 1px
  `#3f424d`, 999px radius.

**Every element in this view is a link.** Headlines, cards, coverage bars and
section pills all navigate to the wire. See Interactions.

### 2. Wire (deep dive)

**Purpose:** work through everything; find a specific thing.

**Layout:** same page frame. Header adds a "← Today" link before the brand.
Below the header: a filter pill row (All + sections with counts), a sort control
(Rank / Most covered / Newest), then the story list.

**Story row** is a CSS grid `26px 1fr 132px 104px`, 18px gap, `align-items:
start`, 15-16px vertical padding, separated by 1px `rgba(233,233,237,.1)` top
borders:

1. **Rank** — 13px monospace, `#9184d9` when expanded/first, else `#595d6c`.
2. **Story** — headline (19px expanded, 16px collapsed), 12px `#9397ab` meta
   line (`N outlets · N articles · running N days · last update Nh ago`),
   keyword pills, and when expanded an article list indented behind a 1px
   `#3f424d` left border with 14px padding.
3. **Momentum** — 132×34 SVG polyline, 1.6px stroke, round joins and caps, plus
   a 10.5px `#75798c` trend label ("peaked yesterday").
4. **Sources** — a 5px-tall stacked bar of accent-ramp segments sized by article
   share, above 10.5px outlet names.

The expanded row carries `linear-gradient(90deg, rgba(145,132,217,.07),
transparent 60%)`.

### 3. Mobile

Single column, 390px. Rank and sparkline share a row above the headline;
sparkline shrinks to 70×18. Sources column drops entirely — outlet count moves
into the meta line. Hit targets ≥44px.

---

## Interactions & behaviour

- **Board → wire.** Clicking any headline, card, coverage bar or "Open all"
  switches view to the wire with that story expanded, filters reset. Section
  pills switch to the wire filtered to that section. Typing in the board search
  switches to the wire with the query applied.
- **Wire → board.** The "← Today" link, which also clears query, filter and
  keyword.
- **Expand.** Clicking a story row toggles its article list in place. Multiple
  rows may be open at once. No page navigation, no third level — the old
  three-level drilldown is gone.
- **Search.** Filters over story headline, article titles, outlet names and
  keywords. Case-insensitive substring. Shows "N of M stories" and an empty
  state with a clear affordance.
- **Keyword pills.** Clicking one filters to stories carrying it; clicking
  again clears.
- **Sort.** Rank (outlet count, then articles), Most covered (outlet count),
  Newest (latest published).
- **Article links.** Open in a new tab, `rel="noopener"`.
- **Filter counts** must reflect the *current* result set, not the corpus —
  showing "All 23" beside a single visible story was a bug found in review.

No loading or error states are designed. The data is one static JSON fetch;
render a minimal skeleton on the board's lead card and a plain retry line on
failure, matching the muted text colour.

## State

Six variables, all client-side, no persistence and no accounts:

```
view      'board' | 'wire'
query     search string
cat       active section filter, default 'All'
keyword   active keyword pill or null
sort      'rank' | 'outlets' | 'newest'
open      { [storyId]: true }   expanded rows
```

Data: two `fetch` calls at load, `stories.json` and `momentum.json`, joined on
story id. Nothing else is fetched.

## Design tokens (Nocturne)

Colours — do not introduce values outside these ramps:

```
page ground     #12141f
surface         #161826
raised surface  #232532
panel           #1b1d2b
border          #3f424d
hairline        rgba(233,233,237,.10 / .12 / .16)
track           #292b31

text            #e9e9ed
text secondary  #cfd3e5
text muted      #9397ab
text dim        #75798c
text faint      #595d6c

accent          #9184d9
accent light    #b5abfc
accent tint     #d2cefd
accent ramp     #796cbf  #5d5294  #423a6a
accent wash     rgba(145,132,217,.07 / .16 / .18)
```

Type: Inter, weights 400/500/600 only — never bolder than 500 for headings.
Monospace (JetBrains Mono or system) for ranks, kickers and dates.

```
lead headline   27px / 1.18 / -.022em / 400
story headline  19px / 1.25 / -.015em   (16px collapsed)
card headline   15.5px / 1.3
brand           24px / -.02em / 500
article title   13.5px / 1.4
meta            11.5-12px
kicker          10px / 600 / .14em / uppercase / mono
```

Radius 8px controls, 10px cards, 999px pills. Spacing is the system's 0.7×
density scale; the values above are already on it. Icons: Phosphor. Sparkline
strokes 1.5-2px, round caps and joins, no fills except the lead card's 35%
gradient. Accent appears as line and glow, never as a flood.

Interactive states: hover tint from the accent ramp, `:focus-visible { outline:
2px solid var(--color-accent); outline-offset: 2px }`. Never leave the default
focus ring.

## Data contract

`fixtures/stories_v0.3.0.json` and `fixtures/momentum_v0.3.0.json` are the
contract, generated from a real fetch (127 articles, 12 feeds — every link,
title, outlet and timestamp real). `fixtures/README.md` documents how each field
was derived and, importantly, what is approximated: the momentum series is
bucketed by article publish date rather than accumulated daily, because daily
rollups do not exist yet.

Key fields per story: `id`, `headline`, `headline_source` (`llm` | `fallback`),
`kind` (`story` | `roundup` | `deal`), `keywords`, `entities`, `section`,
`outlet_count`, `article_count`, `days_running`, `latest_published`, `outlets[]`,
`articles[]`.

**The board shows `kind == "story"` only.** Roundups (single-outlet article
series) and deals (affiliate posts) stay reachable behind a wire filter — in the
sample fetch they are 17 of 41 clusters, and ranking them alongside news puts
"This Monitor Is $120 Off" next to ceasefire coverage.

## Assets

None. No images, no logos, no icon files. Icons are Phosphor web font;
sparklines and bars are inline SVG and CSS generated from data.

## Files

```
prototype/Newvelles Wire.dc.html       the interactive prototype — start here
prototype/Newvelles Redesign.dc.html   three original directions + mobile
specs/Newvelles Build Spec.dc.html     pipeline algorithms and JSON schemas
specs/Newvelles Delivery Plan.dc.html  milestones, repo split, LLM decision
fixtures/stories_v0.3.0.json           the data contract
fixtures/momentum_v0.3.0.json          14-day series (approximated — see README)
fixtures/README.md                     provenance and derivation rules
KICKOFF.md                             starting prompts for each repo
```

Open the `.dc.html` files directly in a browser. Both spec documents print to
PDF cleanly.
