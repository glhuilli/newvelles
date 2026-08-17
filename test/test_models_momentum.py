"""Tests for newvelles.models.momentum — cross-run story identity and the 14-day rollup."""

import pytest

from newvelles.models.momentum import (CARRY_THRESHOLD, WINDOW_DAYS, apply_momentum,
                                       derive_trend)


def _story(sid, keywords, entities, outlets=3, articles=6):
    return {
        "id": sid,
        "headline": f"headline {sid}",
        "keywords": keywords,
        "entities": entities,
        "outlet_count": outlets,
        "article_count": articles,
        "days_running": 1,
        "first_seen": "",
        "kind": "story",
    }


def _doc(stories):
    return {"version": "0.3.0", "story_count": len(stories),
            "article_count": sum(s["article_count"] for s in stories), "stories": stories}


ALASKA = _story("st_aaa111", ["alaska summit", "ceasefire"], ["Trump", "Putin", "Alaska"],
                outlets=10, articles=20)
MARKETS = _story("st_bbb222", ["fed rates"], ["Federal Reserve", "Powell"], outlets=4, articles=7)


class TestIdentityCarry:
    def test_two_day_carry_death_and_birth(self):
        # Day 1: alaska + markets
        d1, mom1, state1 = apply_momentum(_doc([dict(ALASKA), dict(MARKETS)]), None, "2026-08-15")
        assert set(mom1["stories"]) == {"st_aaa111", "st_bbb222"}
        assert all(v["trend"] == "new" for v in mom1["stories"].values())

        # Day 2: alaska persists under a NEW fingerprint id; markets died; tech is born
        alaska_day2 = _story("st_ccc333", ["alaska summit", "ceasefire", "zelensky"],
                             ["Trump", "Putin", "Alaska", "Zelensky"], outlets=14, articles=30)
        tech = _story("st_ddd444", ["pixel event"], ["Google"], outlets=2, articles=4)
        d2, mom2, state2 = apply_momentum(_doc([alaska_day2, tech]), state1, "2026-08-16")

        # carried: the day-2 alaska story now carries the day-1 id
        carried = d2["stories"][0]
        assert carried["id"] == "st_aaa111"
        assert carried["days_running"] == 2
        assert carried["first_seen"] == "2026-08-15"
        entry = mom2["stories"]["st_aaa111"]
        assert [p["date"] for p in entry["series"]] == ["2026-08-15", "2026-08-16"]
        assert entry["series"][1]["outlets"] == 14
        # died: markets absent from the doc but retained in state for the window
        assert "st_bbb222" not in mom2["stories"]
        assert "st_bbb222" in state2["stories"]
        # born: fresh id, new trend
        assert mom2["stories"]["st_ddd444"]["trend"] == "new"

    def test_same_day_second_run_takes_max_and_keeps_id(self):
        d1, _, state1 = apply_momentum(_doc([dict(ALASKA)]), None, "2026-08-15")
        # later run same day: fewer outlets in this fetch, more articles
        again = _story("st_eee555", ["alaska summit", "ceasefire"], ["Trump", "Putin", "Alaska"],
                       outlets=7, articles=25)
        d2, mom2, state2 = apply_momentum(_doc([again]), state1, "2026-08-15")
        assert d2["stories"][0]["id"] == "st_aaa111"
        series = mom2["stories"]["st_aaa111"]["series"]
        assert len(series) == 1  # still one datapoint for the day
        assert series[0]["outlets"] == 10   # max(10, 7) — a day records its peak
        assert series[0]["articles"] == 25  # max(20, 25)
        assert d2["stories"][0]["days_running"] == 1

    def test_skipped_day_mints_new_id(self):
        _, _, state1 = apply_momentum(_doc([dict(ALASKA)]), None, "2026-08-13")
        # story absent on the 14th; returns on the 15th -> matching window is yesterday only
        returns = _story("st_fff666", ["alaska summit", "ceasefire"],
                         ["Trump", "Putin", "Alaska"])
        d3, mom3, _ = apply_momentum(_doc([returns]), state1, "2026-08-15")
        assert d3["stories"][0]["id"] == "st_fff666"
        assert mom3["stories"]["st_fff666"]["trend"] == "new"

    def test_one_to_one_matching_prefers_best_score(self):
        _, _, state1 = apply_momentum(_doc([dict(ALASKA)]), None, "2026-08-15")
        strong = _story("st_ggg777", ["alaska summit", "ceasefire"],
                        ["Trump", "Putin", "Alaska"])          # high overlap
        weak = _story("st_hhh888", ["alaska summit"], ["Alaska", "Anchorage", "Tourism"])
        d2, _, _ = apply_momentum(_doc([weak, strong]), state1, "2026-08-16")
        by_headline = {s["headline"]: s["id"] for s in d2["stories"]}
        assert by_headline["headline st_ggg777"] == "st_aaa111"  # best match carries the id
        assert by_headline["headline st_hhh888"] == "st_hhh888"  # loser keeps its own id

    def test_below_threshold_does_not_carry(self):
        _, _, state1 = apply_momentum(_doc([dict(ALASKA)]), None, "2026-08-15")
        unrelated = _story("st_iii999", ["earnings"], ["Acme Corp"])
        d2, _, _ = apply_momentum(_doc([unrelated]), state1, "2026-08-16")
        assert d2["stories"][0]["id"] == "st_iii999"


