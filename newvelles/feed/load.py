from collections import defaultdict
from typing import Any, Dict, List

from newvelles.feed.log import log_entries
from newvelles.feed.parser import parse_feed


def load_rss(rss_file_path) -> List[str]:  # pragma: no cover
    """
    Given a file, yield all RSS links

    TODO: check edge cases and exclude links that don't validate accepted RSS link format
    """
    with open(rss_file_path, 'r') as f:
        for line in f.readlines():
            yield line.strip()


def build_data_from_rss_feeds(rss_file: str) -> Dict[str, str]:
    """
    Builds from RSS feeds, which is basically {title: link} for now.

    TODO: consider using much richer metadata object to expand UX (e.g., images).
    """
    feeds = load_rss(rss_file)
    title_data = {}
    news_data: Dict[str, Any] = defaultdict(list)
    for feed_title, entry in parse_feed(feeds):
        title_data[entry.title] = entry.link
        news_data[feed_title].append(entry)
    log_entries(news_data)
    return title_data
