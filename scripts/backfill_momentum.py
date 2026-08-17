#!/usr/bin/env python
"""Seed momentum_state.json and momentum.json from archived production runs.

Replays the last WINDOW_DAYS days of archived visualization runs through the
same build_stories -> apply_momentum pipeline the Lambda uses, then uploads
the seeded state (private bucket) and rollup (public bucket). Without this,
every story reads "new today" for the first fortnight and the sparkline
column is empty at launch.

Usage:
    python scripts/backfill_momentum.py --env qa --dry-run
    python scripts/backfill_momentum.py --env qa
    python scripts/backfill_momentum.py --env prod

The source archive is always the production private bucket (the QA Lambda
runs rarely, so its archive cannot seed a realistic window); --env selects
the destination buckets only.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from newvelles.models.momentum import WINDOW_DAYS, apply_momentum  # noqa: E402
from newvelles.models.stories import build_stories  # noqa: E402
from newvelles.utils.s3 import upload_to_s3  # noqa: E402

SOURCE_ARCHIVE_BUCKET = "newvelles-data-bucket"
ARCHIVE_PREFIX = "newvelles_visualization_0.2.1_"
DESTINATIONS = {
    "qa": ("newvelles-qa-bucket", "public-newvelles-qa-bucket"),
    "prod": ("newvelles-data-bucket", "public-newvelles-data-bucket"),
}
_STAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})")


def list_window_runs(s3_client) -> list:
    """Archive keys for the last WINDOW_DAYS distinct dates, oldest first,
    one run per minute-stamp (retries produce near-duplicate objects)."""
    keys = []
    for page in s3_client.get_paginator("list_objects_v2").paginate(
        Bucket=SOURCE_ARCHIVE_BUCKET, Prefix=ARCHIVE_PREFIX
    ):
        keys.extend(o["Key"] for o in page.get("Contents", []))
    keys.sort()

    dated = []
    seen_minutes = set()
    for key in keys:
        match = _STAMP_RE.search(key)
        if not match:
            continue
        minute = match.group(1) + match.group(2)
        if minute in seen_minutes:
            continue
        seen_minutes.add(minute)
        dated.append((match.group(1), key))

    dates = sorted({d for d, _ in dated})[-WINDOW_DAYS:]
    return [(d, k) for d, k in dated if d in dates]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", choices=sorted(DESTINATIONS), required=True)
    parser.add_argument("--dry-run", action="store_true",
                        help="write momentum.json/momentum_state.json locally instead of S3")
    args = parser.parse_args()

    s3_client = boto3.client("s3")
    runs = list_window_runs(s3_client)
    print(f"Replaying {len(runs)} archived runs across "
          f"{len({d for d, _ in runs})} days from s3://{SOURCE_ARCHIVE_BUCKET}/")

    state = None
    momentum_doc = None
    for run_date, key in runs:
        body = s3_client.get_object(Bucket=SOURCE_ARCHIVE_BUCKET, Key=key)["Body"].read()
        stories_data = build_stories(json.loads(body))
        stories_data, momentum_doc, state = apply_momentum(stories_data, state, today=run_date)
        carried = sum(1 for s in stories_data["stories"] if s.get("days_running", 1) > 1)
        print(f"  {key[-25:-5]}: {stories_data['story_count']} stories, {carried} carried ids")

    if momentum_doc is None:
        print("No archived runs found in the window — nothing to seed.")
        sys.exit(1)

    multi_day = sum(1 for v in momentum_doc["stories"].values() if v["days_running"] > 1)
    print(f"\nSeeded window {momentum_doc['window_start']} → {momentum_doc['window_end']}: "
          f"{len(momentum_doc['stories'])} live stories, {multi_day} spanning multiple days, "
          f"{len(state['stories'])} in state")

    if args.dry_run:
        Path("momentum_backfill.json").write_text(json.dumps(momentum_doc, indent=1))
        Path("momentum_state_backfill.json").write_text(json.dumps(state, indent=1))
        print("Dry run: wrote momentum_backfill.json + momentum_state_backfill.json locally")
        return

    private_bucket, public_bucket = DESTINATIONS[args.env]
    upload_to_s3(bucket_name=private_bucket, file_name="momentum_state.json",
                 string_byte=json.dumps(state).encode("utf-8"))
    upload_to_s3(bucket_name=public_bucket, file_name="momentum.json",
                 string_byte=json.dumps(momentum_doc).encode("utf-8"), public_read=True)
    print(f"Uploaded momentum_state.json -> s3://{private_bucket}/ "
          f"and momentum.json -> s3://{public_bucket}/")


if __name__ == "__main__":
    main()
