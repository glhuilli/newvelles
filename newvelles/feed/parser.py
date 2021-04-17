from typing import Iterable, List, Tuple

import feedparser


def parse_feed(feed_paths: List[str]) -> Iterable[Tuple[str, str]]:  # pragma: no cover
    for feed_path in feed_paths:
        feed = feedparser.parse(feed_path)
        feed_title = feed['feed']['title']
        for entry in feed.entries:
            yield (feed_title, entry.title)
