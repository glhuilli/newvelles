"""Normalize the several RSS date formats to ISO 8601 UTC."""
import re
from datetime import datetime, timezone
from email.utils import mktime_tz, parsedate_tz

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")


def to_iso8601(raw: str) -> str:
    """Return raw normalized to YYYY-MM-DDTHH:MM:SSZ (UTC), or raw unchanged if unparseable."""
    dt = _parse(raw)
    if dt is None:
        return raw
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_date(raw: str) -> str:
    """Return the UTC date part (YYYY-MM-DD), or empty string if unparseable."""
    dt = _parse(raw)
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _parse(raw: str):
    if not raw:
        return None
    if _ISO_RE.match(raw):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    # RFC 2822 with numeric offsets or named zones (EST/GMT/...) — parsedate_tz
    # understands the obsolete US zone names that RSS feeds still emit.
    parsed = parsedate_tz(raw)
    if parsed is None:
        return None
    if parsed[9] is None:
        parsed = parsed[:9] + (0,)
    try:
        return datetime.fromtimestamp(mktime_tz(parsed), timezone.utc)
    except (ValueError, OverflowError):
        return None
