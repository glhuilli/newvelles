"""Tests for newvelles.utils.dates — RSS date normalization to ISO 8601 UTC."""

import pytest

from newvelles.utils.dates import iso_date, to_iso8601


@pytest.mark.parametrize("raw,expected", [
    ("Sat, 16 Aug 2025 18:51:12 +0000", "2025-08-16T18:51:12Z"),   # RFC 2822
    ("2025-08-16T04:31:19Z", "2025-08-16T04:31:19Z"),              # already ISO/UTC
    ("Sat, 16 Aug 2025 13:00:00 EST", "2025-08-16T18:00:00Z"),     # named US zone
    ("Sat, 16 Aug 2025 13:00:00 GMT", "2025-08-16T13:00:00Z"),
    ("2026-08-07T12:00:00", "2026-08-07T12:00:00Z"),               # naive -> assume UTC
    ("2025-08-16T04:31:19+02:00", "2025-08-16T02:31:19Z"),         # offset converted
])
def test_to_iso8601_formats(raw, expected):
    assert to_iso8601(raw) == expected


def test_to_iso8601_unparseable_returns_input():
    assert to_iso8601("not a date") == "not a date"
    assert to_iso8601("") == ""


def test_iso_date():
    assert iso_date("Sat, 16 Aug 2025 18:51:12 +0000") == "2025-08-16"
    assert iso_date("garbage") == ""
