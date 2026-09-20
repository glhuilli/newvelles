"""Publish one analysis entry (index.json + payload.json) to the public bucket.

Usage: python scripts/publish_analysis.py --entry five-years [--bucket public-newvelles-data-bucket] [--dry-run]

Never runs inside the Lambda. Validates the index against the schema first.
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "analysis" / "entries"
SCHEMA = ROOT / "schemas" / "analysis_index_schema.json"
DEFAULT_BUCKET = "public-newvelles-data-bucket"


def gzip_bytes(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=9, mtime=0)


def put_args(key: str, body: bytes, cache_seconds: int) -> dict:
    return {
        "Key": key,
        "Body": body,
        "ContentType": "application/json",
        "ContentEncoding": "gzip",
        "CacheControl": f"public, max-age={cache_seconds}",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry", required=True)
    ap.add_argument("--bucket", default=DEFAULT_BUCKET)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    index_path = ENTRIES / "index.json"
    payload_path = ENTRIES / args.entry / "payload.json"
    if not payload_path.exists():
        print(f"missing {payload_path}; run build_payload.py --entry {args.entry}", file=sys.stderr)
        return 2
    index = json.loads(index_path.read_text(encoding="utf-8"))
    jsonschema.validate(index, json.loads(SCHEMA.read_text(encoding="utf-8")))
    if args.entry not in {e["id"] for e in index["entries"]}:
        print(f"entry {args.entry} is not in index.json", file=sys.stderr)
        return 2

    uploads = [
        put_args("analysis/index.json", gzip_bytes(index_path.read_bytes()), 300),
        put_args(f"analysis/entries/{args.entry}/payload.json", gzip_bytes(payload_path.read_bytes()), 86400),
    ]
    for u in uploads:
        print(f"{'DRY ' if args.dry_run else ''}put s3://{args.bucket}/{u['Key']} ({len(u['Body']) / 1024:.0f} KB gzip)")
    if args.dry_run:
        return 0
    import boto3  # imported here so tests never need AWS

    s3 = boto3.client("s3")
    for u in uploads:
        s3.put_object(Bucket=args.bucket, **u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
