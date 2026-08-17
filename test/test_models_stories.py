"""Tests for newvelles.models.stories — merge, classify, assemble (schema 0.3.0)."""

import json
from pathlib import Path

import pytest

from newvelles.models.stories import collect_groups, normalize_link

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("url,expected", [
    ("https://www.BBC.co.uk/news/article-1?at_medium=RSS", "bbc.co.uk/news/article-1"),
    ("https://lifehacker.com/tech/x?utm_medium=RSS", "lifehacker.com/tech/x"),
    ("http://example.com/path/", "example.com/path"),
    ("https://example.com/", "example.com"),
])
def test_normalize_link(url, expected):
    assert normalize_link(url) == expected


def test_same_article_same_identity_despite_query_and_case():
    a = normalize_link("https://www.nytimes.com/2025/08/16/x.html?smid=rss")
    b = normalize_link("https://WWW.NYTIMES.com/2025/08/16/x.html")
    assert a == b


def _viz(entries_by_group):
    """Helper: {top_id: {sub_id: [ (title, link) ]}} -> visualization dict."""
    viz = {}
    for top, subs in entries_by_group.items():
        viz[top] = {}
        for sub, arts in subs.items():
            viz[top][sub] = {
                t: {"title": t, "link": l, "timestamp": "Sat, 16 Aug 2025 18:51:12 +0000",
                    "source": "https://feeds.bbci.co.uk/news/world/rss.xml"}
                for t, l in arts
            }
    return viz


def test_collect_groups_dedupes_within_group():
    viz = _viz({"[alaska]": {
        "[sub1]": [("A", "https://x.com/a"), ("B", "https://x.com/b")],
        "[sub2]": [("A2", "https://x.com/a?utm_medium=RSS")],   # same article, different sub-group
    }})
    groups = collect_groups(viz)
    assert len(groups) == 1
    assert set(groups[0]["articles"]) == {"x.com/a", "x.com/b"}


def test_collect_groups_keywords_from_bracket_phrases():
    viz = _viz({"[Alaska Summit] [ceasefire] [Alaska Summit]": {
        "[s]": [("A", "https://x.com/a"), ("B", "https://x.com/b")]}})
    assert collect_groups(viz)[0]["keywords"] == ["alaska summit", "ceasefire"]


def test_collect_groups_handles_old_key_names():
    viz = {"[g]": {"[s]": {"T": {
        "title": "T", "link": "https://x.com/t",
        "published": "2025-08-16T04:31:19Z",
        "title_detail_base": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    }}}}
    g = collect_groups(viz)[0]
    art = g["articles"]["x.com/t"]
    assert art["published_raw"] == "2025-08-16T04:31:19Z"
    assert art["feed"].startswith("https://rss.nytimes.com")


def test_intra_group_dedupe_on_real_example_file():
    """data/latest_news_example.json: 410 entries resolve to 121 unique links,
    all duplication is within-group across sub-groups."""
    viz = json.loads((REPO_ROOT / "data" / "latest_news_example.json").read_text())
    groups = collect_groups(viz)
    per_group_total = sum(len(g["articles"]) for g in groups)
    assert per_group_total < 410  # dedupe actually removed intra-group copies
    assert len({l for g in groups for l in g["articles"]}) == 121
