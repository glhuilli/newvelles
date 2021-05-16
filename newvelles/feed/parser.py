from typing import Any, Iterable, List, Tuple

import feedparser

from newvelles.config import debug

DEBUG = debug()


def parse_feed(feed_paths: List[str]) -> Iterable[Tuple[str, Any]]:  # pragma: no cover
    """
    Use the feedparser package to load data from a particular RSS feed path
    """
    for feed_path in feed_paths:
        feed = feedparser.parse(feed_path)
        feed_title = feed['feed']['title']
        if DEBUG:
            print(f'{feed_title} entries: {len(feed.entries)}')
        for entry in feed.entries:
            yield (feed_title, entry)
