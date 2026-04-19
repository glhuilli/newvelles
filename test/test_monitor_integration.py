"""Integration tests for the monitoring dashboard."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from newvelles.monitor.cache import CacheManager
from newvelles.monitor.cli import monitor
from newvelles.monitor.metrics import (
    aggregate_daily_metrics,
    extract_file_metrics,
    get_overall_statistics,
)


@pytest.fixture
def sample_visualization_data():
    """Sample visualization data for testing."""
    return {
        "Top News Group": {
            "Sub Group 1": {
                "Article 1": {
                    "title": "Article 1",
                    "link": "https://example.com/1",
                    "timestamp": "2026-04-18T10:00:00",
                    "source": "https://example.com/rss",
                    "title_detail_base": "https://example.com",
                }
            },
            "Sub Group 2": {
                "Article 2": {
                    "title": "Article 2",
                    "link": "https://example.com/2",
                    "timestamp": "2026-04-18T11:00:00",
                    "source": "https://example.com/rss2",
                    "title_detail_base": "https://example.com",
                }
            },
        }
    }


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestMonitoringIntegration:
    """Integration tests for the complete monitoring workflow."""

    def test_full_workflow(self, sample_visualization_data, temp_cache_dir):
        """Test complete workflow: extract metrics -> cache -> aggregate -> stats."""
        # Initialize cache manager
        cache = CacheManager(temp_cache_dir)

        # Extract metrics from sample data
        filename = "newvelles_visualization_0.2.1_2026-04-18T10:00:00.json"
        metrics = extract_file_metrics(sample_visualization_data, filename)

        # Verify extracted metrics
        assert metrics["total_articles"] == 2
        assert metrics["total_groups"] == 1  # Only top-level groups (not including sub-groups)
        assert metrics["top_level_groups"] == 1
        assert metrics["sub_groups"] == 2
        assert metrics["subgroups_per_top_group"] == 2.0  # 2 sub-groups / 1 top-level = 2.0

        # Add to cache
        cache.add_file(filename, {
            "processed": True,
            "articles": metrics["total_articles"],
            "groups": metrics["total_groups"],
            "timestamp": metrics["timestamp"],
        })

        # Verify file in cache
        known_files = cache.get_known_files()
        assert filename in known_files

        # Update daily metrics
        date = "2026-04-18"
        cache.update_daily_metrics(date, metrics)

        # Load daily metrics
        daily_metrics = cache.load_daily_metrics()
        assert date in daily_metrics
        assert daily_metrics[date]["daily_total_articles"] == 2

        # Calculate overall statistics
        stats = get_overall_statistics(daily_metrics)
        assert stats["total_updates"] == 1
        assert stats["total_days"] == 1

    def test_multiple_updates_same_day(self, sample_visualization_data, temp_cache_dir):
        """Test handling multiple updates on the same day."""
        cache = CacheManager(temp_cache_dir)

        # Process multiple files for the same day
        for hour in ["10:00:00", "16:00:00", "22:00:00"]:
            filename = f"newvelles_visualization_0.2.1_2026-04-18T{hour}.json"
            metrics = extract_file_metrics(sample_visualization_data, filename)

            cache.add_file(filename, {
                "processed": True,
                "articles": metrics["total_articles"],
                "groups": metrics["total_groups"],
                "timestamp": metrics["timestamp"],
            })

            cache.update_daily_metrics("2026-04-18", metrics)

        # Verify aggregations
        daily_metrics = cache.load_daily_metrics()
        assert len(daily_metrics["2026-04-18"]["updates"]) == 3
        assert daily_metrics["2026-04-18"]["daily_total_articles"] == 6  # 2 * 3 updates

    def test_cache_persistence(self, sample_visualization_data, temp_cache_dir):
        """Test that cache persists across CacheManager instances."""
        # Create first cache manager and add data
        cache1 = CacheManager(temp_cache_dir)
        filename = "newvelles_visualization_0.2.1_2026-04-18T10:00:00.json"
        metrics = extract_file_metrics(sample_visualization_data, filename)

        cache1.add_file(filename, {
            "processed": True,
            "articles": metrics["total_articles"],
            "groups": metrics["total_groups"],
            "timestamp": metrics["timestamp"],
        })
        cache1.update_daily_metrics("2026-04-18", metrics)

        # Create second cache manager (simulates new run)
        cache2 = CacheManager(temp_cache_dir)

        # Verify data is still there
        known_files = cache2.get_known_files()
        assert filename in known_files

        daily_metrics = cache2.load_daily_metrics()
        assert "2026-04-18" in daily_metrics

    def test_incremental_cache_updates(self, sample_visualization_data, temp_cache_dir):
        """Test incremental updates to cache."""
        cache = CacheManager(temp_cache_dir)

        # Add first file
        file1 = "newvelles_visualization_0.2.1_2026-04-17T10:00:00.json"
        metrics1 = extract_file_metrics(sample_visualization_data, file1)
        cache.add_file(file1, {
            "processed": True,
            "articles": metrics1["total_articles"],
            "groups": metrics1["total_groups"],
            "timestamp": metrics1["timestamp"],
        })

        known_files_1 = cache.get_known_files()
        assert len(known_files_1) == 1

        # Add second file (incremental)
        file2 = "newvelles_visualization_0.2.1_2026-04-18T10:00:00.json"
        metrics2 = extract_file_metrics(sample_visualization_data, file2)
        cache.add_file(file2, {
            "processed": True,
            "articles": metrics2["total_articles"],
            "groups": metrics2["total_groups"],
            "timestamp": metrics2["timestamp"],
        })

        known_files_2 = cache.get_known_files()
        assert len(known_files_2) == 2
        assert file1 in known_files_2
        assert file2 in known_files_2

    @patch("newvelles.monitor.cli.fetch_incremental_data")
    @patch("newvelles.monitor.cli.get_latest_metadata")
    def test_cli_update_command(self, mock_metadata, mock_fetch, temp_cache_dir):
        """Test CLI update command."""
        from click.testing import CliRunner

        # Mock S3 responses
        mock_metadata.return_value = {
            "datetime": "2026-04-18T10:00:00",
            "version": "0.2.1"
        }
        mock_fetch.return_value = []  # No new files

        # Run CLI command
        runner = CliRunner()
        with patch("newvelles.monitor.cli.CacheManager") as mock_cache_class:
            mock_cache = MagicMock()
            mock_cache.get_known_files.return_value = set()
            mock_cache_class.return_value = mock_cache

            result = runner.invoke(monitor, ["update"])

            assert result.exit_code == 0
            assert "up to date" in result.output.lower() or "no new files" in result.output.lower()

    def test_metrics_aggregation_accuracy(self, sample_visualization_data):
        """Test accuracy of metrics aggregation."""
        # Create multiple metrics for aggregation
        metrics_list = []

        for i in range(5):
            filename = f"newvelles_visualization_0.2.1_2026-04-18T{i:02d}:00:00.json"
            metrics = extract_file_metrics(sample_visualization_data, filename)
            metrics_list.append(metrics)

        # Aggregate by day
        daily_metrics = aggregate_daily_metrics(metrics_list)

        # Verify aggregations
        assert "2026-04-18" in daily_metrics
        day_data = daily_metrics["2026-04-18"]

        assert day_data["updates_count"] == 5
        assert day_data["total_articles"]["mean"] == 2.0  # All files have 2 articles
        assert day_data["total_groups"]["mean"] == 1.0  # All files have 1 top-level group
        assert day_data["subgroups_per_top_group"]["mean"] == 2.0  # All files have 2 sub-groups per top group


class TestMonitoringErrorHandling:
    """Test error handling in monitoring system."""

    def test_empty_cache_handling(self, temp_cache_dir):
        """Test handling of empty cache."""
        cache = CacheManager(temp_cache_dir)

        # Should not crash with empty cache
        known_files = cache.get_known_files()
        assert len(known_files) == 0

        daily_metrics = cache.load_daily_metrics()
        assert len(daily_metrics) == 0

    def test_malformed_data_handling(self, temp_cache_dir):
        """Test handling of malformed visualization data."""
        cache = CacheManager(temp_cache_dir)

        # Empty data
        metrics = extract_file_metrics({}, "test.json")
        assert metrics["total_articles"] == 0
        assert metrics["total_groups"] == 0

        # Should not crash when adding to cache
        cache.add_file("test.json", {
            "processed": True,
            "articles": 0,
            "groups": 0,
            "timestamp": "2026-04-18T10:00:00",
        })

    def test_missing_metadata_fields(self):
        """Test handling of missing metadata fields in articles."""
        incomplete_data = {
            "Group": {
                "Subgroup": {
                    "Article": {
                        "title": "Test"
                        # Missing: link, timestamp, source
                    }
                }
            }
        }

        # Should not crash
        metrics = extract_file_metrics(incomplete_data, "test.json")
        assert metrics["total_articles"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
