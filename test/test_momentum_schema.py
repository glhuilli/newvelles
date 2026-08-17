"""Schema validation for momentum.json (v0.3.0) — contract fixture and generated output."""

import json
from pathlib import Path

import jsonschema
import pytest

from newvelles.models.momentum import apply_momentum

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def schema():
    return json.loads((REPO_ROOT / "schemas" / "momentum_schema.json").read_text())


def _fixture():
    return json.loads((REPO_ROOT / "test" / "fixtures" / "momentum_v0.3.0.json").read_text())


def _generated_doc():
    story = {"id": "st_abc123", "headline": "h", "keywords": ["alaska summit"],
             "entities": ["Trump"], "outlet_count": 5, "article_count": 9,
             "days_running": 1, "first_seen": "", "kind": "story"}
    doc = {"version": "0.3.0", "generated": "2026-08-15T12:00:00",
           "story_count": 1, "article_count": 9, "stories": [story]}
    _, mom, state = apply_momentum(doc, None, "2026-08-15")
    story2 = dict(story, id="st_zzz999", outlet_count=8, article_count=15)
    doc2 = {"version": "0.3.0", "generated": "2026-08-16T12:00:00",
            "story_count": 1, "article_count": 15, "stories": [story2]}
    _, mom2, _ = apply_momentum(doc2, state, "2026-08-16")
    return mom2


def test_contract_fixture_validates(schema):
    jsonschema.validate(_fixture(), schema)


def test_generated_momentum_validates(schema):
    jsonschema.validate(_generated_doc(), schema)


def test_schema_rejects_missing_trend(schema):
    fixture = _fixture()
    story = next(iter(fixture["stories"].values()))
    del story["trend"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(fixture, schema)


def test_schema_rejects_unknown_trend(schema):
    fixture = _fixture()
    story = next(iter(fixture["stories"].values()))
    story["trend"] = "skyrocketing"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(fixture, schema)


def test_schema_rejects_empty_series(schema):
    fixture = _fixture()
    story = next(iter(fixture["stories"].values()))
    story["series"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(fixture, schema)
