"""Tests for newvelles.feed.__init__ module."""

import pytest

from newvelles.feed import NewsEntry


class TestNewsEntry:
    """Test NewsEntry NamedTuple."""

    def test_news_entry_creation(self):
        """Test NewsEntry can be created with required fields."""
        entry = NewsEntry(
            title="Test Title",
            link="https://example.com",
            published="2025-01-16",
            title_detail_base="example.com",
        )

        assert entry.title == "Test Title"
        assert entry.link == "https://example.com"
        assert entry.published == "2025-01-16"
        assert entry.title_detail_base == "example.com"

    def test_news_entry_immutable(self):
        """Test that NewsEntry is immutable."""
        entry = NewsEntry(
            title="Test Title",
            link="https://example.com",
            published="2025-01-16",
            title_detail_base="example.com",
        )

        with pytest.raises(AttributeError):
            entry.title = "New Title"

    def test_news_entry_indexable(self):
        """Test that NewsEntry is indexable like a tuple."""
        entry = NewsEntry(
            title="Test Title",
            link="https://example.com",
            published="2025-01-16",
            title_detail_base="example.com",
        )

        assert entry[0] == "Test Title"
        assert entry[1] == "https://example.com"
        assert entry[2] == "2025-01-16"
        assert entry[3] == "example.com"

    def test_news_entry_fields(self):
        """Test that NewsEntry has the expected fields."""
        expected_fields = ["title", "link", "published", "title_detail_base"]
        assert NewsEntry._fields == tuple(expected_fields)

    def test_news_entry_asdict(self):
        """Test NewsEntry._asdict() method."""
        entry = NewsEntry(
            title="Test Title",
            link="https://example.com",
            published="2025-01-16",
            title_detail_base="example.com",
        )

        expected_dict = {
            "title": "Test Title",
            "link": "https://example.com",
            "published": "2025-01-16",
            "title_detail_base": "example.com",
        }

        assert entry._asdict() == expected_dict
