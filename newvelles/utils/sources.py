"""Resolve RSS feed URLs to outlet name, registered domain and section."""
import json
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

_SOURCES_PATH = Path(__file__).resolve().parents[2] / "data" / "sources.json"


class SourceInfo(NamedTuple):
    outlet: str
    domain: str
    section: str


def _load_table() -> dict:
    try:
        return json.loads(_SOURCES_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


_TABLE = _load_table()
_REPORTED_UNMAPPED: set = set()

# two-label public suffixes we actually encounter in the feed list
_TWO_LABEL_SUFFIXES = {"co.uk", "com.au", "co.jp"}


def registered_domain(host: str) -> str:
    parts = host.lower().lstrip(".").split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in _TWO_LABEL_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def is_mapped(feed_url: str) -> bool:
    return feed_url.strip() in _TABLE


def resolve_feed(feed_url: str) -> SourceInfo:
    feed_url = feed_url.strip()
    entry = _TABLE.get(feed_url)
    if entry:
        return SourceInfo(entry["outlet"], entry["domain"], entry["section"])
    host = urlsplit(feed_url).netloc or feed_url
    domain = registered_domain(host.split(":")[0].removeprefix("www."))
    if feed_url not in _REPORTED_UNMAPPED:
        _REPORTED_UNMAPPED.add(feed_url)
        print(f"⚠️ Unmapped RSS feed (add to data/sources.json): {feed_url}")
    outlet = domain.split(".")[0].capitalize()
    return SourceInfo(outlet, domain, "General")
