"""Tests for monitoring dashboard visualizer module."""

from datetime import datetime, timedelta, timezone
from io import StringIO

import pytest
from rich.console import Console

from newvelles.monitor.visualizer import (
    _calculate_time_ago,
    _get_status_indicator,
    display_dashboard,
    display_header,
    display_summary_stats,
    plot_articles_per_day,
    plot_groups_per_update,
    plot_independent_news_per_day,
)


class TestTimeAgoCalculation:
    """Test human-readable time difference calculations."""

    def test_just_now(self):
        """Test time difference less than 1 minute shows 'just now'."""
        now = datetime.now(timezone.utc)
        timestamp = now - timedelta(seconds=30)
        result = _calculate_time_ago(timestamp.strftime("%Y-%m-%dT%H:%M:%S"))
        assert result == "just now"

    def test_minutes_ago(self):
        """Test time difference in minutes."""
        now = datetime.now(timezone.utc)
        timestamp = now - timedelta(minutes=5)
        result = _calculate_time_ago(timestamp.strftime("%Y-%m-%dT%H:%M:%S"))
        assert result == "5 minutes ago"

    def test_one_minute_ago(self):
        """Test singular 'minute' for 1 minute ago."""
        now = datetime.now(timezone.utc)
        timestamp = now - timedelta(minutes=1)
        result = _calculate_time_ago(timestamp.strftime("%Y-%m-%dT%H:%M:%S"))
        assert result == "1 minute ago"

    def test_hours_ago(self):
        """Test time difference in hours."""
        now = datetime.now(timezone.utc)
        timestamp = now - timedelta(hours=2)
        result = _calculate_time_ago(timestamp.strftime("%Y-%m-%dT%H:%M:%S"))
        assert result == "2 hours ago"

    def test_one_hour_ago(self):
        """Test singular 'hour' for 1 hour ago."""
        now = datetime.now(timezone.utc)
        timestamp = now - timedelta(hours=1)
        result = _calculate_time_ago(timestamp.strftime("%Y-%m-%dT%H:%M:%S"))
        assert result == "1 hour ago"

    def test_days_ago(self):
        """Test time difference in days."""
        now = datetime.now(timezone.utc)
        timestamp = now - timedelta(days=3)
        result = _calculate_time_ago(timestamp.strftime("%Y-%m-%dT%H:%M:%S"))
        assert result == "3 days ago"

    def test_one_day_ago(self):
        """Test singular 'day' for 1 day ago."""
        now = datetime.now(timezone.utc)
        timestamp = now - timedelta(days=1)
        result = _calculate_time_ago(timestamp.strftime("%Y-%m-%dT%H:%M:%S"))
        assert result == "1 day ago"

    def test_invalid_timestamp(self):
        """Test invalid timestamp returns 'unknown'."""
        result = _calculate_time_ago("invalid-timestamp")
        assert result == "unknown"


class TestStatusIndicator:
    """Test status indicator logic."""

    def test_healthy_status_recent_update(self):
        """Test healthy status for recent update (< 7 hours)."""
        now = datetime.now(timezone.utc)
        timestamp = now - timedelta(hours=2)
        status_text, status_emoji = _get_status_indicator(
            timestamp.strftime("%Y-%m-%dT%H:%M:%S")
        )
        assert status_text == "HEALTHY"
        assert status_emoji == "🟢"

    def test_stale_status_old_update(self):
        """Test stale status for old update (> 7 hours)."""
        now = datetime.now(timezone.utc)
        timestamp = now - timedelta(hours=8)
        status_text, status_emoji = _get_status_indicator(
            timestamp.strftime("%Y-%m-%dT%H:%M:%S")
        )
        assert status_text == "STALE"
        assert status_emoji == "🔴"

    def test_edge_case_exactly_seven_hours(self):
        """Test edge case at exactly 7 hours boundary."""
        now = datetime.now(timezone.utc)
        timestamp = now - timedelta(hours=7, minutes=1)
        status_text, status_emoji = _get_status_indicator(
            timestamp.strftime("%Y-%m-%dT%H:%M:%S")
        )
        assert status_text == "STALE"
        assert status_emoji == "🔴"

    def test_unknown_status_invalid_timestamp(self):
        """Test unknown status for invalid timestamp."""
        status_text, status_emoji = _get_status_indicator("invalid-timestamp")
        assert status_text == "UNKNOWN"
        assert status_emoji == "⚪"


