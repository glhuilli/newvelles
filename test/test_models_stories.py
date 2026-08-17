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


def _g(links):
    return {"group_id": "[g]", "keywords": [],
            "articles": {l: {"title": l, "link": l, "published_raw": "", "feed": ""} for l in links}}


def test_merge_containment_beats_jaccard():
    """A 4-article group fully contained in a 30-article group must merge
    (containment 1.0) even though Jaccard would be ~0.13."""
    from newvelles.models.stories import merge_groups
    big = _g([f"big.com/{i}" for i in range(30)])
    small = _g([f"big.com/{i}" for i in range(4)])
    assert merge_groups([big, small]) == [[0, 1]]


def test_merge_below_threshold_stays_apart():
    from newvelles.models.stories import merge_groups
    a = _g(["a.com/1", "a.com/2", "a.com/3", "shared.com/x"])
    b = _g(["b.com/1", "b.com/2", "b.com/3", "shared.com/x"])
    # overlap = 1/4 = 0.25 < 0.5
    assert merge_groups([a, b]) == [[0], [1]]


def test_merge_transitive_chain():
    """A~B and B~C merge into one component even when A and C share nothing."""
    from newvelles.models.stories import merge_groups
    a = _g(["x.com/1", "x.com/2"])
    b = _g(["x.com/1", "x.com/2", "y.com/1", "y.com/2"])
    c = _g(["y.com/1", "y.com/2"])
    assert merge_groups([a, b, c]) == [[0, 1, 2]]


def test_merge_no_overlap_is_noop():
    from newvelles.models.stories import merge_groups
    groups = [_g([f"s{i}.com/a", f"s{i}.com/b"]) for i in range(5)]
    assert merge_groups(groups) == [[i] for i in range(5)]


def test_merge_threshold_boundary_inclusive():
    from newvelles.models.stories import merge_groups
    a = _g(["s.com/1", "s.com/2", "u.com/1", "u.com/2"])
    b = _g(["s.com/1", "s.com/2", "v.com/1", "v.com/2"])
    # overlap = 2/4 = 0.5 -> edge at threshold 0.5 (>=)
    assert merge_groups([a, b], threshold=0.5) == [[0, 1]]


EARNINGS_TITLES = [
    "Select Water Solutions Q2 Earnings Call Highlights",
    "Essential Utilities Q2 Earnings Call Highlights",
    "Watts Water Technologies Q2 Earnings Call Highlights",
    "Warby Parker Q2 Earnings Call Highlights",
]

HACKS_TITLES = [
    "Five Hacks Every Amazfit Balance 3 User Should Know",
    "Five Hacks Every Amazfit Cheetah 2 Ultra User Should Know",
    "10 Screenshot Hacks Every Mac User Should Know",
]

DEAL_TITLES = [
    "This 27-Inch Asus OLED Gaming Monitor Is $120 Off Right Now",
    "This LG Ultrawide OLED Gaming Monitor Is $200 Off Right Now",
    "This 45-Inch LG UltraGear OLED Curved Monitor Is $700 Off",
]

NEWS_TITLES = [
    "Trump Bows to Putin's Approach on Ukraine: No Cease-Fire, Deadlines or Sanctions",
    "Watch: Moment Trump and Putin meet in Alaska",
    "Trump and Putin end summit without ceasefire deal for Ukraine",
]


def test_earnings_cluster_is_roundup():
    from newvelles.models.stories import classify_story
    assert classify_story(EARNINGS_TITLES, outlet_count=1) == "roundup"


def test_hacks_cluster_is_roundup():
    from newvelles.models.stories import classify_story
    assert classify_story(HACKS_TITLES, outlet_count=1) == "roundup"


def test_monitor_cluster_is_deal():
    from newvelles.models.stories import classify_story
    assert classify_story(DEAL_TITLES, outlet_count=1) == "deal"


def test_multi_outlet_news_is_story():
    from newvelles.models.stories import classify_story
    assert classify_story(NEWS_TITLES, outlet_count=3) == "story"


def test_multi_outlet_template_still_story():
    """Roundup requires single-outlet; a template across outlets is real syndication."""
    from newvelles.models.stories import classify_story
    assert classify_story(EARNINGS_TITLES, outlet_count=4) == "story"


def test_proper_noun_run_does_not_count_as_template():
    """Two outlets covering one event share a long run carrying proper nouns —
    that's a subject, not a template (sentence-case titles here)."""
    from newvelles.models.stories import classify_story
    titles = [
        "Judge orders U.S. to dispense $600M for vaccines RFK Jr. held up",
        "Court says administration must dispense $600M for vaccines RFK Jr. held up",
    ]
    assert classify_story(titles, outlet_count=1) == "story"


def test_template_run_counts_contiguous_words():
    from newvelles.models.stories import template_run
    assert template_run(EARNINGS_TITLES) >= 3     # "Q2 Earnings Call Highlights"
    assert template_run(NEWS_TITLES) < 3


def test_weekday_month_names_are_generic():
    from newvelles.models.stories import classify_story
    titles = [
        "Gold prices today, Monday, August 4",
        "Gold prices today, Tuesday, August 5",
        "Gold prices today, Wednesday, August 6",
    ]
    assert classify_story(titles, outlet_count=1) == "roundup"


def _entry(title, link, published, feed):
    return {"title": title, "link": link, "timestamp": published, "source": feed}


BBC = "https://feeds.bbci.co.uk/news/world/rss.xml"
NYT = "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"