class TestWindow:
    def test_series_never_exceeds_window(self):
        state = None
        stories_doc = None
        for day in range(1, 17):  # 16 consecutive days
            persistent = _story(f"st_day{day:02}", ["alaska summit", "ceasefire"],
                                ["Trump", "Putin", "Alaska"], outlets=day)
            stories_doc, mom, state = apply_momentum(_doc([persistent]), state,
                                                     f"2026-08-{day:02}")
        entry = list(mom["stories"].values())[0]
        assert len(entry["series"]) <= WINDOW_DAYS
        assert entry["series"][-1]["date"] == "2026-08-16"
        assert mom["window_days"] == WINDOW_DAYS
        assert mom["window_start"] == "2026-08-03"
        assert mom["window_end"] == "2026-08-16"

    def test_state_prunes_stories_outside_window(self):
        _, _, state = apply_momentum(_doc([dict(ALASKA)]), None, "2026-08-01")
        for day in range(2, 17):
            other = _story(f"st_x{day:02}", [f"kw{day}"], [f"Ent{day}"])
            _, _, state = apply_momentum(_doc([other]), state, f"2026-08-{day:02}")
        assert "st_aaa111" not in state["stories"]  # last seen 2026-08-01, outside window


class TestTrend:
    def _series(self, *outlets, start_day=1):
        return [{"date": f"2026-08-{start_day + i:02}", "outlets": o, "articles": o * 2}
                for i, o in enumerate(outlets)]

    def test_single_datapoint_is_new(self):
        assert derive_trend(self._series(5), "2026-08-01") == "new"

    def test_climbing(self):
        s = self._series(3, 5, 9)
        assert derive_trend(s, "2026-08-03") == "climbing"

    def test_peaked_yesterday(self):
        s = self._series(3, 12, 6)
        assert derive_trend(s, "2026-08-02") == "peaked"

    def test_cooling(self):
        s = self._series(12, 9, 4, 2)
        assert derive_trend(s, "2026-08-01") == "cooling"

    def test_steady(self):
        s = self._series(5, 5, 5)
        assert derive_trend(s, "2026-08-01") == "steady"


class TestDocShape:
    def test_doc_contains_only_current_story_ids(self):
        _, _, state1 = apply_momentum(_doc([dict(ALASKA), dict(MARKETS)]), None, "2026-08-15")
        only_alaska = _story("st_jjj000", ["alaska summit", "ceasefire"],
                             ["Trump", "Putin", "Alaska"])
        _, mom2, _ = apply_momentum(_doc([only_alaska]), state1, "2026-08-16")
        assert set(mom2["stories"]) == {"st_aaa111"}

    def test_first_run_from_none_state(self):
        d, mom, state = apply_momentum(_doc([dict(ALASKA)]), None, "2026-08-15")
        assert mom["version"] == "0.3.0"
        assert d["stories"][0]["first_seen"] == "2026-08-15"
        assert state["stories"]["st_aaa111"]["last_seen"] == "2026-08-15"

    def test_peak_date_is_earliest_max(self):
        state = None
        outlets_by_day = {15: 4, 16: 9, 17: 9}
        for day, o in outlets_by_day.items():
            s = _story(f"st_p{day}", ["alaska summit", "ceasefire"],
                       ["Trump", "Putin", "Alaska"], outlets=o)
            _, mom, state = apply_momentum(_doc([s]), state, f"2026-08-{day}")
        entry = list(mom["stories"].values())[0]
        assert entry["peak_date"] == "2026-08-16"  # earliest occurrence of the max


def test_carry_threshold_constant():
    assert CARRY_THRESHOLD == 0.4
    assert WINDOW_DAYS == 14
