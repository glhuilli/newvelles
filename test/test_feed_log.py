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


class TestEmitVisualization:
    """The unified emit function must reproduce both legacy paths byte-identically."""

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_s3_writer_matches_legacy_log_s3(self, mock_datetime, mock_upload):
        from newvelles.feed.log import emit_visualization
        mock_datetime.return_value = "2025-01-16T10:30:45"
        viz = {"g": {"sg": {"T": {"title": "T", "link": "https://x/1"}}}}

        result = emit_visualization(viz, writers="s3")

        assert result == "newvelles_visualization_0.2.1_2025-01-16T10:30:45.json"
        assert mock_upload.call_count == 3
        names = [c.kwargs["file_name"] for c in mock_upload.call_args_list]
        assert names == [
            "newvelles_visualization_0.2.1_2025-01-16T10:30:45.json",
            "latest_news.json",
            "latest_news_metadata.json",
        ]
        # S3 metadata records which archive object the live file came from,
        # turning a restore from a search into a lookup
        meta = json.loads(mock_upload.call_args_list[2].kwargs["string_byte"])
        assert meta == {
            "datetime": "2025-01-16T10:30:45",
            "version": "0.2.1",
            "latest_log_reference": "newvelles_visualization_0.2.1_2025-01-16T10:30:45.json",
        }
        # payload bytes identical to legacy json.dumps
        assert mock_upload.call_args_list[0].kwargs["string_byte"] == json.dumps(viz).encode("utf-8")
        # public flags
        assert mock_upload.call_args_list[0].kwargs.get("public_read", False) is False
        assert mock_upload.call_args_list[1].kwargs["public_read"] is True
        assert mock_upload.call_args_list[2].kwargs["public_read"] is True

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_local_writer_writes_files_and_metadata_reference(
        self, mock_datetime, mock_upload, tmp_path, monkeypatch
    ):
        from newvelles.feed import log as log_mod
        mock_datetime.return_value = "2025-01-16T10:30:45"
        monkeypatch.setattr(log_mod, "_LATEST_PATH", str(tmp_path / "latest"))
        monkeypatch.chdir(tmp_path)
        viz = {"a": 1}

        result = log_mod.emit_visualization(viz, writers="local", output_path=str(tmp_path / "logs"))

        assert result == str(tmp_path / "logs") + "/newvelles_visualization_0.2.1_2025-01-16T10:30:45.json"
        assert json.load(open(result)) == viz
        assert json.load(open(tmp_path / "latest" / "latest_news.json")) == viz
        assert json.load(open(tmp_path / "latest_news.json")) == viz  # cwd copy
        meta = json.load(open(tmp_path / "latest" / "latest_news_metadata.json"))
        assert meta["latest_log_reference"] == result  # local path INCLUDES the reference
        mock_upload.assert_not_called()

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_both_writer_uploads_metadata_with_reference(
        self, mock_datetime, mock_upload, tmp_path, monkeypatch
    ):
        from newvelles.feed import log as log_mod
        mock_datetime.return_value = "2025-01-16T10:30:45"
        monkeypatch.setattr(log_mod, "_LATEST_PATH", str(tmp_path / "latest"))
        monkeypatch.chdir(tmp_path)

        log_mod.emit_visualization({}, writers="both", output_path=str(tmp_path / "logs"))

        meta_call = [c for c in mock_upload.call_args_list
                     if c.kwargs["file_name"] == "latest_news_metadata.json"][0]
        meta = json.loads(meta_call.kwargs["string_byte"])
        assert "latest_log_reference" in meta  # legacy log_visualization(s3=True) behavior

    def test_invalid_writer_raises(self):
        from newvelles.feed.log import emit_visualization
        with pytest.raises(ValueError):
            emit_visualization({}, writers="ftp")

    @patch("newvelles.feed.log.emit_visualization")
    def test_log_s3_delegates(self, mock_emit):
        mock_emit.return_value = "x.json"
        assert log_s3({}) == "x.json"
        mock_emit.assert_called_once_with({}, writers="s3", stories_data=None,
                                          momentum_doc=None, momentum_state=None)


