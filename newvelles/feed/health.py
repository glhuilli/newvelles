"""Per-feed fetch/parse health records emitted each run (docs/NEXT_STEPS.md §1)."""
import json
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from dateutil import parser as date_parser

from newvelles.config import config
from newvelles.utils.s3 import upload_to_s3

FEED_HEALTH_VERSION = "0.1.0"

_CONFIG = config()


def _feed_attr(feed: Any, name: str, default: Any = None) -> Any:
    try:
        value = getattr(feed, name)
    except AttributeError:
        return default
    return default if value is None else value


def _newest_entry_age_days(entries: List[Any]) -> Optional[int]:
    ages = []
    for entry in entries:
        published = _feed_attr(entry, "published")
        if not published:
            continue
        try:
            ages.append((date.today() - date_parser.parse(published).date()).days)
        except (ValueError, OverflowError, TypeError):
            continue
    return min(ages) if ages else None


def build_health_record(url: str, feed: Any, latency_ms: int) -> Dict[str, Any]:
    entries = list(_feed_attr(feed, "entries", []) or [])
    bozo_exception = _feed_attr(feed, "bozo_exception")
    record = {
        "url": url,
        "http_status": _feed_attr(feed, "status"),
        "resolved_url": _feed_attr(feed, "href"),
        "entry_count": len(entries),
        "newest_entry_age_days": _newest_entry_age_days(entries),
        "latency_ms": latency_ms,
        "bozo": bool(_feed_attr(feed, "bozo", False)),
        "error": str(bozo_exception) if bozo_exception else None,
    }
    record["ok"] = _is_ok(record)
    return record


def error_health_record(url: str, error: Exception, latency_ms: int) -> Dict[str, Any]:
    return {
        "url": url,
        "http_status": None,
        "resolved_url": None,
        "entry_count": 0,
        "newest_entry_age_days": None,
        "latency_ms": latency_ms,
        "bozo": True,
        "error": str(error),
        "ok": False,
    }


def _is_ok(record: Dict[str, Any]) -> bool:
    status = record["http_status"]
    if status is not None and status >= 400:
        return False
    return record["entry_count"] > 0


def build_health_doc(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok_count = sum(1 for r in records if r["ok"])
    return {
        "version": FEED_HEALTH_VERSION,
        "datetime": datetime.now().isoformat(timespec="seconds"),
        "feed_count": len(records),
        "ok_count": ok_count,
        "failed_count": len(records) - ok_count,
        "feeds": records,
    }


def health_summary_lines(records: List[Dict[str, Any]]) -> List[str]:
    failed = [r for r in records if not r["ok"]]
    lines = [
        f"📡 Feed health: {len(records) - len(failed)}/{len(records)} feeds ok, "
        f"{len(failed)} failed"
    ]
    if failed:
        details = ", ".join(
            f"{r['url']} (status={r['http_status']}, entries={r['entry_count']})"
            for r in failed
        )
        lines.append(f"📡 Failing feeds: {details}")
    return lines


def emit_feed_health(records: List[Dict[str, Any]]) -> None:
    """Print CloudWatch summary lines; upload the full doc when in Lambda.

    Fail-open by design: feed health must never break a news run.
    """
    try:
        for line in health_summary_lines(records):
            print(line)
        if os.getenv("AWS_LAMBDA") != "true":
            return
        doc = build_health_doc(records)
        bucket = os.getenv(
            "AWS_S3_BUCKET", _CONFIG.get("S3", "bucket", fallback="newvelles-data-bucket")
        )
        upload_to_s3(
            bucket_name=bucket,
            file_name=f"feed_health/feed_health_{doc['datetime']}.json",
            string_byte=json.dumps(doc).encode("utf-8"),
        )
    except Exception as e:  # pylint: disable=broad-except
        print(f"⚠️ Feed health emit failed (run continues): {e}")
