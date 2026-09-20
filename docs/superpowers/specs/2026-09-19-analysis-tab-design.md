# Analysis tab on newvelles.com — design

_Date: 2026-09-19. Status: draft for review. Prototype: https://claude.ai/artifact/P1Ldpg1eusqtKFg9txAgaU_

## Goal

Give the historical analysis a home on newvelles.com instead of the personal
site. The board header gets a tab strip (Today, Wire, Analysis). The Analysis
view lists dated entries. Each entry carries its own set of panels. Entry 01 is
"Five years of news cycles" (Jul 2021 to Aug 2026), which is the current
dashboard in `analysis/site/`, ported onto the board's Nocturne design system.

The first build ports all eight panels so they can be reviewed locally against
real data. Which panels stay is decided after that review. Production deploy is
a separate later step and is out of scope here.

## Scope

In scope:

- Data contract for entries and payloads, built and published from this repo.
- Flask proxy routes and Vite dev proxy in `newvelles_web`.
- Header tab strip, `analysis` view, entries row, entry header, panel pills,
  and all eight panels in `newvelles_web/src/redesign/`.
- Fixture, local and live data modes for the analysis data.
- Unit, integration and e2e tests.
- A local review workflow with the real payload.

Out of scope:

- Deploying to Lightsail. `bin/deploy.sh` is unchanged.
- Editing the Learnings content or the analysis itself.
- The methods post link target. The index carries the field. The value can be
  empty until the post is published.
- Splitting the payload into a lazy detail file. Recorded as a follow-up.

## Part 1 — Data contract (newvelles repo)

Two public files under an `analysis/` prefix in the public bucket.

**`analysis/index.json`** (schema `schemas/analysis_index_schema.json`, version `0.1.0`):

```json
{
  "version": "0.1.0",
  "generated": "2026-09-19T20:00:00Z",
  "entries": [
    {
      "id": "five-years",
      "number": 1,
      "title": "Five years of news cycles",
      "summary": "How stories start, peak and fade across the whole archive ...",
      "first_day": "2021-07-10",
      "last_day": "2026-08-18",
      "published": "2026-09-19",
      "links": { "post": "", "code": "https://github.com/glhuilli/newvelles/tree/main/analysis" },
      "panels": ["timeline", "ledger", "lifetimes", "archetypes", "stats", "categories", "topstories", "learnings"],
      "payload": "/analysis/entries/five-years/payload.json",
      "stats": { "runs": 9311, "stories": 114927, "days": 1832, "majors": 13 }
    }
  ]
}
```

Entries are listed newest first. `id` matches `^[a-z0-9-]+$`. `panels` is the
ordered list the front end renders. Unknown panel names render a placeholder,
so an entry can drop or add panels without a code change to the index.

**`analysis/entries/<id>/payload.json`** is today's `analysis/site/data.json`
plus two fields: `version: "0.1.0"` and `entry: "<id>"`. The existing keys
(`meta`, `daily`, `weekly`, `sections`, `ledger`, `annotations`, `events`,
`drill`, `clusters`, `lifetimes`, `archetypes`, `discords`, `stats`,
`categories`) are unchanged so the ported renderers read the same shapes.
Size today: 1.38 MB raw, 315 KB gzipped. It is fetched only when the entry is
opened.

**Builder.** `analysis/build_payload.py` gains `--entry <id>`. It writes
`analysis/entries/<id>/payload.json` (gitignored) and upserts the entry in
`analysis/entries/index.json` (checked in). Entry metadata (title, summary,
links, panels) lives in `analysis/entries/<id>/entry.json` (checked in). The
builder merges `entry.json` with computed `first_day`, `last_day`, and `stats`.
`--site` keeps working for the standalone page.

**Publish.** `make publish-analysis ENTRY=<id>` validates `index.json` against
the schema, gzips both files, and uploads them to the public bucket with
`Content-Encoding: gzip`, `Content-Type: application/json`, and a short
`Cache-Control` (`max-age=300`) for the index and a long one for the payload.
It uses the same `upload_to_s3` path as the other public files. It never runs
inside the Lambda.

## Part 2 — Flask proxy and dev proxy (newvelles_web)

`newvelles_web/analysis.py` mirrors `stories.py`:

- `GET /analysis/index.json` → bucket `analysis/index.json`, or
  `data/local/analysis/index.json` when `local=True`.
- `GET /analysis/entries/<id>/payload.json` → bucket path, or the local file.
  `<id>` is validated against `^[a-z0-9-]+$` before any fetch.

`vite.config.js` proxies `/analysis` to `localhost:5001`, matching the four
existing entries.

Data modes in `src/redesign/main.js` gain an `analysis` base per mode:

| Mode | Index | Payload |
|---|---|---|
| fixture | `/data/fixtures/analysis/index.json` | `/data/fixtures/analysis/entries/<id>/payload.json` |
| local | `/data/local/analysis/index.json` | `/data/local/analysis/entries/<id>/payload.json` |
| live | `/analysis/index.json` | `/analysis/entries/<id>/payload.json` |

The fixture is a trimmed real payload (a few weeks of `daily` and `weekly`,
five ledger rows, three events, one drill major, the clusters those rows
reference, a subset of lifetimes, full `archetypes`, `stats`, `categories`).
Target under 150 KB. A script `scripts/make_analysis_fixture.py` in the web
repo produces it from a real payload so it can be refreshed.

## Part 3 — Front end architecture (newvelles_web/src/redesign)

