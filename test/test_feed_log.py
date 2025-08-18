"""Tests for newvelles.feed.log module."""

import json
import os
import tempfile
from unittest.mock import Mock, mock_open, patch

import pytest

from newvelles.feed.log import (_LATEST_PATH, _LOG_GROUPED_NAME,
                                _LOG_LATEST_VISUALIZATION_METADATA_NAME,
                                _LOG_LATEST_VISUALIZATION_NAME, _LOG_NAME, _LOG_PATH,
                                _LOG_VISUALIZATION_NAME, _S3_BUCKET, _S3_PUBLIC_BUCKET,
                                _current_datetime, log_entries, log_s3)


class TestCurrentDatetime:
    """Test _current_datetime function."""

    @patch("newvelles.feed.log.datetime")
    def test_current_datetime_format(self, mock_datetime):
        """Test that _current_datetime returns correctly formatted datetime."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-16T10:30:45.123456"
        mock_datetime.now.return_value = mock_now

        result = _current_datetime()

        # Should remove microseconds and join with dots
        expected = "2025-01-16T10:30:45"
        assert result == expected

    @patch("newvelles.feed.log.datetime")
    def test_current_datetime_no_microseconds(self, mock_datetime):
        """Test _current_datetime when no microseconds present."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-16T10:30:45"
        mock_datetime.now.return_value = mock_now

        result = _current_datetime()

        # When no microseconds, should return the datetime string as-is
        expected = "2025-01-16T10:30:45"
        assert result == expected


class TestLogEntries:
    """Test log_entries function - Lambda-compatible version (stats only, no file operations)."""

    def test_log_entries_basic(self, capsys):
        """Test basic functionality of log_entries (Lambda-compatible stats only)."""
        title_data = {
            "Article 1": ["Article 1", "https://example.com/1"],
            "Article 2": ["Article 2", "https://example.com/2"],
        }
        news_data = {
            "Feed 1": [["Article 1", "https://example.com/1"]],
            "Feed 2": [["Article 2", "https://example.com/2"]],
        }

        log_entries(title_data, news_data)

        # Capture printed output
        captured = capsys.readouterr()
        
        # Should print statistics
        assert "📊 Log entries summary:" in captured.out
        assert "Title data entries: 2" in captured.out
        assert "News feeds processed: 2" in captured.out
        assert "Top feeds:" in captured.out

    def test_log_entries_empty_data(self, capsys):
        """Test log_entries with empty data."""
        title_data = {}
        news_data = {}

        log_entries(title_data, news_data)

        # Capture printed output
        captured = capsys.readouterr()
        
        # Should print statistics for empty data
        assert "📊 Log entries summary:" in captured.out
        assert "Title data entries: 0" in captured.out
        assert "News feeds processed: 0" in captured.out

    def test_log_entries_feed_ranking(self, capsys):
        """Test that log_entries shows top feeds by article count."""
        title_data = {
            "Article 1": ["Article 1", "https://example.com/1"],
            "Article 2": ["Article 2", "https://example.com/2"],
            "Article 3": ["Article 3", "https://example.com/3"],
        }
        news_data = {
            "High Volume Feed": [["A1"], ["A2"], ["A3"]],  # 3 articles
            "Medium Feed": [["B1"], ["B2"]],  # 2 articles  
            "Low Feed": [["C1"]],  # 1 article
        }

        log_entries(title_data, news_data)

        # Capture printed output
        captured = capsys.readouterr()
        
        # Should show top feeds ranked by article count
        assert "Top feeds:" in captured.out
        assert "High Volume Feed(3)" in captured.out

    def test_log_entries_no_file_operations(self):
        """Test that log_entries does not perform any file operations (Lambda-compatible)."""
        title_data = {"Article 1": ["Article 1", "https://example.com/1"]}
        news_data = {"Feed 1": [["Article 1", "https://example.com/1"]]}

        with patch("os.makedirs") as mock_makedirs, \
             patch("builtins.open", mock_open()) as mock_file:
            
            log_entries(title_data, news_data)

            # Should NOT create directories or files (Lambda-compatible)
            mock_makedirs.assert_not_called()
            mock_file.assert_not_called()


class TestLogS3:
    """Test log_s3 function."""

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_log_s3_basic(self, mock_datetime, mock_upload):
        """Test basic functionality of log_s3 (S3-only uploads)."""
        mock_datetime.return_value = "2025-01-16T10:30:45"

        visualization_data = {
            "group1": {
                "subgroup1": {
                    "Article 1": {"title": "Article 1", "link": "https://example.com/1"}
                }
            }
        }

        result = log_s3(visualization_data)

        # Should return the S3 file name
        expected_filename = "newvelles_visualization_0.2.1_2025-01-16T10:30:45.json"
        assert result == expected_filename

        # Should upload to S3 (3 uploads: private bucket + 2 public bucket files)
        assert mock_upload.call_count == 3

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.makedirs")
    def test_log_s3_uploads(self, mock_makedirs, mock_file, mock_datetime, mock_upload):
        """Test that log_s3 uploads to correct S3 locations."""
        mock_datetime.return_value = "2025-01-16T10:30:45"

        visualization_data = {}

        log_s3(visualization_data)

        # Should upload to both private and public buckets
        upload_calls = mock_upload.call_args_list

        # Check that private bucket uploads are made
        private_uploads = [
            call for call in upload_calls if call.kwargs["bucket_name"] == _S3_BUCKET
        ]
        assert len(private_uploads) >= 1

        # Check that public bucket uploads are made
        public_uploads = [
            call
            for call in upload_calls
            if call.kwargs["bucket_name"] == _S3_PUBLIC_BUCKET
        ]
        assert len(public_uploads) >= 1

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_log_s3_file_names(self, mock_datetime, mock_upload):
        """Test that log_s3 uploads files with correct names to S3."""
        mock_datetime.return_value = "2025-01-16T10:30:45"

        visualization_data = {}

        log_s3(visualization_data)

        # Check S3 upload calls for correct file names
        upload_calls = mock_upload.call_args_list

        # Extract file names from upload calls
        uploaded_files = [call.kwargs["file_name"] for call in upload_calls]

        expected_files = [
            "newvelles_visualization_0.2.1_2025-01-16T10:30:45.json",  # Private bucket
            "latest_news.json",  # Public bucket
            "latest_news_metadata.json",  # Public bucket
        ]

        for expected_file in expected_files:
            assert expected_file in uploaded_files

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_log_s3_metadata_content(self, mock_datetime, mock_upload):
        """Test that log_s3 uploads correct metadata content to S3."""
        mock_datetime.return_value = "2025-01-16T10:30:45"

        visualization_data = {}

        log_s3(visualization_data)

        # Find the metadata upload call
        upload_calls = mock_upload.call_args_list
        metadata_calls = [
            call for call in upload_calls
            if call.kwargs["file_name"] == "latest_news_metadata.json"
        ]

        assert len(metadata_calls) == 1

        # Check the metadata content
        metadata_content = metadata_calls[0].kwargs["string_byte"].decode("utf-8")
        import json
        metadata = json.loads(metadata_content)

        assert "datetime" in metadata
        assert "version" in metadata
        assert metadata["datetime"] == "2025-01-16T10:30:45"
        assert metadata["version"] == "0.2.1"
