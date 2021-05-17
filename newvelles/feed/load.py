from collections import defaultdict
from typing import Any, Dict, List

from newvelles.feed.log import log_entries
from newvelles.feed.parser import parse_feed
from newvelles.feed import NewsEntry


def load_rss(rss_file_path) -> List[str]:  # pragma: no cover
    """
    Given a file, yield all RSS links

    TODO: check edge cases and exclude links that don't validate accepted RSS link format
    """
    with open(rss_file_path, 'r') as f:
        for line in f.readlines():
            yield line.strip()


def build_data_from_rss_feeds(rss_file: str) -> Dict[str, NewsEntry]:
    """
    Builds from RSS feeds, which is basically {title: link} for now.

    TODO: consider using much richer metadata object to expand UX (e.g., images).
    """
    feeds = load_rss(rss_file)
    title_data = {}
    news_data: Dict[str, Any] = defaultdict(list)
    for feed_title, entry in parse_feed(feeds):
        try:
            news_entry = NewsEntry(
                title=entry.title,
                link=entry.link,
                published=entry.published,
                title_detail_base=entry.title_detail.base,
            )
            title_data[entry.title] = news_entry
            news_data[feed_title].append(entry)
        except Exception:
            continue
    log_entries(news_data)
    return title_data
