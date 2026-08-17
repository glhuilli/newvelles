"""Pre-publish sanity gate for stories.json.

Schema validation passes happily on a run that produced three stories or four
hundred; both are bugs, not news days. The gate refuses to publish when the
story count deviates more than NEWVELLES_GATE_MAX_DEVIATION from the previous
published run, or when the article count falls below
NEWVELLES_GATE_MIN_ARTICLES — leaving the previously published file in place.
"""
import os
from typing import Optional, Tuple

DEFAULT_MAX_DEVIATION = 0.6
DEFAULT_MIN_ARTICLES = 50


def _max_deviation() -> float:
    return float(os.environ.get("NEWVELLES_GATE_MAX_DEVIATION", DEFAULT_MAX_DEVIATION))


def _min_articles() -> int:
    return int(os.environ.get("NEWVELLES_GATE_MIN_ARTICLES", DEFAULT_MIN_ARTICLES))


def evaluate_stories_gate(
    stories_data: dict, previous_story_count: Optional[int]
) -> Tuple[bool, str]:
    """Return (ok, reason). reason is empty when ok."""
    article_count = stories_data.get("article_count", 0)
    min_articles = _min_articles()
    if article_count < min_articles:
        return False, (
            f"article count {article_count} below floor {min_articles} — "
            "looks like a broken fetch, not a news day"
        )

    story_count = stories_data.get("story_count", 0)
    if previous_story_count:  # None or 0: nothing meaningful to compare against
        deviation = abs(story_count - previous_story_count) / previous_story_count
        if deviation > _max_deviation():
            return False, (
                f"story count {story_count} deviates {deviation:.0%} from previous "
                f"published run ({previous_story_count}) — refusing to publish"
            )

    return True, ""
