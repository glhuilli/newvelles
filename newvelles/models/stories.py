"""Merge visualization groups into stories (schema 0.3.0). Stage A + A.5."""
import re
from urllib.parse import urlsplit

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