class TestDisplayHeader:
    """Test dashboard header display."""

    def test_display_header_renders_metadata(self):
        """Test header displays metadata correctly."""
        console = Console(file=StringIO(), width=80)
        metadata = {"datetime": "2026-04-16T13:14:38", "version": "0.2.1"}

        display_header(console, metadata)
        output = console.file.getvalue()

        assert "Newvelles Production Monitoring Dashboard" in output
        assert "2026-04-16T13:14:38" in output
        assert "0.2.1" in output

    def test_display_header_handles_missing_data(self):
        """Test header handles missing metadata gracefully."""
        console = Console(file=StringIO(), width=80)
        metadata = {}

        display_header(console, metadata)
        output = console.file.getvalue()

        assert "Unknown" in output


class TestDisplaySummaryStats:
    """Test summary statistics display."""

    def test_display_summary_stats_renders_all_metrics(self):
        """Test summary stats displays all metrics."""
        console = Console(file=StringIO(), width=120)
        stats = {
            "total_updates": 8614,
            "first_update": "2021-07-10 06:00:00",
            "latest_update": "2026-04-16 13:14:38",
            "avg_articles_per_update": 150.2,
            "avg_groups_per_update": 45.8,
        }

        display_summary_stats(console, stats)
        output = console.file.getvalue()

        assert "Overall Statistics" in output
        assert "8,614" in output
        assert "2021-07-10 06:00:00" in output
        assert "2026-04-16 13:14:38" in output
        assert "150.2" in output
        assert "45.8" in output

    def test_display_summary_stats_handles_missing_data(self):
        """Test summary stats handles missing data with defaults."""
        console = Console(file=StringIO(), width=120)
        stats = {}

        display_summary_stats(console, stats)
        output = console.file.getvalue()

        assert "Overall Statistics" in output
        assert "0" in output or "Unknown" in output


class TestPlotFunctions:
    """Test plotting functions."""

    def test_plot_articles_per_day_with_data(self):
        """Test articles per day plot with valid data."""
        daily_metrics = {
            "2026-04-14": {"updates": [{"total_articles": 150, "total_groups": 45}]},
            "2026-04-15": {"updates": [{"total_articles": 155, "total_groups": 48}]},
            "2026-04-16": {"updates": [{"total_articles": 160, "total_groups": 50}]},
        }

        # Should not raise any exceptions
        plot_articles_per_day(daily_metrics, days=7)

    def test_plot_articles_per_day_empty_data(self, capsys):
        """Test articles per day plot handles empty data."""
        plot_articles_per_day({}, days=7)
        captured = capsys.readouterr()
        assert "No data available" in captured.out

    def test_plot_groups_per_update_with_data(self):
        """Test groups per update plot with valid data."""
        daily_metrics = {
            "2026-04-14": {"updates": [{"total_articles": 150, "total_groups": 45}]},
            "2026-04-15": {"updates": [{"total_articles": 155, "total_groups": 48}]},
        }

        # Should not raise any exceptions
        plot_groups_per_update(daily_metrics, days=7)

    def test_plot_groups_per_update_empty_data(self, capsys):
        """Test groups per update plot handles empty data."""
        plot_groups_per_update({}, days=7)
        captured = capsys.readouterr()
        assert "No data available" in captured.out

    def test_plot_independent_news_per_day_with_data(self):
        """Test independent news plot with valid data."""
        daily_metrics = {
            "2026-04-14": {
                "updates": [
                    {"total_articles": 150, "total_groups": 45, "sub_groups": 30}
                ]
            },
            "2026-04-15": {
                "updates": [
                    {"total_articles": 155, "total_groups": 48, "sub_groups": 32}
                ]
            },
        }

        # Should not raise any exceptions
        plot_independent_news_per_day(daily_metrics, days=7)

    def test_plot_independent_news_per_day_empty_data(self, capsys):
        """Test independent news plot handles empty data."""
        plot_independent_news_per_day({}, days=7)
        captured = capsys.readouterr()
        assert "No data available" in captured.out


class TestDisplayDashboard:
    """Test main dashboard display orchestrator."""

    def test_display_dashboard_integrates_all_components(self):
        """Test dashboard integrates header, stats, and plots."""
        metadata = {"datetime": "2026-04-16T13:14:38", "version": "0.2.1"}

        stats = {
            "total_updates": 8614,
            "first_update": "2021-07-10 06:00:00",
            "latest_update": "2026-04-16 13:14:38",
            "avg_articles_per_update": 150.2,
            "avg_groups_per_update": 45.8,
        }

        daily_metrics = {
            "2026-04-14": {
                "updates": [
                    {"total_articles": 150, "total_groups": 45, "sub_groups": 30}
                ]
            },
            "2026-04-15": {
                "updates": [
                    {"total_articles": 155, "total_groups": 48, "sub_groups": 32}
                ]
            },
        }

        # Should not raise any exceptions
        display_dashboard(metadata, stats, daily_metrics, days=7)

    def test_display_dashboard_handles_empty_data(self):
        """Test dashboard handles empty data gracefully."""
        # Should not raise any exceptions
        display_dashboard({}, {}, {}, days=7)
