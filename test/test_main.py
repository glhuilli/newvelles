"""Tests for newvelles.__main__ module."""

import tempfile
from unittest.mock import Mock, call, patch

import pytest
from click.testing import CliRunner

from newvelles.__main__ import main, run, run_daemon


class TestRun:
    """Test run function."""

    @patch("newvelles.__main__.print_viz")
    @patch("newvelles.__main__.print_sorted_grouped_titles")
    @patch("newvelles.__main__.log_groups")
    @patch("newvelles.__main__.log_visualization")
    @patch("newvelles.__main__.build_visualization")
    @patch("newvelles.__main__.build_data_from_rss_feeds")
    @patch("newvelles.__main__.CONFIG")
    @patch("newvelles.__main__.DEBUG", False)
    def test_run_basic(
        self,
        mock_config,
        mock_build_data,
        mock_build_viz,
        mock_log_viz,
        mock_log_groups,
        mock_print_titles,
        mock_print_viz,
    ):
        """Test basic functionality of run function."""
        # Mock configuration
        mock_config.__getitem__.return_value = {"cluster_limit": "2"}

        # Mock data building
        mock_title_data = {"Article 1": Mock()}
        mock_build_data.return_value = mock_title_data

        # Mock visualization building
        mock_visualization_data = {"group1": {"subgroup1": {"Article 1": {}}}}
        mock_group_sentences = {1: ["Article 1"]}
        mock_build_viz.return_value = (mock_visualization_data, mock_group_sentences)

        rss_file = "test_rss.txt"

        run(rss_file, s3=False)

        # Verify the pipeline was called correctly
        mock_build_data.assert_called_once_with(rss_file)
        mock_build_viz.assert_called_once_with(mock_title_data, cluster_limit=2)
        mock_log_viz.assert_called_once_with(mock_visualization_data, s3=False)
        mock_log_groups.assert_called_once_with(mock_group_sentences)

        # Debug prints should not be called when DEBUG=False
        mock_print_titles.assert_not_called()
        mock_print_viz.assert_not_called()

    @patch("newvelles.__main__.print_viz")
    @patch("newvelles.__main__.print_sorted_grouped_titles")
    @patch("newvelles.__main__.log_groups")
    @patch("newvelles.__main__.log_visualization")
    @patch("newvelles.__main__.build_visualization")
    @patch("newvelles.__main__.build_data_from_rss_feeds")
    @patch("newvelles.__main__.CONFIG")
    @patch("newvelles.__main__.DEBUG", True)
    def test_run_debug_mode(
        self,
        mock_config,
        mock_build_data,
        mock_build_viz,
        mock_log_viz,
        mock_log_groups,
        mock_print_titles,
        mock_print_viz,
    ):
        """Test run function with debug mode enabled."""
        # Mock configuration
        mock_config.__getitem__.return_value = {"cluster_limit": "5"}

        # Mock data
        mock_title_data = {"Article 1": Mock()}
        mock_build_data.return_value = mock_title_data

        mock_visualization_data = {"group1": {"subgroup1": {"Article 1": {}}}}
        mock_group_sentences = {1: ["Article 1"]}
        mock_build_viz.return_value = (mock_visualization_data, mock_group_sentences)

        rss_file = "test_rss.txt"

        run(rss_file, s3=True)

        # Verify debug prints are called when DEBUG=True
        mock_print_titles.assert_called_once_with(mock_group_sentences)
        mock_print_viz.assert_called_once_with(mock_visualization_data)

        # Verify S3 logging is enabled
        mock_log_viz.assert_called_once_with(mock_visualization_data, s3=True)

    @patch("newvelles.__main__.build_data_from_rss_feeds")
    @patch("newvelles.__main__.CONFIG")
    def test_run_cluster_limit_conversion(self, mock_config, mock_build_data):
        """Test that cluster_limit is properly converted to int."""
        # Mock configuration with string value
        mock_config.__getitem__.return_value = {"cluster_limit": "10"}
        mock_build_data.return_value = {}

        with patch("newvelles.__main__.build_visualization") as mock_build_viz, patch(
            "newvelles.__main__.log_visualization"
        ), patch("newvelles.__main__.log_groups"):

            mock_build_viz.return_value = ({}, {})

            run("test.txt", s3=False)

            # Verify cluster_limit is converted to int
            mock_build_viz.assert_called_once_with({}, cluster_limit=10)


