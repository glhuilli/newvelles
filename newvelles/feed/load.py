import logging
from collections import defaultdict
from datetime import date
from typing import Any, Dict, Iterable, List

from dateutil import parser as date_parser

from newvelles.feed import NewsEntry
from newvelles.feed.log import log_entries
from newvelles.feed.parser import parse_feed

_DATE_RANGE_DAYS = 14


def load_rss(rss_file_path) -> Iterable[str]:  # pragma: no cover
    """
    Given a file, yield all RSS links

    TODO: check edge cases and exclude links that don't validate accepted RSS link format
    """
    with open(rss_file_path, "r", encoding="utf-8") as f:
        for line in f.readlines():
            yield line.strip()


def build_data_from_rss_feeds_list(rss_list: List[str], log: bool = True) -> Dict[str, NewsEntry]:
    title_data = {}
    news_data: Dict[str, Any] = defaultdict(list)
    for feed_title, entry in parse_feed(rss_list):
        try:
            # Validate required entry fields
            if not _has_required_fields(entry):
                continue

            if _within_date_range(entry):
                # Safe access to title_detail.base with fallback
                title_detail_base = _get_title_detail_base(entry)

                news_entry = NewsEntry(
                    title=entry.title,
                    link=entry.link,
                    published=entry.published,
                    title_detail_base=title_detail_base,
                )
                title_data[entry.title] = news_entry
                news_data[feed_title].append(entry)
        except Exception as e:
            # Log the specific error for debugging but continue processing
            logger = logging.getLogger(__name__)
            logger.debug(f"Skipping entry due to error: {e}")
            continue
    if log:
        log_entries(title_data, news_data)
    return title_data


def build_data_from_rss_feeds(rss_file: str) -> Dict[str, NewsEntry]:
    """
    Builds from RSS feeds, which is basically {title: link} for now.

    TODO: consider using much richer metadata object to expand UX (e.g., images).
    """
    feeds = list(load_rss(rss_file))
    return build_data_from_rss_feeds_list(feeds)


def _has_required_fields(entry) -> bool:
    """
    Check if entry has all required fields for NewsEntry
    """
    required_attrs = ["title", "link", "published"]
    return all(hasattr(entry, attr) and getattr(entry, attr) for attr in required_attrs)


def _get_title_detail_base(entry) -> str:
    """
    Safely extract title_detail.base with fallbacks
    """
    try:
        if hasattr(entry, "title_detail") and hasattr(entry.title_detail, "base"):
            return entry.title_detail.base
        if hasattr(entry, "link"):
            return entry.link
        return "unknown"
    except Exception:
        return "unknown"


def _within_date_range(entry) -> bool:
    """
    Check if entry is within the acceptable date range
    """
    try:
        entry_date = date_parser.parse(entry.published).date()
        current_date = date.today()
        delta = current_date - entry_date
        return delta.days < _DATE_RANGE_DAYS
    except Exception:
        # If we can't parse the date, assume it's recent
        return True
