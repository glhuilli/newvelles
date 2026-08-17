"""Schema validation for stories.json (v0.3.0) — contract fixture and real output."""

import json
from pathlib import Path

import jsonschema
import pytest

from newvelles.models.stories import build_stories

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def schema():
    return json.loads((REPO_ROOT / "schemas" / "stories_schema.json").read_text())


def _fixture():
    return json.loads((REPO_ROOT / "test" / "fixtures" / "stories_v0.3.0.json").read_text())


def test_contract_fixture_validates(schema):
    jsonschema.validate(_fixture(), schema)


def test_build_stories_output_validates(schema):
    viz = json.loads((REPO_ROOT / "data" / "latest_news_example.json").read_text())
    jsonschema.validate(build_stories(viz), schema)


def test_schema_rejects_missing_headline(schema):
    fixture = _fixture()
    del fixture["stories"][0]["headline"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(fixture, schema)


def test_schema_rejects_bad_kind(schema):
    fixture = _fixture()
    fixture["stories"][0]["kind"] = "advert"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(fixture, schema)
