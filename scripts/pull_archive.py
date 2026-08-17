#!/usr/bin/env python
"""Mirror the full visualization archive locally for historical analysis.

Downloads every archived run (newvelles_visualization_0.2.1_*, July 2021 ->
present; ~9,300 objects, ~1.8 GB) from the private bucket into
archive/YYYY/<key>. Resumable: existing files with matching size are skipped,
so re-running only fetches what's missing.

Usage:
    python scripts/pull_archive.py                 # everything
    python scripts/pull_archive.py --since 2024-01 # subset by date prefix
    make pull-archive

This is step one of the historical-analysis workstream (see
docs/NEXT_STEPS.md): the local mirror feeds a backfill that replays the
archive through build_stories + the momentum identity matcher into an
analysis-ready Parquet dataset.
"""
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3

BUCKET = "newvelles-data-bucket"
PREFIX = "newvelles_visualization_0.2.1_"
DEFAULT_TARGET = Path("archive")
CONCURRENCY = 16


def list_archive(s3_client, since: str) -> list:
    objects = []
    for page in s3_client.get_paginator("list_objects_v2").paginate(
        Bucket=BUCKET, Prefix=PREFIX
    ):
        for obj in page.get("Contents", []):
            stamp = obj["Key"].rsplit("_", 1)[-1]  # 2026-08-17T01:00:44.json
            if stamp >= since:
                objects.append((obj["Key"], obj["Size"], stamp[:4]))
    return objects


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET,
                        help="local directory (default: ./archive)")
    parser.add_argument("--since", default="2021",
                        help="only keys with timestamp >= this prefix (e.g. 2024-01)")
    args = parser.parse_args()

    s3_client = boto3.client("s3")
    objects = list_archive(s3_client, args.since)
    total_gb = sum(size for _, size, _ in objects) / 1e9
    print(f"archive: {len(objects)} runs, {total_gb:.2f} GB (since {args.since})")

    pending = []
    for key, size, year in objects:
        path = args.target / year / key
        if path.exists() and path.stat().st_size == size:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        pending.append((key, path))
    print(f"already local: {len(objects) - len(pending)} | to download: {len(pending)}")
    if not pending:
        print("nothing to do")
        return

    def fetch(item):
        key, path = item
        s3_client.download_file(BUCKET, key, str(path))
        return key

    done = 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [pool.submit(fetch, item) for item in pending]
        for future in as_completed(futures):
            future.result()  # surface any download error
            done += 1
            if done % 250 == 0 or done == len(pending):
                print(f"  {done}/{len(pending)} downloaded")

    print(f"✅ archive mirrored to {args.target}/ "
          f"({len(objects)} runs, {total_gb:.2f} GB)")
    sys.exit(0)


if __name__ == "__main__":
    main()