class TestEmitStories:
    @patch("newvelles.feed.log.read_json_from_s3", return_value=None)
    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_stories_uploaded_to_public_bucket_after_legacy_files(
        self, mock_datetime, mock_upload, mock_read
    ):
        from newvelles.feed.log import emit_visualization
        mock_datetime.return_value = "2025-01-16T10:30:45"
        stories = {"version": "0.3.0", "story_count": 100, "article_count": 500, "stories": []}

        emit_visualization({}, writers="s3", stories_data=stories)

        names = [c.kwargs["file_name"] for c in mock_upload.call_args_list]
        assert names == [
            "newvelles_visualization_0.2.1_2025-01-16T10:30:45.json",
            "latest_news.json",
            "latest_news_metadata.json",
            "stories.json",
        ]
        stories_call = mock_upload.call_args_list[3]
        assert stories_call.kwargs["bucket_name"] == _S3_PUBLIC_BUCKET
        assert stories_call.kwargs["public_read"] is True
        assert json.loads(stories_call.kwargs["string_byte"]) == stories

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_no_stories_means_no_fourth_upload(self, mock_datetime, mock_upload):
        from newvelles.feed.log import emit_visualization
        mock_datetime.return_value = "2025-01-16T10:30:45"
        emit_visualization({}, writers="s3")
        assert mock_upload.call_count == 3

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_local_writer_writes_stories_file(self, mock_datetime, mock_upload, tmp_path, monkeypatch):
        from newvelles.feed import log as log_mod
        mock_datetime.return_value = "2025-01-16T10:30:45"
        monkeypatch.setattr(log_mod, "_LATEST_PATH", str(tmp_path / "latest"))
        monkeypatch.chdir(tmp_path)
        stories = {"version": "0.3.0", "stories": []}

        log_mod.emit_visualization({}, writers="local", output_path=str(tmp_path / "logs"),
                                   stories_data=stories)

        assert json.load(open(tmp_path / "latest" / "stories.json")) == stories
        assert json.load(open(tmp_path / "stories.json")) == stories
        mock_upload.assert_not_called()


class TestEmitMomentum:
    STORIES = {"version": "0.3.0", "story_count": 100, "article_count": 500, "stories": []}
    MOMENTUM = {"version": "0.3.0", "generated": "2025-01-16T10:30:45", "window_days": 14,
                "stories": {}}
    STATE = {"version": "0.3.0", "updated": "2025-01-16", "stories": {}}

    @patch("newvelles.feed.log.read_json_from_s3", return_value=None)
    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_momentum_uploads_after_stories(self, mock_datetime, mock_upload, mock_read):
        from newvelles.feed.log import _S3_BUCKET, emit_visualization
        mock_datetime.return_value = "2025-01-16T10:30:45"

        emit_visualization({}, writers="s3", stories_data=self.STORIES,
                           momentum_doc=self.MOMENTUM, momentum_state=self.STATE)

        calls = mock_upload.call_args_list
        names = [c.kwargs["file_name"] for c in calls]
        assert names == [
            "newvelles_visualization_0.2.1_2025-01-16T10:30:45.json",
            "latest_news.json",
            "latest_news_metadata.json",
            "stories.json",
            "momentum.json",
            "momentum_state.json",
        ]
        momentum_call = calls[4]
        assert momentum_call.kwargs["bucket_name"] == _S3_PUBLIC_BUCKET
        assert momentum_call.kwargs["public_read"] is True
        assert json.loads(momentum_call.kwargs["string_byte"]) == self.MOMENTUM
        state_call = calls[5]
        assert state_call.kwargs["bucket_name"] == _S3_BUCKET  # private
        assert state_call.kwargs.get("public_read", False) is False

    @patch("newvelles.feed.log.read_json_from_s3")
    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_blocked_gate_blocks_momentum_and_state_too(self, mock_datetime, mock_upload, mock_read):
        """An anomalous run must not pollute the identity state."""
        from newvelles.feed.log import emit_visualization
        mock_datetime.return_value = "2025-01-16T10:30:45"
        mock_read.return_value = {"story_count": 175}
        bad = {"version": "0.3.0", "story_count": 400, "article_count": 500, "stories": []}

        emit_visualization({}, writers="s3", stories_data=bad,
                           momentum_doc=self.MOMENTUM, momentum_state=self.STATE)

        names = [c.kwargs["file_name"] for c in mock_upload.call_args_list]
        assert "stories.json" not in names
        assert "momentum.json" not in names
        assert "momentum_state.json" not in names

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_local_writer_writes_momentum_and_state(self, mock_datetime, mock_upload,
                                                    tmp_path, monkeypatch):
        from newvelles.feed import log as log_mod
        mock_datetime.return_value = "2025-01-16T10:30:45"
        monkeypatch.setattr(log_mod, "_LATEST_PATH", str(tmp_path / "latest"))
        monkeypatch.chdir(tmp_path)

        log_mod.emit_visualization({}, writers="local", output_path=str(tmp_path / "logs"),
                                   stories_data=self.STORIES,
                                   momentum_doc=self.MOMENTUM, momentum_state=self.STATE)

        assert json.load(open(tmp_path / "momentum.json")) == self.MOMENTUM
        assert json.load(open(tmp_path / "latest" / "momentum.json")) == self.MOMENTUM
        assert json.load(open(tmp_path / "cache" / "momentum_state.json")) == self.STATE
        mock_upload.assert_not_called()

    @patch("newvelles.feed.log.emit_visualization")
    def test_log_s3_passes_momentum_through(self, mock_emit):
        mock_emit.return_value = "x.json"
        log_s3({}, stories_data=self.STORIES, momentum_doc=self.MOMENTUM,
               momentum_state=self.STATE)
        mock_emit.assert_called_once_with(
            {}, writers="s3", stories_data=self.STORIES,
            momentum_doc=self.MOMENTUM, momentum_state=self.STATE)
