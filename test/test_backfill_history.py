"""Tests for scripts/backfill_history.py — the identity-carry pass."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from backfill_history import _day_delta, _new_uid, carry_identity


def _story(headline, keywords, entities=()):
    return {"headline": headline, "keywords": list(keywords), "entities": list(entities)}


def _uids(rows):
    return [s["story_uid"] for _, _, s in rows]


class TestCarryIdentity:
    def test_same_signature_carries_uid_across_consecutive_days(self):
        runs = [
            ("2021-07-10", "2021-07-10T01:00:00", [_story("A", ["alpha", "beta", "gamma"])]),
            ("2021-07-11", "2021-07-11T01:00:00", [_story("A again", ["alpha", "beta", "gamma"])]),
        ]
        uids = _uids(list(carry_identity(runs)))
        assert uids[0] == uids[1]

    def test_below_threshold_gets_new_uid(self):
        runs = [
            ("2021-07-10", "2021-07-10T01:00:00", [_story("A", ["alpha", "beta", "gamma"])]),
            ("2021-07-11", "2021-07-11T01:00:00", [_story("B", ["delta", "epsilon", "zeta"])]),
        ]
        uids = _uids(list(carry_identity(runs)))
        assert uids[0] != uids[1]

    def test_two_day_gap_resets_carry(self):
        kw = ["alpha", "beta", "gamma"]
        runs = [
            ("2021-07-10", "2021-07-10T01:00:00", [_story("A", kw)]),
            ("2021-07-13", "2021-07-13T01:00:00", [_story("A returns", kw)]),
        ]
        uids = _uids(list(carry_identity(runs)))
        assert uids[0] != uids[1]

    def test_same_day_multiple_runs_carry(self):
        kw = ["alpha", "beta", "gamma"]
        runs = [
            ("2021-07-10", "2021-07-10T01:00:00", [_story("A", kw)]),
            ("2021-07-10", "2021-07-10T07:00:00", [_story("A later", kw)]),
        ]
        uids = _uids(list(carry_identity(runs)))
        assert uids[0] == uids[1]

    def test_every_input_story_yields_one_row(self):
        runs = [
            ("2021-07-10", "2021-07-10T01:00:00",
             [_story("A", ["a1", "a2"]), _story("B", ["b1", "b2"])]),
            ("2021-07-11", "2021-07-11T01:00:00", [_story("C", ["c1", "c2"])]),
        ]
        rows = list(carry_identity(runs))
        assert len(rows) == 3
        assert [ts for ts, _, _ in rows] == [
            "2021-07-10T01:00:00", "2021-07-10T01:00:00", "2021-07-11T01:00:00"]

    def test_signature_includes_entities(self):
        runs = [
            ("2021-07-10", "2021-07-10T01:00:00", [_story("A", ["k1"], ["Tupac", "Vegas"])]),
            ("2021-07-11", "2021-07-11T01:00:00", [_story("B", ["k1"], ["Tupac", "Vegas"])]),
        ]
        uids = _uids(list(carry_identity(runs)))
        assert uids[0] == uids[1]


def test_day_delta():
    assert _day_delta("2021-07-11", "2021-07-10") == 1
    assert _day_delta("2021-08-01", "2021-07-31") == 1
    assert _day_delta("2021-07-13", "2021-07-10") == 3


def test_new_uid_is_stable_and_distinct():
    s1 = _story("Headline one", ["k1", "k2"])
    s2 = _story("Headline two", ["k1", "k2"])
    assert _new_uid("2021-07-10", s1) == _new_uid("2021-07-10", s1)
    assert _new_uid("2021-07-10", s1) != _new_uid("2021-07-10", s2)
    assert _new_uid("2021-07-10", s1).startswith("h_")
