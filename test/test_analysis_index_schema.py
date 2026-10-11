"""Contract tests for analysis/entries/index.json and the publish helper."""
import gzip
import json
import os

import jsonschema
import pytest

SCHEMA_PATH = "schemas/analysis_index_schema.json"
INDEX_PATH = "analysis/entries/index.json"


@pytest.fixture
def schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _valid_index():
    return {
        "version": "0.1.0",
        "generated": "2026-09-19T20:00:00Z",
        "entries": [
            {
                "id": "five-years",
                "number": 1,
                "title": "Five years of news cycles",
                "summary": "How stories start, peak and fade.",
                "first_day": "2021-07-10",
                "last_day": "2026-08-18",
                "published": "2026-09-19",
                "links": {"post": "", "code": "https://github.com/glhuilli/newvelles/tree/main/analysis"},
                "panels": ["timeline", "ledger"],
                "payload": "/analysis/entries/five-years/payload.json",
                "stats": {"runs": 9311, "stories": 114927, "days": 1832, "majors": 13},
            }
        ],
    }


def test_valid_index_passes(schema):
    jsonschema.validate(_valid_index(), schema)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["entries"][0].update(id="Five Years"),
        lambda d: d["entries"][0].update(id="../etc"),
        lambda d: d["entries"][0].pop("payload"),
        lambda d: d["entries"][0].update(panels=[]),
        lambda d: d["entries"][0].update(first_day="2021/07/10"),
        lambda d: d.update(version="1.0"),
        lambda d: d["entries"][0]["stats"].update(runs="9311"),
    ],
)
def test_invalid_index_rejected(schema, mutate):
    doc = _valid_index()
    mutate(doc)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)


def test_checked_in_index_validates(schema):
    assert os.path.exists(INDEX_PATH), "run: analysis/.venv/bin/python analysis/build_payload.py --entry five-years"
    with open(INDEX_PATH, encoding="utf-8") as f:
        doc = json.load(f)
    jsonschema.validate(doc, schema)
    assert doc["entries"][0]["id"] == "five-years"
    numbers = [e["number"] for e in doc["entries"]]
    assert numbers == sorted(numbers, reverse=True), "entries must be newest first"


def test_publish_helpers_gzip_and_headers():
    from scripts.publish_analysis import gzip_bytes, put_args

    raw = json.dumps({"a": 1}).encode()
    gz = gzip_bytes(raw)
    assert gzip.decompress(gz) == raw
    args = put_args("analysis/index.json", gz, cache_seconds=300)
    assert args["Key"] == "analysis/index.json"
    assert args["Body"] == gz
    assert args["ContentType"] == "application/json"
    assert args["ContentEncoding"] == "gzip"
    assert args["CacheControl"] == "public, max-age=300"
    # the public bucket has no policy; readability comes from this ACL alone
    assert args["ACL"] == "public-read"
