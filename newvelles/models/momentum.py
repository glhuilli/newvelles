"""Story identity across runs and days, and the rolling 14-day momentum rollup.

Links can't carry identity across days — tomorrow's coverage of the same story
is entirely new articles. Identity is matched on content overlap instead:
Jaccard over keywords ∪ entities against stories last seen today or yesterday.
A match inherits the previous story id; no match mints a new one.

Per-day datapoints record a day's peak (max outlets/articles across that day's
runs); only the current day is ever mutated. The public momentum.json carries
only stories present in the current stories.json; the private state keeps the
full window.
"""
import json
from datetime import date, timedelta, timezone
from datetime import datetime as _datetime
from typing import Optional, Tuple

MOMENTUM_VERSION = "0.3.0"
WINDOW_DAYS = 14
CARRY_THRESHOLD = 0.4
LOCAL_STATE_PATH = "./cache/momentum_state.json"


def utc_today() -> str:
    """Momentum days are UTC — matching the archive timestamps and the Lambda."""
    return _datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_state_s3() -> Optional[dict]:
    """Read momentum_state.json from the private bucket; None on first run."""
    # Imported lazily: feed.log resolves bucket names from env/config at import
    # time, and tests monkeypatch them there — resolving at call time keeps the
    # patched values visible.
    from newvelles.feed.log import _MOMENTUM_STATE_NAME, _S3_BUCKET  # pylint: disable=import-outside-toplevel
    from newvelles.utils.s3 import read_json_from_s3  # pylint: disable=import-outside-toplevel
    return read_json_from_s3(_S3_BUCKET, f"{_MOMENTUM_STATE_NAME}.json")


def load_state_local(path: str = LOCAL_STATE_PATH) -> Optional[dict]:
    """Read the local momentum state; None on first run or unreadable file."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _signature(story: dict) -> set:
    return set(story.get("keywords", [])) | {e.lower() for e in story.get("entities", [])}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _empty_state() -> dict:
    return {"version": MOMENTUM_VERSION, "updated": "", "stories": {}}


def _match_previous(stories: list, state: dict, today: str) -> dict:
    """One-to-one assignment of current stories to carryable previous ids.

    Returns {current_index: previous_id}. Candidates are previous stories last
    seen today (earlier run) or yesterday; pairs are assigned best-score-first.
    """
    yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    candidates = {
        prev_id: _signature(entry)
        for prev_id, entry in state["stories"].items()
        if entry["last_seen"] >= yesterday
    }
    scored = []
    for idx, story in enumerate(stories):
        sig = _signature(story)
        for prev_id, prev_sig in candidates.items():
            score = _jaccard(sig, prev_sig)
            if score >= CARRY_THRESHOLD:
                scored.append((score, idx, prev_id))
    scored.sort(reverse=True)

    assigned: dict = {}
    used_prev: set = set()
    for _score, idx, prev_id in scored:
        if idx in assigned or prev_id in used_prev:
            continue
        assigned[idx] = prev_id
        used_prev.add(prev_id)
    return assigned


def derive_trend(series: list, peak_date: str) -> str:
    """One of: new | climbing | peaked | cooling | steady. The vocabulary is a
    UI contract — the front end prints it verbatim under the sparkline."""
    if len(series) == 1:
        return "new"
    last, prev = series[-1]["outlets"], series[-2]["outlets"]
    window_mean = sum(p["outlets"] for p in series) / len(series)
    if last > prev and last >= window_mean:
        return "climbing"
    if peak_date == series[-2]["date"] and last < prev:
        return "peaked"
    if last < prev and last < window_mean:
        return "cooling"
    return "steady"


def _peak_date(series: list) -> str:
    peak = max(p["outlets"] for p in series)
    return next(p["date"] for p in series if p["outlets"] == peak)


def apply_momentum(
    stories_data: dict, state: Optional[dict], today: str
) -> Tuple[dict, dict, dict]:
    """Carry story identity, update the rolling state, and derive momentum.json.

    Returns (stories_data with carried ids/days_running/first_seen,
             momentum_doc, new_state). stories_data is mutated in place.
    """
    state = state or _empty_state()
    window_start = (date.fromisoformat(today) - timedelta(days=WINDOW_DAYS - 1)).isoformat()
    stories = stories_data.get("stories", [])
    carried = _match_previous(stories, state, today)

    new_state_stories: dict = {}
    for idx, story in enumerate(stories):
        story_id = carried.get(idx, story["id"])
        previous = state["stories"].get(story_id) if idx in carried else None

        series = list(previous["series"]) if previous else []
        datapoint = {"date": today, "outlets": story["outlet_count"],
                     "articles": story["article_count"]}
        if series and series[-1]["date"] == today:
            # a later run on the same day: the day records its peak
            series[-1] = {
                "date": today,
                "outlets": max(series[-1]["outlets"], datapoint["outlets"]),
                "articles": max(series[-1]["articles"], datapoint["articles"]),
            }
        else:
            series.append(datapoint)
        series = [p for p in series if p["date"] >= window_start]

        first_seen = previous["first_seen"] if previous else today
        story["id"] = story_id
        story["first_seen"] = first_seen
        story["days_running"] = len(series)
        new_state_stories[story_id] = {
            "keywords": story.get("keywords", []),
            "entities": story.get("entities", []),
            "first_seen": first_seen,
            "last_seen": today,
            "series": series,
        }

    # retain previous stories not seen today while they remain inside the window
    for prev_id, entry in state["stories"].items():
        if prev_id in new_state_stories:
            continue
        trimmed = [p for p in entry["series"] if p["date"] >= window_start]
        if entry["last_seen"] >= window_start and trimmed:
            new_state_stories[prev_id] = {**entry, "series": trimmed}

    new_state = {"version": MOMENTUM_VERSION, "updated": today, "stories": new_state_stories}

    momentum_stories = {}
    for story in stories:
        entry = new_state_stories[story["id"]]
        peak = _peak_date(entry["series"])
        momentum_stories[story["id"]] = {
            "first_seen": entry["first_seen"],
            "days_running": len(entry["series"]),
            "series": entry["series"],
            "peak_date": peak,
            "trend": derive_trend(entry["series"], peak),
        }

    momentum_doc = {
        "version": MOMENTUM_VERSION,
        "generated": stories_data.get("generated", today),
        "window_days": WINDOW_DAYS,
        "window_start": window_start,
        "window_end": today,
        "stories": momentum_stories,
    }
    return stories_data, momentum_doc, new_state
