from typing import Any, Iterable, List, Tuple

import feedparser


def parse_feed(feed_paths: List[str]) -> Iterable[Tuple[str, Any]]:  # pragma: no cover
    for feed_path in feed_paths:
        feed = feedparser.parse(feed_path)
        feed_title = feed['feed']['title']
        print(f'{feed_title} entries: {len(feed.entries)}')
        for entry in feed.entries:
            yield (feed_title, entry)