**State.** `state.view` gains `'analysis'`. Two new fields: `entry` (entry id
or `null` = newest) and `panel` (panel name, default `'timeline'`). New
actions: `goAnalysis()`, `selectEntry(id)`, `selectPanel(name)`. Panel-local
interaction (timeline drill, pinned cluster, top-stories mode, ledger sort)
stays inside the panel module and does not go through `setState`.

**Header.** `renderBoard` and `renderWire` share one `renderHeader(state)`
that emits the brand block, the tab strip, and the actions. The tab strip is
three `button[role=tab]` elements bound to `goBoard`, `goWire`, `goAnalysis`.
The two "Full wire →" buttons are removed. The search box is hidden in the
analysis view for this build. The wire tab shows the story count.

**Loader.** `analysis/loader.js` exports `loadIndex()` and `loadEntry(id)`.
Both memoize in module scope. `loadIndex` runs on the first switch to the
analysis view, never at page load. `loadEntry` runs when an entry is selected.
Errors render an inline retry block inside the view, not the page-level error.

**View.** `analysis/view.js` exports `renderAnalysis(container, state)`. It
writes the shell with `innerHTML` (entries row, entry header, pill row, one
`section` per panel with `hidden` on all but the active one, a shared tooltip
element), then calls `mountPanel(name, payload, section)`. Because `render()`
rebuilds `#app` on every state change, the shell is cheap to rebuild and each
panel mounts fresh into its section when it becomes active. A panel that is
already mounted for the same entry and panel is not rebuilt, tracked by a
`data-mounted="<entry>/<panel>"` attribute on the section.

**Panels.** One module per panel under `analysis/panels/`, each exporting
`mount(section, payload, ctx)` where `ctx` carries the tooltip helpers, section
colors, and date formatters that the dashboard's `template.html` script defines
at the top. Renderers move over from `template.html` lines 403 to 913 with
these changes only:

- `d3` global becomes named imports from `d3-selection`, `d3-scale`,
  `d3-shape`, `d3-array`, `d3-axis`, `d3-brush`, `d3-time`, `d3-time-format`.
- `document.getElementById` lookups become `section.querySelector`.
- CSS classes get the `an-` prefix and colors come from Nocturne tokens.
- Module-level state (`drillTo`, `pinnedCluster`, `tsSelected`, `tsMode`,
  `rendered`) becomes closure state per mount.

**Styles.** `analysis/styles.css` is imported by `styles.css`. Tokens:
`--page`→`--nv-page`, `--surface`→`--nv-surface`, `--ink`→`--nv-text`,
`--ink-2`→`--nv-text-secondary`, `--muted`→`--nv-text-dim`,
`--grid`→`--nv-hairline-10`, `--baseline`→`--nv-hairline-16`,
`--accent`→`--nv-accent`. Series `--s1..--s8` use the dashboard's dark set,
validated against `--nv-page` with the dataviz palette validator (all checks
pass). `--s8` for "Other" is `#6b6f80`. No other new colors.

**Dependencies.** `package.json` gains the eight `d3-*` packages as runtime
dependencies. Vite bundles them into the redesign entry.

## Part 4 — Tests (newvelles_web)

- Unit (`tests/unit/analysisLoader.test.js`): index parse, newest-first
  selection, memoization, invalid id rejection, error path.
- Integration (`tests/integration/analysis.test.js`, jsdom, fixture data):
  tab strip switches `state.view`; analysis view renders the entries row, the
  entry header fields, and one pill per `panels` entry; selecting each pill
  mounts that panel without throwing and marks the section mounted; an unknown
  panel name renders the placeholder; the search box is absent in the view.
- e2e (`tests/e2e/analysis.spec.js`): the Analysis tab is visible, clicking it
  shows the entry title, clicking Ledger shows a table.
- The web repo has no Python test harness. The Flask id validation is a pure
  function kept small enough to read, and the local review workflow exercises
  both routes with `curl`. Not adding pytest to the web repo for this.
- In this repo: `test/test_analysis_index_schema.py` validates the checked-in
  index and a rejected malformed one.

Note: `data/` is gitignored in the web repo and the existing fixtures were
force-added. The analysis fixture files are added the same way (`git add -f`).

## Part 5 — Local review workflow

```
# newvelles
analysis/.venv/bin/python analysis/build_payload.py --entry five-years
# newvelles_web
mkdir -p data/local/analysis/entries/five-years
cp ../newvelles/analysis/entries/index.json data/local/analysis/
cp ../newvelles/analysis/entries/five-years/payload.json data/local/analysis/entries/five-years/
VITE_NV_DATA_SOURCE=local npm run dev
```

Open `http://localhost:5173/`, click Analysis. Review each panel. Decisions
about which panels stay are recorded in `analysis/entries/five-years/entry.json`
by editing `panels`.

## Delivery

Two branches named `analysis-tab`, one per repo, each ending in a PR.

- PR A (newvelles): `entry.json`, builder `--entry`, `index.json`, schema,
  schema test, `make publish-analysis`, README note. No S3 upload until the
  UI is accepted.
- PR B (newvelles_web): everything in Parts 2 to 4, all eight panels, fixture
  and fixture script, tests, `REDESIGN_STATUS.md` note. Not deployed.

## Follow-ups (not in this design)

- Lazy `detail.json` holding `clusters` and `drill` (77% of the payload).
- Search inside the analysis view.
- Publishing the methods post and filling `links.post`.
- Retiring `analysis/site/index.html` export once the tab is live.