class TestRunDaemon:
    """Test run_daemon function."""

    @patch("newvelles.__main__.time.sleep")
    @patch("newvelles.__main__.run")
    @patch("newvelles.__main__.CONFIG")
    def test_run_daemon_single_iteration(self, mock_config, mock_run, mock_sleep):
        """Test run_daemon for a single iteration."""
        # Mock configuration
        mock_config.__getitem__.return_value = {"wait_time": "1", "debug": "False"}

        # Mock sleep to raise exception after first iteration to prevent infinite loop
        mock_sleep.side_effect = KeyboardInterrupt()

        rss_file = "test_rss.txt"

        with pytest.raises(KeyboardInterrupt):
            run_daemon(rss_file, s3=False)

        # Verify run was called once
        mock_run.assert_called_once_with(rss_file, False)

        # Verify sleep was called with correct wait time (1 minute = 60 seconds)
        mock_sleep.assert_called_once_with(60)

    @patch("newvelles.__main__.time.sleep")
    @patch("newvelles.__main__.run")
    @patch("newvelles.__main__.CONFIG")
    def test_run_daemon_multiple_iterations(self, mock_config, mock_run, mock_sleep):
        """Test run_daemon for multiple iterations."""
        # Mock configuration
        mock_config.__getitem__.return_value = {"wait_time": "0.5", "debug": "False"}

        # Mock sleep to allow 3 iterations before stopping
        call_count = 0

        def mock_sleep_side_effect(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                raise KeyboardInterrupt()

        mock_sleep.side_effect = mock_sleep_side_effect

        rss_file = "test_rss.txt"

        with pytest.raises(KeyboardInterrupt):
            run_daemon(rss_file, s3=True)

        # Verify run was called 3 times
        assert mock_run.call_count == 3
        expected_calls = [call(rss_file, True)] * 3
        mock_run.assert_has_calls(expected_calls)

        # Verify sleep was called 3 times with correct wait time (0.5 minutes = 30 seconds)
        assert mock_sleep.call_count == 3
        expected_sleep_calls = [call(30)] * 3
        mock_sleep.assert_has_calls(expected_sleep_calls)

    @patch("newvelles.__main__.time.sleep")
    @patch("newvelles.__main__.run")
    @patch("newvelles.__main__.CONFIG")
    @patch("builtins.print")
    def test_run_daemon_with_print_statements(
        self, mock_print, mock_config, mock_run, mock_sleep
    ):
        """Test run_daemon print statements."""
        mock_config.__getitem__.return_value = {"wait_time": "2", "debug": "True"}
        mock_sleep.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            run_daemon("test.txt", s3=False)

        # Check print statements were called (debug mode is True)
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any("Latest run:" in call for call in print_calls)
        assert any("waiting for 120 seconds" in call for call in print_calls)

    @patch("newvelles.__main__.time.sleep")
    @patch("newvelles.__main__.run")
    @patch("newvelles.__main__.CONFIG")
    def test_run_daemon_wait_time_conversion(self, mock_config, mock_run, mock_sleep):
        """Test that wait_time is properly converted to int."""
        # Mock configuration with string value
        mock_config.__getitem__.return_value = {"wait_time": "0.75", "debug": "False"}
        mock_sleep.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            run_daemon("test.txt", s3=False)

        # Verify wait_time is converted to int (0.75 minutes = 45 seconds)
        mock_sleep.assert_called_once_with(45)


class TestMain:
    """Test main CLI function."""

    @patch("newvelles.__main__.run")
    def test_main_basic_run(self, mock_run):
        """Test main function with basic run (no daemon)."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("https://example.com/feed.xml\n")
            rss_file = f.name

        try:
            result = runner.invoke(main, ["--rss_file", rss_file])

            assert result.exit_code == 0
            mock_run.assert_called_once_with(rss_file, False)
        finally:
            import os

            os.unlink(rss_file)

    @patch("newvelles.__main__.run_daemon")
    def test_main_daemon_mode(self, mock_run_daemon):
        """Test main function with daemon mode."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("https://example.com/feed.xml\n")
            rss_file = f.name

        try:
            result = runner.invoke(main, ["--rss_file", rss_file, "--daemon"])

            assert result.exit_code == 0
            mock_run_daemon.assert_called_once_with(rss_file, False)
        finally:
            import os

            os.unlink(rss_file)

    @patch("newvelles.__main__.run")
    def test_main_with_s3_flag(self, mock_run):
        """Test main function with S3 flag."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("https://example.com/feed.xml\n")
            rss_file = f.name

        try:
            result = runner.invoke(main, ["--rss_file", rss_file, "--s3"])

            assert result.exit_code == 0
            mock_run.assert_called_once_with(rss_file, True)
        finally:
            import os

            os.unlink(rss_file)

    @patch("newvelles.__main__.run_daemon")
    def test_main_daemon_and_s3(self, mock_run_daemon):
        """Test main function with both daemon and S3 flags."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("https://example.com/feed.xml\n")
            rss_file = f.name

        try:
            result = runner.invoke(main, ["--rss_file", rss_file, "--daemon", "--s3"])

            assert result.exit_code == 0
            mock_run_daemon.assert_called_once_with(rss_file, True)
        finally:
            import os

            os.unlink(rss_file)

    def test_main_default_rss_file(self):
        """Test main function with default RSS file."""
        runner = CliRunner()

        with patch("newvelles.__main__.run") as mock_run:
            result = runner.invoke(main, [])

            assert result.exit_code == 0
            # Should use default RSS file
            mock_run.assert_called_once_with("./data/rss_source.txt", False)

    @patch("newvelles.__main__.run")
    def test_main_help_message(self, mock_run):
        """Test main function help message."""
        runner = CliRunner()

        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "rss_file" in result.output
        assert "daemon" in result.output
        assert "s3" in result.output

        # Run should not be called when showing help
        mock_run.assert_not_called()

    @patch("newvelles.__main__.run")
    def test_main_invalid_file(self, mock_run):
        """Test main function behavior with non-existent file."""
        runner = CliRunner()

        # Use a file that doesn't exist
        result = runner.invoke(main, ["--rss_file", "/non/existent/file.txt"])

        # Click should still call the function, but the underlying functions should handle the error
        assert (
            result.exit_code == 0
        )  # Click exits successfully even if file doesn't exist
        mock_run.assert_called_once_with("/non/existent/file.txt", False)
