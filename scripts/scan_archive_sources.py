#!/usr/bin/env python
"""Report archive feed URLs missing from data/sources.json.

IO-only pass over the local archive mirror (see scripts/pull_archive.py):
collects every article's `source` feed URL, counts articles per URL, and
prints unmapped URLs grouped by registered domain. Run before the historical
backfill so early-era articles resolve to real outlets/sections instead of
the domain fallback.

Usage:
    python scripts/scan_archive_sources.py [--archive-dir archive] [--min-articles 1000]
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from newvelles.utils.sources import is_mapped, registered_domain  # noqa: E402
from urllib.parse import urlsplit  # noqa: E402


def iter_articles(run_file: Path):
    try:
        viz = json.loads(run_file.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return
    for subs in viz.values():
        if not isinstance(subs, dict):
            continue
        for arts in subs.values():
            if not isinstance(arts, dict):
                continue
            for art in arts.values():
                src = art.get("source") if isinstance(art, dict) else None
                if src:
                    yield src


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive-dir", default="archive")
    ap.add_argument("--min-articles", type=int, default=1000)
    args = ap.parse_args()

    counts: Counter = Counter()
    files = sorted(Path(args.archive_dir).rglob("*.json"))
    for i, f in enumerate(files):
        for src in iter_articles(f):
            counts[src.strip()] += 1
        if (i + 1) % 1000 == 0:
            print(f"  scanned {i + 1}/{len(files)} runs...", file=sys.stderr)

    total = sum(counts.values())
    unmapped = {u: c for u, c in counts.items() if not is_mapped(u)}
    unmapped_total = sum(unmapped.values())
    by_domain: dict = defaultdict(Counter)
    for u, c in unmapped.items():
        host = urlsplit(u).netloc or u
        by_domain[registered_domain(host.removeprefix("www."))][u] += c

    print(f"\n{len(files)} runs · {total:,} article occurrences · "
          f"{len(counts)} distinct feed URLs")
    print(f"unmapped: {len(unmapped)} URLs · {unmapped_total:,} occurrences "
          f"({100 * unmapped_total / max(total, 1):.2f}%)\n")
    for domain, urls in sorted(by_domain.items(), key=lambda kv: -sum(kv[1].values())):
        dtotal = sum(urls.values())
        if dtotal < args.min_articles:
            continue
        print(f"{domain}  ({dtotal:,} occurrences)")
        for u, c in urls.most_common(6):
            print(f"    {c:>9,}  {u}")


if __name__ == "__main__":
    main()
