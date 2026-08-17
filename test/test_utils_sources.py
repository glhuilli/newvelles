"""Tests for newvelles.utils.sources — feed URL resolution to outlet/domain/section."""

import json
from pathlib import Path

from newvelles.utils.sources import SourceInfo, is_mapped, resolve_feed

REPO_ROOT = Path(__file__).resolve().parents[1]


def _feeds(fname):
    return [line.strip() for line in (REPO_ROOT / "data" / fname).read_text().splitlines() if line.strip()]


def test_every_production_feed_is_mapped():
    unmapped = [f for f in _feeds("rss_source.txt") if not is_mapped(f)]
    assert unmapped == [], f"Unmapped production feeds: {unmapped}"


def test_every_qa_feed_is_mapped():
    unmapped = [f for f in _feeds("rss_qa_reliable.txt") if not is_mapped(f)]
    assert unmapped == [], f"Unmapped QA feeds: {unmapped}"


def test_known_resolutions():
    r = resolve_feed("https://feeds.bbci.co.uk/news/world/rss.xml")
    assert r.outlet == "BBC" and r.domain == "bbc.com" and r.section == "World"
    r = resolve_feed("https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml")
    assert r.outlet == "NYT" and r.domain == "nytimes.com" and r.section == "Tech"


def test_self_reported_feed_variants_resolve():
    """Feeds sometimes self-report a base URL that differs from the source list —
    these variants were observed in real production archives."""
    r = resolve_feed("https://abcnews.com/abcnews/internationalheadlines")
    assert r.outlet == "ABC News" and r.section == "World"
    r = resolve_feed("https://www.westword.com/feed/")
    assert r.outlet == "Westword" and r.section == "Local"
    r = resolve_feed("https://www.newsweek.com")
    assert r.outlet == "Newsweek"


def test_unmapped_feed_falls_back_to_registered_domain():
    r = resolve_feed("https://blog.example.co.uk/feed.xml")
    assert isinstance(r, SourceInfo)
    assert r.domain == "example.co.uk"
    assert r.section == "General"
    assert r.outlet  # non-empty


def test_sections_are_valid_vocabulary():
    table = json.loads((REPO_ROOT / "data" / "sources.json").read_text())
    allowed = {"World", "US politics", "Markets", "Tech", "Science", "Local", "General"}
    bad = {url: v["section"] for url, v in table.items() if v["section"] not in allowed}
    assert bad == {}
