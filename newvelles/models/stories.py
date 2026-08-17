"""Merge visualization groups into stories (schema 0.3.0). Stage A + A.5."""
import hashlib
import re
from collections import Counter
from datetime import datetime
from urllib.parse import urlsplit

from newvelles.utils.dates import iso_date, to_iso8601
from newvelles.utils.sources import resolve_feed

STORIES_VERSION = "0.3.0"
MERGE_THRESHOLD = 0.5

_BRACKET_RE = re.compile(r"\[([^\]]+)\]")


def normalize_link(url: str) -> str:
    """Article identity: lowercase host, no www., no trailing slash, no query/fragment."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/")
    return f"{host}{path}"


def _article_from_entry(entry: dict) -> dict:
    return {
        "title": entry.get("title", ""),
        "link": entry.get("link", ""),
        "published_raw": entry.get("timestamp") or entry.get("published", ""),
        "feed": entry.get("source") or entry.get("title_detail_base", ""),
    }


def _keywords_from_group_id(group_id: str) -> list:
    seen, out = set(), []
    for phrase in _BRACKET_RE.findall(group_id):
        keyword = phrase.strip().lower()
        if keyword and keyword not in seen:
            seen.add(keyword)
            out.append(keyword)
    return out


def collect_groups(visualization: dict) -> list:
    """Flatten each top-level group to unique articles keyed by normalized link.

    Collapses the intra-group duplication where one article appears in many
    sub-groups of the same parent.
    """
    groups = []
    for top_id, sub_groups in visualization.items():
        articles = {}
        for entries in sub_groups.values():
            for entry in entries.values():
                article = _article_from_entry(entry)
                key = normalize_link(article["link"])
                if key and key not in articles:
                    articles[key] = article
        if articles:
            groups.append({
                "group_id": top_id,
                "articles": articles,
                "keywords": _keywords_from_group_id(top_id),
            })
    return groups


def _find(parent, i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def _union(parent, a, b):
    root_a, root_b = _find(parent, a), _find(parent, b)
    if root_a != root_b:
        parent[max(root_a, root_b)] = min(root_a, root_b)


def merge_groups(groups: list, threshold: float = MERGE_THRESHOLD) -> list:
    """Connected components over groups, edge when link containment >= threshold.

    Containment (min in the denominator) rather than Jaccard: a small group
    fully contained in a large one must merge.
    """
    link_sets = [set(g["articles"]) for g in groups]
    parent = list(range(len(groups)))
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            smaller = min(len(link_sets[i]), len(link_sets[j]))
            if smaller == 0:
                continue
            if len(link_sets[i] & link_sets[j]) / smaller >= threshold:
                _union(parent, i, j)
    components: dict = {}
    for i in range(len(groups)):
        components.setdefault(_find(parent, i), []).append(i)
    return [components[root] for root in sorted(components)]


DEAL_RE = re.compile(
    r"(\$\s?\d[\d,]*(\.\d+)?\s*off|\d+\s?%\s*off|\bpre-?order\b|\bdeals?\b|\bdiscount\b|\bcoupon\b)",
    re.IGNORECASE,
)
TEMPLATE_MIN_RUN = 3
TEMPLATE_SHARE = 0.6
_GENERIC_CAPITALIZED = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
}
_WORD_RE = re.compile(r"[A-Za-z0-9$%'’.-]+")


def _words(title: str) -> list:
    return _WORD_RE.findall(title)


def _is_title_case(words: list) -> bool:
    significant = [w for w in words if len(w) > 3 and w[0].isalpha()]
    if not significant:
        return False
    capitalized = [w for w in significant if w[0].isupper()]
    return len(capitalized) / len(significant) >= 0.7


def _proper_nouns(titles: list) -> set:
    """Proper nouns collected only from sentence-case titles — capitalization is
    meaningless in title-case headlines, and weekday/month names are generic."""
    nouns = set()
    for title in titles:
        words = _words(title)
        if _is_title_case(words):
            continue
        for word in words[1:]:  # skip sentence-initial capital
            if word[0].isalpha() and word[0].isupper():
                clean = word.lower().strip(".'’")
                if clean not in _GENERIC_CAPITALIZED:
                    nouns.add(clean)
    return nouns


def _contains_run(words: list, run: tuple) -> bool:
    n = len(run)
    return any(tuple(words[k:k + n]) == run for k in range(len(words) - n + 1))


def template_run(titles: list) -> int:
    """Longest contiguous word run shared by >= 60% of titles, excluding runs
    that contain a proper noun.

    Only *maximal* shared runs are considered: a proper-noun-free sub-run
    inside a longer shared run that carries a proper noun is part of a
    subject ("dispense $600M for vaccines RFK Jr. held up"), not a template.
    """
    if len(titles) < 2:
        return 0
    proper = _proper_nouns(titles)
    lowered = [[w.lower() for w in _words(t)] for t in titles]
    need = max(2, -(-len(titles) * 6 // 10))  # ceil(0.6 * n), at least 2

    shared = set()
    for words in lowered:
        for i in range(len(words)):
            for j in range(i + TEMPLATE_MIN_RUN, len(words) + 1):
                run = tuple(words[i:j])
                if run in shared:
                    continue
                count = sum(1 for other in lowered if _contains_run(other, run))
                if count >= need:
                    shared.add(run)

    best = 0
    for run in shared:
        is_maximal = not any(
            other != run and _contains_run(list(other), run) for other in shared
        )
        if not is_maximal:
            continue
        if any(w.strip(".'’") in proper for w in run):
            continue
        best = max(best, len(run))
    return best


def classify_story(titles: list, outlet_count: int) -> str:
    """kind classification: deal | roundup | story. Classification, not
    filtering — nothing is discarded downstream."""
    deal_matches = sum(1 for t in titles if DEAL_RE.search(t))
    if titles and deal_matches / len(titles) > 0.5:
        return "deal"
    if outlet_count == 1 and template_run(titles) >= TEMPLATE_MIN_RUN:
        return "roundup"
    return "story"


_ENTITY_LABELS = {"PERSON", "ORG", "GPE", "LOC", "NORP", "FAC", "EVENT"}
MAX_KEYWORDS = 8
MAX_ENTITIES = 10


def _story_id(links: list) -> str:
    fingerprint = hashlib.sha256(",".join(sorted(links)[:20]).encode("utf-8")).hexdigest()
    return f"st_{fingerprint[:6]}"


def _fallback_headline(articles: list) -> str:
    by_outlet = Counter(a["outlet"] for a in articles)
    top_outlet = by_outlet.most_common(1)[0][0]
    candidates = [a["title"] for a in articles if a["outlet"] == top_outlet]
    return max(candidates, key=len)


def _extract_entities(titles: list) -> list:
    from newvelles.utils.text import NLP  # module-level spaCy model, already loaded
    counts: Counter = Counter()
    for title in titles:
        for ent in NLP(title).ents:
            if ent.label_ in _ENTITY_LABELS:
                counts[ent.text] += 1
    return [entity for entity, _ in counts.most_common(MAX_ENTITIES)]


def build_stories(visualization: dict, generated: str = None) -> dict:
    """Assemble the stories.json document from a visualization dict."""
    groups = collect_groups(visualization)
    components = merge_groups(groups)

    stories = []
    all_links: set = set()
    all_feeds: set = set()
    for component in components:
        articles_by_link: dict = {}
        keywords, seen_keywords = [], set()
        for idx in component:
            for link, article in groups[idx]["articles"].items():
                articles_by_link.setdefault(link, article)
            for keyword in groups[idx]["keywords"]:
                if keyword not in seen_keywords:
                    seen_keywords.add(keyword)
                    keywords.append(keyword)

        articles = []
        for link, article in articles_by_link.items():
            source = resolve_feed(article["feed"])
            articles.append({
                "title": article["title"],
                "link": article["link"],
                "published": to_iso8601(article["published_raw"]),
                "outlet": source.outlet,
                "domain": source.domain,
                "section": source.section,
                "feed": article["feed"],
            })
            all_feeds.add(article["feed"])
        all_links.update(articles_by_link)
        articles.sort(key=lambda a: a["published"], reverse=True)

        titles = [a["title"] for a in articles]
        outlet_counter = Counter(a["outlet"] for a in articles)
        outlet_domains = {a["outlet"]: a["domain"] for a in articles}
        sections = Counter(a["section"] for a in articles)
        publish_dates = {iso_date(a["published"]) for a in articles} - {""}
        parseable = [a["published"] for a in articles if a["published"].endswith("Z")]

        stories.append({
            "id": _story_id(list(articles_by_link)),
            "headline": _fallback_headline(articles),
            "headline_source": "fallback",
            "keywords": keywords[:MAX_KEYWORDS],
            "entities": _extract_entities(titles),
            "section": sections.most_common(1)[0][0],
            "kind": classify_story(titles, outlet_count=len(outlet_counter)),
            "outlet_count": len(outlet_counter),
            "article_count": len(articles),
            "latest_published": max(parseable) if parseable else "",
            "first_seen": min(publish_dates) if publish_dates else "",
            "days_running": max(len(publish_dates), 1),
            "merged_from_groups": len(component),
            "outlets": [
                {"outlet": outlet, "domain": outlet_domains[outlet], "articles": count}
                for outlet, count in outlet_counter.most_common()
            ],
            "articles": articles,
        })

    stories.sort(
        key=lambda s: (s["outlet_count"], s["article_count"], s["latest_published"]),
        reverse=True,
    )
    kind_counts = Counter(s["kind"] for s in stories)
    return {
        "version": STORIES_VERSION,
        "generated": generated or datetime.now().isoformat().split(".")[0],
        "feeds": len(all_feeds),
        "article_count": len(all_links),
        "story_count": len(stories),
        "merge_threshold": MERGE_THRESHOLD,
        "kind_counts": {k: kind_counts.get(k, 0) for k in ("story", "roundup", "deal")},
        "stories": stories,
    }
