"""Tests for the pre-publish sanity gate on stories.json.

The gate refuses to publish when the story count deviates more than 60% from
the previous published run, or when the article count falls below a floor —
schema validation alone passes happily on a run that produced 3 stories or 400.
"""

import json
from unittest.mock import patch

import pytest

from newvelles.utils.publish_gate import (DEFAULT_MAX_DEVIATION, DEFAULT_MIN_ARTICLES,
                                          evaluate_stories_gate)


def _doc(story_count=180, article_count=600):
    return {"version": "0.3.0", "story_count": story_count, "article_count": article_count}


class TestEvaluateStoriesGate:
    def test_first_publish_passes_without_previous(self):
        ok, reason = evaluate_stories_gate(_doc(), previous_story_count=None)
        assert ok is True
        assert reason == ""

    def test_normal_run_passes(self):
        ok, _ = evaluate_stories_gate(_doc(story_count=180), previous_story_count=175)
        assert ok is True

    def test_story_count_spike_blocks(self):
        # 175 -> 400 is a +128% deviation
        ok, reason = evaluate_stories_gate(_doc(story_count=400), previous_story_count=175)
        assert ok is False
        assert "deviat" in reason and "400" in reason and "175" in reason

    def test_story_count_collapse_blocks(self):
        # 175 -> 6 is a -96% deviation
        ok, reason = evaluate_stories_gate(_doc(story_count=6), previous_story_count=175)
        assert ok is False

    def test_deviation_boundary_is_exclusive(self):
        # exactly 60% deviation is allowed; "more than 60%" blocks
        ok, _ = evaluate_stories_gate(_doc(story_count=160), previous_story_count=100)
        assert ok is True
        ok, _ = evaluate_stories_gate(_doc(story_count=161), previous_story_count=100)
        assert ok is False

    def test_article_floor_blocks(self):
        ok, reason = evaluate_stories_gate(
            _doc(article_count=DEFAULT_MIN_ARTICLES - 1), previous_story_count=None)
        assert ok is False
        assert "article" in reason.lower()

    def test_article_floor_boundary_passes(self):
        ok, _ = evaluate_stories_gate(
            _doc(article_count=DEFAULT_MIN_ARTICLES), previous_story_count=None)
        assert ok is True

    def test_zero_previous_count_does_not_divide_by_zero(self):
        ok, _ = evaluate_stories_gate(_doc(story_count=180), previous_story_count=0)
        assert ok is True  # nothing meaningful to compare against

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("NEWVELLES_GATE_MIN_ARTICLES", "700")
        monkeypatch.setenv("NEWVELLES_GATE_MAX_DEVIATION", "0.1")
        ok, _ = evaluate_stories_gate(_doc(article_count=600), previous_story_count=None)
        assert ok is False  # floor raised above the run's article count
        monkeypatch.setenv("NEWVELLES_GATE_MIN_ARTICLES", "50")
        ok, _ = evaluate_stories_gate(_doc(story_count=120), previous_story_count=100)
        assert ok is False  # 20% deviation vs 10% allowance

    def test_defaults_exported(self):
        assert DEFAULT_MAX_DEVIATION == 0.6
        assert DEFAULT_MIN_ARTICLES == 50


class TestGateWiredIntoEmit:
    """The gate guards only the public stories.json upload; legacy files always publish."""

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log.read_json_from_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_blocked_gate_skips_stories_upload_only(self, mock_dt, mock_read, mock_upload, capsys):
        from newvelles.feed.log import emit_visualization
        mock_dt.return_value = "2025-01-16T10:30:45"
        mock_read.return_value = {"story_count": 175}  # previous published run

        emit_visualization({}, writers="s3", stories_data=_doc(story_count=400))

        names = [c.kwargs["file_name"] for c in mock_upload.call_args_list]
        assert "stories.json" not in names
        assert names == [
            "newvelles_visualization_0.2.1_2025-01-16T10:30:45.json",
            "latest_news.json",
            "latest_news_metadata.json",
        ]
        assert "sanity gate" in capsys.readouterr().out.lower()

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log.read_json_from_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_passing_gate_uploads_stories(self, mock_dt, mock_read, mock_upload):
        from newvelles.feed.log import emit_visualization
        mock_dt.return_value = "2025-01-16T10:30:45"
        mock_read.return_value = {"story_count": 175}

        emit_visualization({}, writers="s3", stories_data=_doc(story_count=180))

        names = [c.kwargs["file_name"] for c in mock_upload.call_args_list]
        assert "stories.json" in names

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log.read_json_from_s3")
    @patch("newvelles.feed.log._current_datetime")
    def test_missing_previous_file_publishes(self, mock_dt, mock_read, mock_upload):
        """First deploy: no stories.json in the bucket yet."""
        from newvelles.feed.log import emit_visualization
        mock_dt.return_value = "2025-01-16T10:30:45"
        mock_read.return_value = None

        emit_visualization({}, writers="s3", stories_data=_doc())

        names = [c.kwargs["file_name"] for c in mock_upload.call_args_list]
        assert "stories.json" in names

    @patch("newvelles.feed.log.upload_to_s3")
    @patch("newvelles.feed.log.read_json_from_s3")
    def test_local_writer_never_consults_gate(self, mock_read, mock_upload, tmp_path, monkeypatch):
        from newvelles.feed import log as log_mod
        monkeypatch.setattr(log_mod, "_LATEST_PATH", str(tmp_path / "latest"))
        monkeypatch.chdir(tmp_path)

        log_mod.emit_visualization({}, writers="local", output_path=str(tmp_path / "logs"),
                                   stories_data=_doc(story_count=400))

        mock_read.assert_not_called()
        assert json.load(open(tmp_path / "stories.json"))["story_count"] == 400


class TestReadJsonFromS3:
    def test_returns_parsed_json(self):
        from unittest.mock import MagicMock
        from newvelles.utils.s3 import read_json_from_s3
        with patch("newvelles.utils.s3.boto3") as mock_boto:
            body = MagicMock()
            body.read.return_value = b'{"story_count": 42}'
            mock_boto.client.return_value.get_object.return_value = {"Body": body}
            assert read_json_from_s3("bucket", "stories.json") == {"story_count": 42}

    def test_returns_none_on_client_error(self):
        from botocore.exceptions import ClientError
        from newvelles.utils.s3 import read_json_from_s3
        with patch("newvelles.utils.s3.boto3") as mock_boto:
            mock_boto.client.return_value.get_object.side_effect = ClientError(
                {"Error": {"Code": "NoSuchKey"}}, "GetObject")
            assert read_json_from_s3("bucket", "missing.json") is None

    def test_returns_none_on_bad_json(self):
        from unittest.mock import MagicMock
        from newvelles.utils.s3 import read_json_from_s3
        with patch("newvelles.utils.s3.boto3") as mock_boto:
            body = MagicMock()
            body.read.return_value = b"not json"
            mock_boto.client.return_value.get_object.return_value = {"Body": body}
            assert read_json_from_s3("bucket", "stories.json") is None
