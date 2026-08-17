"""Tests for newvelles.feed.parser module."""

from unittest.mock import Mock, patch

import pytest

from newvelles.feed.parser import parse_feed


class TestParseFeed:
    """Test parse_feed function."""

    @patch("newvelles.feed.parser.feedparser.parse")
    @patch("newvelles.feed.parser.debug")
    def test_parse_feed_single_feed(self, mock_debug, mock_feedparser):
        """Test parsing a single RSS feed."""
        mock_debug.return_value = False

        # Mock feedparser response with proper feed structure
        mock_feed = Mock()
        mock_feed.feed = Mock()
        mock_feed.feed.title = "Test Feed"

        # Mock entry object with all required fields
        mock_entry = Mock()
        mock_entry.title = "Test Article"
        mock_entry.link = "https://example.com/article1"
        mock_entry.published = "2025-01-16"

        mock_feed.entries = [mock_entry]
        mock_feedparser.return_value = mock_feed

        feed_paths = ["https://example.com/feed.xml"]
        results = list(parse_feed(feed_paths))

        assert len(results) == 1
        feed_title, entry_data = results[0]
        assert feed_title == "Test Feed"
        assert entry_data == mock_entry

    @patch("newvelles.feed.parser.feedparser.parse")
    @patch("newvelles.feed.parser.debug")
    def test_parse_feed_multiple_feeds(self, mock_debug, mock_feedparser):
        """Test parsing multiple RSS feeds."""
        mock_debug.return_value = False

        # Mock first feed
        mock_feed1 = Mock()
        mock_feed1.feed = Mock()
        mock_feed1.feed.title = "Feed 1"
        mock_entry1 = Mock()
        mock_entry1.title = "Article 1"
        mock_entry1.link = "https://example.com/article1"
        mock_entry1.published = "2025-01-16"
        mock_feed1.entries = [mock_entry1]

        # Mock second feed
        mock_feed2 = Mock()
        mock_feed2.feed = Mock()
        mock_feed2.feed.title = "Feed 2"
        mock_entry2 = Mock()
        mock_entry2.title = "Article 2"
        mock_entry2.link = "https://example.com/article2"
        mock_entry2.published = "2025-01-16"
        mock_feed2.entries = [mock_entry2]

        mock_feedparser.side_effect = [mock_feed1, mock_feed2]

        feed_paths = ["https://example.com/feed1.xml", "https://example.com/feed2.xml"]
        results = list(parse_feed(feed_paths))

        assert len(results) == 2
        assert results[0][0] == "Feed 1"
        assert results[1][0] == "Feed 2"

    @patch("newvelles.feed.parser.feedparser.parse")
    @patch("newvelles.feed.parser.debug")
    @patch("newvelles.feed.parser.logger")
    def test_parse_feed_with_exception(self, mock_logger, mock_debug, mock_feedparser):
        """Test parsing feeds when feedparser raises an exception."""
        mock_debug.return_value = False
        mock_feedparser.side_effect = Exception("Network error")

        feed_paths = ["https://example.com/bad-feed.xml"]
        results = list(parse_feed(feed_paths))

        # Should return empty list when there's an exception
        assert len(results) == 0
        # Should log the exception
        mock_logger.exception.assert_called_once()

    @patch("newvelles.feed.parser.feedparser.parse")
    @patch("newvelles.feed.parser.DEBUG", True)
    def test_parse_feed_debug_mode(self, mock_feedparser):

        # Mock feedparser response
        mock_feed = Mock()
        mock_feed.feed = Mock()
        mock_feed.feed.title = "Test Feed"

        mock_entry = Mock()
        mock_entry.title = "Test Article"
        mock_entry.link = "https://example.com/article1"
        mock_entry.published = "2025-01-16"
        mock_feed.entries = [mock_entry]
        mock_feedparser.return_value = mock_feed

        feed_paths = ["https://example.com/feed.xml"]

        with patch("builtins.print") as mock_print:
            results = list(parse_feed(feed_paths))

        assert len(results) == 1
        # In debug mode, it should print the feed info with entries count
        mock_print.assert_called_with("Test Feed entries: 1")

    @patch("newvelles.feed.parser.feedparser.parse")
    @patch("newvelles.feed.parser.debug")
    def test_parse_feed_empty_list(self, mock_debug, mock_feedparser):
        """Test parsing with empty feed list."""
        mock_debug.return_value = False

        feed_paths = []
        results = list(parse_feed(feed_paths))

        assert len(results) == 0
        mock_feedparser.assert_not_called()

    @patch("newvelles.feed.parser.feedparser.parse")
    @patch("newvelles.feed.parser.debug")
    def test_parse_feed_missing_feed_title(self, mock_debug, mock_feedparser):
        """Test parsing feed with missing feed title."""
        mock_debug.return_value = False

        # Mock feed data without title - our new implementation handles this gracefully
        mock_feed = Mock()
        mock_feed.feed = Mock()
        # Remove title attribute to trigger the fallback logic
        del mock_feed.feed.title
        
        mock_entry = Mock()
        mock_entry.title = "Test Article"
        mock_entry.link = "https://example.com/article1"
        mock_entry.published = "2025-01-16"
        mock_feed.entries = [mock_entry]
        
        mock_feedparser.return_value = mock_feed

        feed_paths = ["https://example.com/feed.xml"]
        results = list(parse_feed(feed_paths))

        # Should handle missing title gracefully with fallback title
        assert len(results) == 1
        feed_title, entry_data = results[0]
        # Should use URL-based fallback title
        assert "example.com" in str(feed_title)


class TestParseFeedHealth:
    """parse_feed appends one health record per feed path when given a collector."""

    @patch("newvelles.feed.parser.feedparser.parse")
    def test_health_record_per_feed(self, mock_parse):
        import feedparser as fp

        good = fp.FeedParserDict()
        good["status"] = 200
        good["feed"] = fp.FeedParserDict()
        good["feed"]["title"] = "Good Feed"
        entry = fp.FeedParserDict()
        entry["title"] = "A"
        entry["link"] = "https://example.com/a"
        entry["published"] = "2026-08-16"
        good["entries"] = [entry]

        empty = fp.FeedParserDict()
        empty["status"] = 404
        empty["entries"] = []

        mock_parse.side_effect = [good, empty]
        health = []
        results = list(parse_feed(["https://good.example/rss", "https://dead.example/rss"],
                                  health=health))

        assert len(results) == 1  # empty feed yields no entries
        assert [r["url"] for r in health] == ["https://good.example/rss",
                                              "https://dead.example/rss"]
        assert health[0]["ok"] is True
        assert health[1]["ok"] is False
        assert health[1]["http_status"] == 404

    @patch("newvelles.feed.parser.feedparser.parse")
    def test_health_record_on_exception(self, mock_parse):
        mock_parse.side_effect = RuntimeError("connection reset")
        health = []
        results = list(parse_feed(["https://broken.example/rss"], health=health))
        assert results == []
        assert len(health) == 1
        assert health[0]["ok"] is False
        assert "connection reset" in health[0]["error"]

    @patch("newvelles.feed.parser.feedparser.parse")
    def test_no_collector_keeps_old_behavior(self, mock_parse):
        mock_parse.side_effect = RuntimeError("boom")
        assert list(parse_feed(["https://broken.example/rss"])) == []
