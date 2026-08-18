# Analysis workspace

Standalone workspace for the historical analysis of the news archive
(2021–present). Nothing here ships to production:

- The Lambda Dockerfile copies explicit paths only (`newvelles/`, `data/`,
  `handler.py`, …) — this folder never enters the image.
- The pipeline never imports from this folder.
- Analysis code uses its own environment and its own libraries. When Python
  work starts here, create `analysis/requirements.txt` and a separate venv —
  do not add analysis dependencies to the root `requirements.txt`.

## Contents

| File | What it is |
|---|---|
| `visualization_options.html` | Self-contained gallery of nine candidate visualizations for the 5-year archive, each as a working D3 sketch over **synthetic data**. D3 v7 is inlined — the file makes zero network requests. Open it directly in a browser. |

## The nine options (summary)

| Option | Form | One-line purpose | Verdict |
|---|---|---|---|
| A | Zoomable annotated timeline | When did news happen, what drove each surge | Build — centerpiece backbone |
| B | Topic streamgraph + share toggle | How attention shifted between topics | Build — pairs with A |
| C | Ridgeline small multiples | Each section's own rhythm | Companion to B |
| D | Calendar heatmap | Does news have seasons | Nice-to-have, good navigation |
| E | Story-lifetime scatter | Flash vs slow-burn stories | Strong candidate |
| F | Rank bump chart | Section drift over years | Cheap add |
| G | Cycle-breaker table + sparklines | Data validation ledger | **Build first** |
| H | Coverage-curve shape clustering | Are there kinds of news cycles | The experimental bet |
| I | Story embedding galaxy | 250k stories as a space | Hold in reserve |

Full specs, effort/risk calls, and caveats live inside the HTML, card by card.

## Recommended order

1. **G** — one afternoon on `stories.parquet`; validates the backfill before any
   visualization work.
2. **A + B** — one zoomable page: overview strip drives a streamgraph detail,
   annotated from G's ledger.
3. **H** — the research piece; if clusters are mush, matrix-profile discord days
   still make a section.
4. **I** — only after A/B/G ship, and only if a 10k-story embedding sample shows
   structure.

## Notes

- The chart palette is the validated reference palette from the dataviz method
  (CVD-checked in light and dark modes; the gallery implements both).
- Real-data versions depend on workstream 3 step 2: `scripts/backfill_history.py`
  producing `stories.parquet` (see `docs/NEXT_STEPS.md`).
