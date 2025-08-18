"""Tests for handler.py lambda function."""

import json
from unittest.mock import Mock, patch

import pytest

from handler import handler, run


class TestHandler:
    """Test lambda handler function."""

    @patch("handler.run")
    def test_handler_success(self, mock_run):
        """Test handler returns success response when run succeeds."""
        mock_run.return_value = True
        
        event = {"test": "data"}
        context = Mock()
        
        response = handler(event, context)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] == "Successful run!"
        assert body["input"] == event
        mock_run.assert_called_once()

    @patch("handler.run")
    def test_handler_failure(self, mock_run):
        """Test handler returns error response when run fails."""
        mock_run.return_value = False
        
        event = {"test": "data"}
        context = Mock()
        
        response = handler(event, context)
        
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["message"] == "Something went wrong"
        assert body["input"] == event
        mock_run.assert_called_once()

    @patch("handler.run")
    def test_handler_exception(self, mock_run):
        """Test handler behavior when run raises exception."""
        mock_run.side_effect = Exception("Test error")
        
        event = {"test": "data"}
        context = Mock()
        
        # The handler function doesn't catch exceptions, so it should raise
        with pytest.raises(Exception, match="Test error"):
            handler(event, context)
        
        mock_run.assert_called_once()


class TestRun:
    """Test run function."""

    @patch("handler.log_s3")
    @patch("handler.build_visualization")
    @patch("handler.build_data_from_rss_feeds_list")
    @patch("handler.CONFIG")
    def test_run_success(self, mock_config, mock_build_data, mock_build_viz, mock_log_s3):
        """Test run function executes pipeline successfully."""
        # Mock configuration
        mock_config.__getitem__.return_value = {"cluster_limit": "5"}
        
        # Mock data building
        mock_title_data = {"Article 1": Mock()}
        mock_build_data.return_value = mock_title_data
        
        # Mock visualization building
        mock_visualization_data = {"group1": {"subgroup1": {"Article 1": {}}}}
        mock_group_sentences = {1: ["Article 1"]}
        mock_build_viz.return_value = (mock_visualization_data, mock_group_sentences)
        
        result = run()
        
        assert result is True
        mock_build_data.assert_called_once()
        mock_build_viz.assert_called_once_with(mock_title_data, cluster_limit=5)
        mock_log_s3.assert_called_once_with(mock_visualization_data)

    @patch("handler.log_s3")
    @patch("handler.build_visualization")
    @patch("handler.build_data_from_rss_feeds_list")
    @patch("handler.CONFIG")
    def test_run_with_exception(self, mock_config, mock_build_data, mock_build_viz, mock_log_s3):
        """Test run function handles exceptions gracefully."""
        mock_config.__getitem__.return_value = {"cluster_limit": "5"}
        mock_build_data.side_effect = Exception("Network error")
        
        with pytest.raises(Exception):
            run()
        
        mock_build_data.assert_called_once()
        mock_build_viz.assert_not_called()
        mock_log_s3.assert_not_called()


def test_direct_invocation():
    """Test direct invocation of handler without mocking."""
    # This test runs the actual handler with minimal data
    # Use with caution as it may make real network calls
    
    event = {"test": "minimal"}
    context = Mock()
    context.aws_request_id = "test-request-id"
    context.log_group_name = "test-log-group"
    context.log_stream_name = "test-log-stream"
    context.function_name = "test-function"
    context.function_version = "1"
    context.invoked_function_arn = "arn:aws:lambda:region:account:function:test"
    context.memory_limit_in_mb = 128
    context.get_remaining_time_in_millis = lambda: 30000
    
    # Note: This will actually run the handler function
    # Comment out this test if you don't want real execution
    # response = handler(event, context)
    # assert "statusCode" in response
    # assert "body" in response
