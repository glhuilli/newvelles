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