VIZ = {
    "[alaska summit] [ceasefire]": {
        "[putin]": {
            "Trump and Putin end summit without ceasefire deal": _entry(
                "Trump and Putin end summit without ceasefire deal",
                "https://www.bbc.co.uk/news/summit-1", "Sat, 16 Aug 2025 18:51:12 +0000", BBC),
            "Watch: Moment Trump and Putin meet in Alaska": _entry(
                "Watch: Moment Trump and Putin meet in Alaska",
                "https://www.bbc.co.uk/news/summit-video", "Sat, 16 Aug 2025 12:00:00 +0000", BBC),
        },
    },
    "[alaska]": {
        "[trump putin]": {
            "Trump bows to Putin approach on Ukraine": _entry(
                "Trump bows to Putin approach on Ukraine",
                "https://www.nytimes.com/2025/08/16/summit.html", "2025-08-15T04:31:19Z", NYT),
            "Watch: Moment Trump and Putin meet in Alaska (dup)": _entry(
                "Watch: Moment Trump and Putin meet in Alaska",
                "https://www.bbc.co.uk/news/summit-video?at_medium=RSS",
                "Sat, 16 Aug 2025 12:00:00 +0000", BBC),
        },
    },
    "[quarterly results]": {
        "[earnings]": {
            "Acme Q2 Earnings Call Highlights": _entry(
                "Acme Q2 Earnings Call Highlights",
                "https://finance.yahoo.com/news/acme", "2025-08-16T04:00:00Z",
                "https://finance.yahoo.com/rss/"),
            "Globex Q2 Earnings Call Highlights": _entry(
                "Globex Q2 Earnings Call Highlights",
                "https://finance.yahoo.com/news/globex", "2025-08-14T04:00:00Z",
                "https://finance.yahoo.com/rss/"),
        },
    },
}


@pytest.fixture(scope="module")
def doc():
    from newvelles.models.stories import build_stories
    return build_stories(VIZ, generated="2025-08-16T20:00:00")


def test_top_level_fields(doc):
    assert doc["version"] == "0.3.0"
    assert doc["generated"] == "2025-08-16T20:00:00"
    assert doc["story_count"] == len(doc["stories"]) == 2
    assert doc["feeds"] == 3
    assert doc["article_count"] == 5  # dup video counted once
    assert doc["merge_threshold"] == 0.5
    assert doc["kind_counts"] == {"story": 1, "roundup": 1, "deal": 0}


def test_merged_story_shape(doc):
    story = doc["stories"][0]  # 2 outlets ranks first
    assert story["outlet_count"] == 2
    assert story["article_count"] == 3
    assert story["merged_from_groups"] == 2
    assert story["kind"] == "story"
    assert story["id"].startswith("st_") and len(story["id"]) == 9
    assert story["headline_source"] == "fallback"
    # fallback: BBC has most articles (2); its longest title:
    assert story["headline"] == "Trump and Putin end summit without ceasefire deal"
    assert story["keywords"][:2] == ["alaska summit", "ceasefire"]
    assert "alaska" in story["keywords"]
    assert story["section"] == "World"
    assert story["latest_published"] == "2025-08-16T18:51:12Z"
    assert story["first_seen"] == "2025-08-15"
    assert story["days_running"] == 2
    outlets = {o["outlet"]: o for o in story["outlets"]}
    assert outlets["BBC"]["articles"] == 2 and outlets["BBC"]["domain"] == "bbc.com"
    assert outlets["NYT"]["articles"] == 1
    # articles sorted by published desc, ISO normalized, each carries outlet metadata
    pubs = [a["published"] for a in story["articles"]]
    assert pubs == sorted(pubs, reverse=True)
    assert all(a["published"].endswith("Z") for a in story["articles"])
    assert story["articles"][0]["domain"] in {"bbc.co.uk", "bbc.com", "nytimes.com"}


def test_roundup_classified_and_ranked_below(doc):
    roundup = doc["stories"][1]
    assert roundup["kind"] == "roundup"
    assert roundup["outlet_count"] == 1


def test_stable_ids(doc):
    from newvelles.models.stories import build_stories
    doc2 = build_stories(VIZ, generated="2099-01-01T00:00:00")
    assert [s["id"] for s in doc2["stories"]] == [s["id"] for s in doc["stories"]]


def test_entities_present(doc):
    story = doc["stories"][0]
    assert isinstance(story["entities"], list)
    assert any("Putin" in e or "Trump" in e or "Alaska" in e for e in story["entities"])


def test_build_stories_on_real_example_file():
    from newvelles.models.stories import build_stories
    viz = json.loads((REPO_ROOT / "data" / "latest_news_example.json").read_text())
    result = build_stories(viz)
    assert result["story_count"] == len(result["stories"]) > 0
    links = [a["link"] for s in result["stories"] for a in s["articles"]]
    # flattening removed the massive intra-group duplication
    assert len(links) == result["article_count"]
    for s in result["stories"]:
        assert s["kind"] in {"story", "roundup", "deal"}
        assert s["outlet_count"] >= 1
        assert s["outlet_count"] == len({a["outlet"] for a in s["articles"]})


def test_intra_group_dedupe_on_real_example_file():
    """data/latest_news_example.json: 410 entries resolve to 121 unique links,
    all duplication is within-group across sub-groups."""
    viz = json.loads((REPO_ROOT / "data" / "latest_news_example.json").read_text())
    groups = collect_groups(viz)
    per_group_total = sum(len(g["articles"]) for g in groups)
    assert per_group_total < 410  # dedupe actually removed intra-group copies
    assert len({l for g in groups for l in g["articles"]}) == 121
