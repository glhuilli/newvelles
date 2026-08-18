#!/usr/bin/env python
"""Replay the mirrored archive into an analysis-ready Parquet dataset.

Workstream 3, step 2 (docs/NEXT_STEPS.md). Two phases:

Phase A (parallel, resumable): each archived visualization run goes through
today's build_stories(); a compact per-run story list is cached under
--cache so re-runs only process missing files.

Phase B (sequential): the momentum identity rule (Jaccard >= 0.4 over
keywords ∪ entities vs stories seen today or yesterday; gaps reset the
carry) assigns a stable story_uid across runs and days, then everything is
written to Parquet — one row per (run, story), full unwindowed history.

Never calls LLM naming; fallback headlines are real headlines.

Usage:
    pip install pyarrow   # main venv, ad hoc — NOT a deployment dependency
    python scripts/backfill_history.py --workers 10
    python scripts/backfill_history.py --since 2026-08   # smoke subset
"""
import argparse
import gzip
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Iterable, Iterator, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from newvelles.models.momentum import _jaccard, _signature  # noqa: E402

JACCARD_THRESHOLD = 0.4
STORY_FIELDS = ("headline", "section", "kind", "outlet_count", "article_count",
                "keywords", "entities", "outlets")


def run_ts_of(path: Path) -> str:
    return path.name.rsplit("_", 1)[-1].removesuffix(".json")


def _day_delta(day: str, prev_day: str) -> int:
    return (date.fromisoformat(day) - date.fromisoformat(prev_day)).days


def _new_uid(day: str, story: dict) -> str:
    basis = f"{day}|{story.get('headline', '')}|{','.join(story.get('keywords', []))}"
    return "h_" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:10]


def build_run_cache(args: Tuple[str, str]) -> str:
    """Phase A worker: one archive file -> one compact cache file."""
    run_file, cache_file = args
    from newvelles.models.stories import build_stories  # heavy import stays in worker
    viz = json.loads(Path(run_file).read_text(encoding="utf-8"))
    doc = build_stories(viz)
    ts = run_ts_of(Path(run_file))
    compact = {
        "run_ts": ts,
        "day": ts[:10],
        "stories": [{f: s.get(f) for f in STORY_FIELDS} for s in doc["stories"]],
    }
    with gzip.open(cache_file, "wt", encoding="utf-8") as f:
        json.dump(compact, f)
    return ts


def carry_identity(
    runs_iter: Iterable[Tuple[str, str, List[dict]]],
) -> Iterator[Tuple[str, str, dict]]:
    """Assign stable story_uid across runs; yields (run_ts, day, story)."""
    prev: dict = {}  # uid -> {"sig": set, "day": str}
    for day, run_ts, stories in runs_iter:
        alive = {u: s for u, s in prev.items() if _day_delta(day, s["day"]) <= 1}
        for story in stories:
            sig = _signature(story)
            best_uid, best_score = None, 0.0
            for uid, st in alive.items():
                score = _jaccard(sig, st["sig"])
                if score > best_score:
                    best_uid, best_score = uid, score
            uid = best_uid if best_score >= JACCARD_THRESHOLD else _new_uid(day, story)
            story["story_uid"] = uid
            alive[uid] = {"sig": sig, "day": day}
            yield run_ts, day, story
        prev = alive


def iter_cached_runs(cache_dir: Path) -> Iterator[Tuple[str, str, List[dict]]]:
    for f in sorted(cache_dir.glob("*.json.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            doc = json.load(fh)
        yield doc["day"], doc["run_ts"], doc["stories"]


def write_parquet(rows: Iterator[Tuple[str, str, dict]], out: Path) -> int:
    import pyarrow as pa
    import pyarrow.parquet as pq

    cols: dict = {k: [] for k in
                  ("run_ts", "day", "story_uid", "headline", "section", "kind",
                   "outlet_count", "article_count", "keywords", "entities", "outlets")}
    for run_ts, day, s in rows:
        cols["run_ts"].append(run_ts)
        cols["day"].append(day)
        cols["story_uid"].append(s["story_uid"])
        cols["headline"].append(s.get("headline") or "")
        cols["section"].append(s.get("section") or "General")
        cols["kind"].append(s.get("kind") or "story")
        cols["outlet_count"].append(int(s.get("outlet_count") or 0))
        cols["article_count"].append(int(s.get("article_count") or 0))
        cols["keywords"].append(json.dumps(s.get("keywords") or []))
        cols["entities"].append(json.dumps(s.get("entities") or []))
        cols["outlets"].append(json.dumps(s.get("outlets") or []))
    table = pa.table(cols)
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out, compression="zstd")
    return table.num_rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive-dir", default="archive")
    ap.add_argument("--out", default="analysis/data/stories.parquet")
    ap.add_argument("--cache", default="analysis/cache/runs_v2")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--since", default="")
    ap.add_argument("--until", default="9999")
    args = ap.parse_args()

    cache_dir = Path(args.cache)
    cache_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(Path(args.archive_dir).rglob("*.json"), key=run_ts_of)
    files = [f for f in files if args.since <= run_ts_of(f) <= args.until]
    pending = [
        (str(f), str(cache_dir / (run_ts_of(f) + ".json.gz")))
        for f in files
        if not (cache_dir / (run_ts_of(f) + ".json.gz")).exists()
    ]
    print(f"phase A: {len(files)} runs in scope, {len(pending)} to process "
          f"({len(files) - len(pending)} cached)")

    done = 0
    failed: List[str] = []
    if pending:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futures = {ex.submit(build_run_cache, p): p[0] for p in pending}
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception as e:  # noqa: BLE001 - keep going, report at end
                    failed.append(f"{futures[fut]}: {e}")
                done += 1
                if done % 200 == 0:
                    print(f"  phase A: {done}/{len(pending)}")
    if failed:
        print(f"⚠️ phase A: {len(failed)} runs failed (skipped):")
        for line in failed[:10]:
            print("   " + line)

    print("phase B: identity carry + parquet write...")
    scoped = (
        (d, ts, st) for d, ts, st in iter_cached_runs(cache_dir)
        if args.since <= ts <= args.until
    )
    n = write_parquet(carry_identity(scoped), Path(args.out))
    print(f"✅ {args.out}: {n:,} rows")


if __name__ == "__main__":
    main()
