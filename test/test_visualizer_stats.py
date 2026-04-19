"""Tests for visualizer stats display."""

from io import StringIO

from rich.console import Console

from newvelles.monitor.visualizer import display_summary_stats


def test_display_summary_stats_with_real_structure():
    """Test that display_summary_stats correctly extracts nested stats."""
    # This is the actual structure returned by get_overall_statistics
    stats = {
        'total_days': 1710,
        'total_updates': 8614,
        'date_range': {
            'start': '2021-07-10',
            'end': '2026-04-16'
        },
        'articles': {
            'mean': 444.11,
            'median': 385.83,
            'min': 83.0,
            'max': 5202.79,
            'stdev': 295.62
        },
        'groups': {  # Now only top-level groups
            'mean': 54.5,
            'median': 55.0,
            'min': 20.0,
            'max': 85.0,
            'stdev': 12.5
        },
        'subgroups_per_top_group': {  # New metric
            'mean': 4.8,
            'median': 4.6,
            'min': 2.0,
            'max': 8.5,
            'stdev': 1.2
        },
        'avg_updates_per_day': 5.04
    }

    # Capture output
    string_io = StringIO()
    console = Console(file=string_io, force_terminal=True, width=80)

    # Display stats
    display_summary_stats(console, stats)

    output = string_io.getvalue()

    # Verify all values are displayed correctly
    assert "8,614" in output  # Total updates with comma formatting
    assert "2021-07-10" in output  # First update
    assert "2026-04-16" in output  # Latest update
    assert "444.1" in output  # Avg articles (rounded to 1 decimal)
    assert "385.8" in output  # Median articles (rounded to 1 decimal)
    assert "54.5" in output  # Avg top-level groups (rounded to 1 decimal)
    assert "55.0" in output  # Median top-level groups
    assert "4.8" in output  # Avg sub-groups per top group
    assert "4.6" in output  # Median sub-groups per top group

    # Check for p50 label
    assert "p50" in output or "Median" in output

    # Check for new labels
    assert "Top-Level" in output or "top-level" in output.lower()
    assert "Sub-Group" in output or "sub-group" in output.lower()

    # Should not contain "Unknown" or only zeros
    assert "Unknown" not in output


def test_display_summary_stats_with_missing_data():
    """Test that display_summary_stats handles missing nested data gracefully."""
    # Empty stats structure
    stats = {}

    # Capture output
    string_io = StringIO()
    console = Console(file=string_io, force_terminal=True, width=80)

    # Display stats (should not crash)
    display_summary_stats(console, stats)

    output = string_io.getvalue()

    # Should display defaults
    assert "0" in output  # Total updates
    assert "Unknown" in output  # Dates
    assert "0.0" in output  # Averages


def test_display_summary_stats_with_partial_data():
    """Test with partially populated stats."""
    stats = {
        'total_updates': 100,
        'date_range': {
            'start': '2026-01-01',
            # 'end' missing
        },
        'articles': {
            'mean': 150.5,
            'median': 142.3
        },
        'groups': {
            'mean': 45.2,
            'median': 44.0
        },
        # 'subgroups_per_top_group' missing
    }

    # Capture output
    string_io = StringIO()
    console = Console(file=string_io, force_terminal=True, width=80)

    # Display stats (should not crash)
    display_summary_stats(console, stats)

    output = string_io.getvalue()

    # Should display available data
    assert "100" in output
    assert "2026-01-01" in output
    assert "150.5" in output
    assert "142.3" in output  # Median articles
    assert "45.2" in output  # Avg groups
    assert "44.0" in output  # Median groups


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
