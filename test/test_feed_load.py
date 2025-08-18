"""Tests for newvelles.feed.load module."""

import tempfile
from datetime import date, timedelta
from unittest.mock import Mock, mock_open, patch

import pytest

from newvelles.feed import NewsEntry
from newvelles.feed.load import (_DATE_RANGE_DAYS, _within_date_range, build_data_from_rss_feeds,
                                 build_data_from_rss_feeds_list, load_rss)


class TestLoadRss:
    """Test load_rss function."""

    def test_load_rss_from_file(self):
        """Test loading RSS URLs from a file."""
        rss_content = """https://example.com/feed1.xml
https://example.com/feed2.xml
https://example.com/feed3.xml
"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(rss_content)
            f.flush()

            results = list(load_rss(f.name))

        expected = [
            "https://example.com/feed1.xml",
            "https://example.com/feed2.xml",
            "https://example.com/feed3.xml",
        ]
        assert results == expected

    def test_load_rss_empty_file(self):
        """Test loading RSS URLs from an empty file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("")
            f.flush()

            results = list(load_rss(f.name))

        assert results == []

    def test_load_rss_with_whitespace(self):
        """Test loading RSS URLs with whitespace handling."""
        rss_content = """  https://example.com/feed1.xml  
  https://example.com/feed2.xml  
"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(rss_content)
            f.flush()

            results = list(load_rss(f.name))

        expected = ["https://example.com/feed1.xml", "https://example.com/feed2.xml"]
        assert results == expected


class TestWithinDateRange:
    """Test _within_date_range function."""

    def test_within_date_range_recent_entry(self):
        """Test that recent entries are within date range."""
        recent_date = date.today() - timedelta(days=5)
        mock_entry = Mock()
        mock_entry.published = recent_date.isoformat()

        assert _within_date_range(mock_entry) is True

    def test_within_date_range_old_entry(self):
        """Test that old entries are outside date range."""
        old_date = date.today() - timedelta(days=_DATE_RANGE_DAYS + 5)
        mock_entry = Mock()
        mock_entry.published = old_date.isoformat()

        assert _within_date_range(mock_entry) is False

    def test_within_date_range_invalid_date(self):
        """Test handling of invalid date format."""
        mock_entry = Mock()
        mock_entry.published = "invalid-date-format"

        # Should handle invalid date gracefully and return True (assumes recent)
        result = _within_date_range(mock_entry)
        assert result is True  # Function returns True for unparseable dates

    def test_within_date_range_missing_published(self):
        """Test handling of entry without published date."""
        mock_entry = Mock()
        del mock_entry.published  # Remove published attribute

        # Should handle missing published gracefully and return True (assumes recent)
        result = _within_date_range(mock_entry)
        assert result is True  # Function returns True for missing attributes


class TestBuildDataFromRssFeeds:
    """Test build_data_from_rss_feeds functions."""

    @patch("newvelles.feed.load.parse_feed")
    @patch("newvelles.feed.load._within_date_range")
    @patch("newvelles.feed.load.log_entries")
    def test_build_data_from_rss_feeds_list(
        self, mock_log, mock_within_range, mock_parse
    ):
        """Test building data from RSS feed list."""
        # Mock entry object
        mock_entry = Mock()
        mock_entry.title = "Test Article"
        mock_entry.link = "https://example.com/article"
        mock_entry.published = "2025-01-16T10:00:00Z"
        mock_entry.title_detail = Mock()
        mock_entry.title_detail.base = "https://example.com"

        # Mock parse_feed to return feed title and entry
        mock_parse.return_value = [("Test Feed", mock_entry)]
        mock_within_range.return_value = True

        rss_list = ["https://example.com/feed.xml"]
        result = build_data_from_rss_feeds_list(rss_list, log=True)

        assert "Test Article" in result
        assert isinstance(result["Test Article"], NewsEntry)
        mock_log.assert_called_once()

    @patch("newvelles.feed.load.parse_feed")
    @patch("newvelles.feed.load._within_date_range")
    def test_build_data_from_rss_feeds_list_no_log(self, mock_within_range, mock_parse):
        """Test building data from RSS feed list without logging."""
        # Mock entry object
        mock_entry = Mock()
        mock_entry.title = "Test Article"
        mock_entry.link = "https://example.com/article"
        mock_entry.published = "2025-01-16T10:00:00Z"
        mock_entry.title_detail = Mock()
        mock_entry.title_detail.base = "https://example.com"

        mock_parse.return_value = [("Test Feed", mock_entry)]
        mock_within_range.return_value = True

        with patch("newvelles.feed.load.log_entries") as mock_log:
            rss_list = ["https://example.com/feed.xml"]
            result = build_data_from_rss_feeds_list(rss_list, log=False)

            assert "Test Article" in result
            mock_log.assert_not_called()

    @patch("newvelles.feed.load.load_rss")
    @patch("newvelles.feed.load.build_data_from_rss_feeds_list")
    def test_build_data_from_rss_feeds(self, mock_build_list, mock_load_rss):
        """Test building data from RSS feeds file."""
        mock_load_rss.return_value = ["https://example.com/feed.xml"]
        expected_result = {"Test Article": Mock()}
        mock_build_list.return_value = expected_result

        result = build_data_from_rss_feeds("test_file.txt")

        mock_load_rss.assert_called_once_with("test_file.txt")
        mock_build_list.assert_called_once_with(["https://example.com/feed.xml"])
        assert result == expected_result

    @patch("newvelles.feed.load.parse_feed")
    @patch("newvelles.feed.load._within_date_range")
    def test_build_data_old_entries_filtered(self, mock_within_range, mock_parse):
        """Test that old entries are filtered out."""
        # Mock entry object
        mock_entry = Mock()
        mock_entry.title = "Old Article"
        mock_entry.link = "https://example.com/old"
        mock_entry.published = "2020-01-16T10:00:00Z"
        mock_entry.title_detail = Mock()
        mock_entry.title_detail.base = "https://example.com"

        mock_parse.return_value = [("Test Feed", mock_entry)]
        mock_within_range.return_value = False  # Old entry

        rss_list = ["https://example.com/feed.xml"]
        result = build_data_from_rss_feeds_list(rss_list, log=False)

        assert len(result) == 0
