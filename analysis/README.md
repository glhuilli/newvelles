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
| `visualization_options.html` | Self-contained gallery of nine candidate visualizations, each as a working D3 sketch over **synthetic data**. The design exploration that picked the dashboard below. |
| `build_payload.py` | Aggregates `data/stories.parquet` into the dashboard payload (daily/weekly series, ledger, lifetimes, archetype k-means, matrix-profile discords) and builds the site. Runs in `analysis/.venv`. |
| `site/template.html` | Dashboard template (tokens, tabs, all chart code). `/*__D3__*/` and `/*__DATA__*/` markers are filled at build time. |
| `site/index.html` | The built dashboard — one self-contained file over **real archive data**. This is the file to export to glhuilli.github.io. |
| `vendor/d3.min.js` | D3 v7.9.0, vendored for offline builds. |

## Pipeline (real data)

```
make pull-archive                                   # 1. mirror S3 archive (resumable)
source .python/newvelles/bin/activate               # 2. main venv (build_stories + spaCy)
pip install pyarrow                                 #    ad hoc, NOT a deployment dep
python scripts/scan_archive_sources.py              # 3. confirm sources.json coverage
python scripts/backfill_history.py --workers 10     # 4. archive -> stories.parquet (resumable)
analysis/.venv/bin/python analysis/build_payload.py --site   # 5. payload + site/index.html
```

## Classification (3-level taxonomy)

`taxonomy.json` (v1.0): 13 majors → ~60 subs → open meta tags, seeded from
IPTC Media Topics. Golden set: 4,020 stories labeled in-session by Fable
(`data/golden_sample.parquet` — the permanent eval reference).

```
analysis/.venv/bin/python analysis/classify_bedrock.py --workers 8  # full corpus, resumable shards
analysis/.venv/bin/python analysis/merge_labels.py                  # -> story_labels.parquet
analysis/.venv/bin/python analysis/eval_labels.py data/haiku_labels # score vs golden
analysis/.venv/bin/python analysis/build_payload.py --site          # refresh Categories tab
```

Benchmarks and route comparison (Haiku / embeddings / qwen3:8b): see
`data/eval_report.md`. Route C: `train_classifier.py`; Route D: `classify_qwen.py`.

Export = copy `analysis/site/index.html` anywhere; it has zero external
dependencies.

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
