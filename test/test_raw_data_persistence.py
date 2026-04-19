"""Tests for raw data persistence functionality."""

import json
import tempfile
from pathlib import Path

import pytest

from newvelles.monitor.fetcher import (
    has_raw_file,
    load_raw_file,
    save_raw_file,
)


class TestRawDataPersistence:
    """Test raw data file saving and loading."""

    def test_save_and_load_raw_file(self, monkeypatch):
        """Test saving and loading raw visualization data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock RAW_DATA_DIR to use temp directory
            from newvelles.monitor import fetcher
            monkeypatch.setattr(fetcher, 'RAW_DATA_DIR', Path(tmpdir))

            filename = "newvelles_visualization_0.2.1_2026-04-18T10:30:00.json"
            data = {
                "Top Group": {
                    "Sub Group": {
                        "Article": {
                            "title": "Test Article",
                            "link": "https://example.com",
                            "timestamp": "2026-04-18T10:00:00",
                            "source": "https://example.com/rss"
                        }
                    }
                }
            }

            # Save raw file
            save_raw_file(filename, data)

            # Verify file exists
            assert has_raw_file(filename)

            # Load and verify data
            loaded_data = load_raw_file(filename)
            assert loaded_data == data

            # Verify directory structure (YYYY/MM/)
            expected_path = Path(tmpdir) / "2026" / "04" / filename
            assert expected_path.exists()

    def test_has_raw_file_returns_false_for_nonexistent(self, monkeypatch):
        """Test has_raw_file returns False for nonexistent files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from newvelles.monitor import fetcher
            monkeypatch.setattr(fetcher, 'RAW_DATA_DIR', Path(tmpdir))

            filename = "newvelles_visualization_0.2.1_2026-04-18T10:30:00.json"
            assert not has_raw_file(filename)

    def test_load_raw_file_returns_none_for_nonexistent(self, monkeypatch):
        """Test load_raw_file returns None for nonexistent files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from newvelles.monitor import fetcher
            monkeypatch.setattr(fetcher, 'RAW_DATA_DIR', Path(tmpdir))

            filename = "newvelles_visualization_0.2.1_2026-04-18T10:30:00.json"
            loaded_data = load_raw_file(filename)
            assert loaded_data is None

    def test_save_raw_file_creates_directory_structure(self, monkeypatch):
        """Test save_raw_file creates year/month directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from newvelles.monitor import fetcher
            monkeypatch.setattr(fetcher, 'RAW_DATA_DIR', Path(tmpdir))

            filename = "newvelles_visualization_0.2.1_2026-04-18T10:30:00.json"
            data = {"test": "data"}

            save_raw_file(filename, data)

            # Check directory structure
            year_dir = Path(tmpdir) / "2026"
            month_dir = year_dir / "04"

            assert year_dir.exists()
            assert month_dir.exists()

    def test_save_raw_file_different_months(self, monkeypatch):
        """Test files from different months are organized separately."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from newvelles.monitor import fetcher
            monkeypatch.setattr(fetcher, 'RAW_DATA_DIR', Path(tmpdir))

            # Save files from different months
            files = [
                ("newvelles_visualization_0.2.1_2026-01-15T10:00:00.json", {"month": "jan"}),
                ("newvelles_visualization_0.2.1_2026-02-15T10:00:00.json", {"month": "feb"}),
                ("newvelles_visualization_0.2.1_2026-12-15T10:00:00.json", {"month": "dec"}),
            ]

            for filename, data in files:
                save_raw_file(filename, data)

            # Verify directory structure
            assert (Path(tmpdir) / "2026" / "01").exists()
            assert (Path(tmpdir) / "2026" / "02").exists()
            assert (Path(tmpdir) / "2026" / "12").exists()

            # Verify each file is in correct location
            for filename, data in files:
                loaded = load_raw_file(filename)
                assert loaded == data

    def test_save_raw_file_invalid_filename(self, monkeypatch):
        """Test save_raw_file handles invalid filenames gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from newvelles.monitor import fetcher
            monkeypatch.setattr(fetcher, 'RAW_DATA_DIR', Path(tmpdir))

            invalid_filename = "invalid_file.json"
            data = {"test": "data"}

            # Should not crash, just log warning
            save_raw_file(invalid_filename, data)

            # File should not be saved
            assert not has_raw_file(invalid_filename)

    def test_multiple_years_organization(self, monkeypatch):
        """Test files from different years are organized correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from newvelles.monitor import fetcher
            monkeypatch.setattr(fetcher, 'RAW_DATA_DIR', Path(tmpdir))

            files = [
                ("newvelles_visualization_0.2.1_2024-06-15T10:00:00.json", {"year": 2024}),
                ("newvelles_visualization_0.2.1_2025-06-15T10:00:00.json", {"year": 2025}),
                ("newvelles_visualization_0.2.1_2026-06-15T10:00:00.json", {"year": 2026}),
            ]

            for filename, data in files:
                save_raw_file(filename, data)

            # Verify year directories exist
            assert (Path(tmpdir) / "2024" / "06").exists()
            assert (Path(tmpdir) / "2025" / "06").exists()
            assert (Path(tmpdir) / "2026" / "06").exists()


class TestDailyMetricsDuplicatePrevention:
    """Test that daily metrics prevent duplicate updates."""

    def test_duplicate_update_is_skipped(self):
        """Test that duplicate updates with same timestamp are skipped."""
        from newvelles.monitor.cache import CacheManager

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(tmpdir)

            update_data = {
                "timestamp": "2026-04-18T10:00:00",
                "total_articles": 100,
                "total_groups": 50,
                "top_level_groups": 25,
                "sub_groups": 25,
            }

            # Add update first time
            cache.update_daily_metrics("2026-04-18", update_data)

            metrics = cache.load_daily_metrics()
            assert len(metrics["2026-04-18"]["updates"]) == 1

            # Add same update again (should be skipped)
            cache.update_daily_metrics("2026-04-18", update_data)

            metrics = cache.load_daily_metrics()
            assert len(metrics["2026-04-18"]["updates"]) == 1

    def test_different_timestamps_are_added(self):
        """Test that updates with different timestamps are all added."""
        from newvelles.monitor.cache import CacheManager

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(tmpdir)

            timestamps = ["10:00:00", "14:00:00", "18:00:00", "22:00:00"]

            for ts in timestamps:
                update_data = {
                    "timestamp": f"2026-04-18T{ts}",
                    "total_articles": 100,
                    "total_groups": 50,
                }
                cache.update_daily_metrics("2026-04-18", update_data)

            metrics = cache.load_daily_metrics()
            assert len(metrics["2026-04-18"]["updates"]) == 4

    def test_aggregations_updated_correctly(self):
        """Test that aggregations are recalculated when updates are added."""
        from newvelles.monitor.cache import CacheManager

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(tmpdir)

            # Add first update
            cache.update_daily_metrics("2026-04-18", {
                "timestamp": "2026-04-18T10:00:00",
                "total_articles": 100,
                "total_groups": 50,
            })

            metrics = cache.load_daily_metrics()
            assert metrics["2026-04-18"]["daily_total_articles"] == 100
            assert metrics["2026-04-18"]["daily_total_groups"] == 50

            # Add second update
            cache.update_daily_metrics("2026-04-18", {
                "timestamp": "2026-04-18T14:00:00",
                "total_articles": 150,
                "total_groups": 60,
            })

            metrics = cache.load_daily_metrics()
            assert metrics["2026-04-18"]["daily_total_articles"] == 250  # 100 + 150
            assert metrics["2026-04-18"]["daily_total_groups"] == 110  # 50 + 60
            assert metrics["2026-04-18"]["daily_avg_articles_per_update"] == 125.0  # (100+150)/2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
