import logging
from typing import Any, Iterable, List, Tuple
from urllib.parse import urlparse

import feedparser

from newvelles.config import debug

DEBUG = debug()
logger = logging.getLogger(__name__)


def parse_feed(feed_paths: List[str]) -> Iterable[Tuple[str, Any]]:  # pragma: no cover
    """
    Use the feedparser package to load data from a particular RSS feed path
    """
    for feed_path in feed_paths:
        try:
            feed = feedparser.parse(feed_path)

            # Handle missing or malformed feed title with fallbacks
            feed_title = _get_feed_title(feed, feed_path)

            # Skip feeds that have no entries or failed to parse
            if not hasattr(feed, "entries") or len(feed.entries) == 0:
                logger.warning(f"No entries found for feed: {feed_path}")
                continue

            if DEBUG:
                print(f"{feed_title} entries: {len(feed.entries)}")

            for entry in feed.entries:
                # Skip entries that don't have required fields
                if not hasattr(entry, "title") or not hasattr(entry, "link"):
                    continue
                yield (feed_title, entry)

        except Exception as e:
            logger.exception(f"Feed path is raising exceptions: {feed_path}\nException: {str(e)}")


def _get_feed_title(feed, feed_path: str) -> str:
    """
    Extract feed title with multiple fallback strategies
    """
    try:
        # Try standard feed.feed.title
        if hasattr(feed, "feed") and hasattr(feed.feed, "title"):
            return feed.feed.title

        # Try feed["feed"]["title"] access
        if "feed" in feed and "title" in feed["feed"]:
            return feed["feed"]["title"]

        # Try alternative title locations
        if hasattr(feed, "feed"):
            # Try other common title fields
            for title_field in ["subtitle", "description", "link"]:
                if hasattr(feed.feed, title_field):
                    title_value = getattr(feed.feed, title_field)
                    if title_value:
                        return f"Feed ({title_field}: {title_value})"

        # Last resort: use the URL as title
        if feed_path:
            # Extract domain from URL for a cleaner title
            parsed_url = urlparse(feed_path)
            domain = parsed_url.netloc or feed_path
            return f"Feed ({domain})"

    except Exception as e:
        logger.warning(f"Could not extract title for feed {feed_path}: {e}")

    # Final fallback
    return f"Unknown Feed ({feed_path})"
