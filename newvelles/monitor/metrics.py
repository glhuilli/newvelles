"""Metrics extraction and aggregation for monitoring dashboard.

This module provides functions to extract metrics from visualization JSON files,
aggregate metrics by day, and calculate trends and statistics.
"""

import re
from datetime import datetime
from typing import Dict, List, Any
from statistics import mean, median, stdev
from collections import defaultdict


def extract_file_metrics(data: Dict[str, Any], filename: str) -> Dict[str, Any]:
    """Extract metrics from a single visualization JSON file.

    Args:
        data: Visualization data with 3-level hierarchical structure:
              {top_level_group: {sub_group: {article_title: {article_data}}}}
        filename: Name of the file (format: newvelles_visualization_0.2.1_YYYY-MM-DDTHH:mm:ss.json)

    Returns:
        Dictionary containing:
        - timestamp: ISO timestamp extracted from filename
        - total_articles: Total number of articles
        - total_groups: Total number of groups (top-level + sub-groups)
        - top_level_groups: Number of top-level groups
        - sub_groups: Number of sub-groups
        - unique_sources: Number of unique RSS sources
        - articles_per_group: Distribution statistics (mean, median, min, max, stdev)
        - top_level_group_sizes: Distribution of articles per top-level group
        - sub_group_sizes: Distribution of articles per sub-group
    """
    # Extract timestamp from filename
    timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', filename)
    timestamp = timestamp_match.group(1) if timestamp_match else datetime.now().isoformat()

    # Initialize counters
    top_level_count = 0
    sub_group_count = 0
    total_articles = 0
    unique_sources = set()
    top_level_group_sizes = []
    sub_group_sizes = []

    # Traverse 3-level hierarchy
    for top_level_key, top_level_value in data.items():
        if not isinstance(top_level_value, dict):
            continue

        top_level_count += 1
        top_level_article_count = 0

        for sub_group_key, sub_group_value in top_level_value.items():
            if not isinstance(sub_group_value, dict):
                continue

            sub_group_count += 1
            sub_group_article_count = 0

            for article_key, article_data in sub_group_value.items():
                if not isinstance(article_data, dict):
                    continue

                total_articles += 1
                top_level_article_count += 1
                sub_group_article_count += 1

                # Extract RSS source (stored in title_detail_base field)
                source = article_data.get('title_detail_base', '')
                if source:
                    unique_sources.add(source)

            # Record sub-group size
            if sub_group_article_count > 0:
                sub_group_sizes.append(sub_group_article_count)

        # Record top-level group size
        if top_level_article_count > 0:
            top_level_group_sizes.append(top_level_article_count)

    # Calculate distribution statistics
    all_group_sizes = top_level_group_sizes + sub_group_sizes

    articles_per_group_stats = {
        'mean': 0.0,
        'median': 0.0,
        'min': 0,
        'max': 0,
        'stdev': 0.0
    }

    if all_group_sizes:
        articles_per_group_stats = {
            'mean': round(mean(all_group_sizes), 2),
            'median': round(median(all_group_sizes), 2),
            'min': min(all_group_sizes),
            'max': max(all_group_sizes),
            'stdev': round(stdev(all_group_sizes), 2) if len(all_group_sizes) > 1 else 0.0
        }

    return {
        'timestamp': timestamp,
        'total_articles': total_articles,
        'total_groups': top_level_count + sub_group_count,
        'top_level_groups': top_level_count,
        'sub_groups': sub_group_count,
        'unique_sources': len(unique_sources),
        'articles_per_group': articles_per_group_stats,
        'top_level_group_sizes': top_level_group_sizes,
        'sub_group_sizes': sub_group_sizes
    }


def aggregate_daily_metrics(file_metrics: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Aggregate multiple file metrics into daily statistics.

    Groups metrics by day and calculates aggregate statistics for each day.

    Args:
        file_metrics: List of metrics dictionaries from extract_file_metrics()

    Returns:
        Dictionary mapping date (YYYY-MM-DD) to daily aggregated metrics:
        - date: The date string
        - updates_count: Number of updates that day
        - total_articles: Stats (mean, median, min, max) for article counts
        - total_groups: Stats for group counts
        - top_level_groups: Stats for top-level group counts
        - sub_groups: Stats for sub-group counts
        - unique_sources: Stats for unique source counts
        - articles_per_group_mean: Stats for articles per group mean
        - timestamps: List of all update timestamps that day
    """
    daily_data = defaultdict(list)

    # Group metrics by date
    for metrics in file_metrics:
        timestamp_str = metrics.get('timestamp', '')
        if not timestamp_str:
            continue

        # Extract date from timestamp (YYYY-MM-DD)
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', timestamp_str)
        if not date_match:
            continue

        date = date_match.group(1)
        daily_data[date].append(metrics)

    # Calculate daily statistics
    daily_metrics = {}

    for date, metrics_list in sorted(daily_data.items()):
        if not metrics_list:
            continue

        # Extract values for each metric
        articles = [m['total_articles'] for m in metrics_list]
        groups = [m['total_groups'] for m in metrics_list]
        top_level = [m['top_level_groups'] for m in metrics_list]
        sub_groups = [m['sub_groups'] for m in metrics_list]
        sources = [m['unique_sources'] for m in metrics_list]
        articles_per_group_means = [m['articles_per_group']['mean'] for m in metrics_list]
        timestamps = [m['timestamp'] for m in metrics_list]

        daily_metrics[date] = {
            'date': date,
            'updates_count': len(metrics_list),
            'total_articles': _calculate_stats(articles),
            'total_groups': _calculate_stats(groups),
            'top_level_groups': _calculate_stats(top_level),
            'sub_groups': _calculate_stats(sub_groups),
            'unique_sources': _calculate_stats(sources),
            'articles_per_group_mean': _calculate_stats(articles_per_group_means),
            'timestamps': timestamps
        }

    return daily_metrics


def calculate_trends(daily_metrics: Dict[str, Dict[str, Any]], days: int = 30) -> Dict[str, Any]:
    """Calculate trend statistics for the last N days.

    Args:
        daily_metrics: Dictionary from aggregate_daily_metrics()
        days: Number of recent days to analyze (default: 30)

    Returns:
        Dictionary containing trend statistics:
        - days_analyzed: Number of days included in analysis
        - date_range: Start and end dates
        - total_updates: Total number of updates in period
        - articles_trend: Trend statistics for article counts
        - groups_trend: Trend statistics for group counts
        - sources_trend: Trend statistics for source counts
        - daily_avg_articles: Average articles per day
        - daily_avg_groups: Average groups per day
        - daily_avg_sources: Average sources per day
    """
    if not daily_metrics:
        return _empty_trends()

    # Get last N days
    sorted_dates = sorted(daily_metrics.keys(), reverse=True)
    recent_dates = sorted_dates[:days]
    recent_dates_sorted = sorted(recent_dates)

    if not recent_dates_sorted:
        return _empty_trends()

    # Extract metrics for trend calculation
    articles_values = []
    groups_values = []
    sources_values = []
    total_updates = 0

    for date in recent_dates_sorted:
        metrics = daily_metrics[date]
        total_updates += metrics['updates_count']

        # Use mean values from daily aggregates
        articles_values.append(metrics['total_articles']['mean'])
        groups_values.append(metrics['total_groups']['mean'])
        sources_values.append(metrics['unique_sources']['mean'])

    return {
        'days_analyzed': len(recent_dates_sorted),
        'date_range': {
            'start': recent_dates_sorted[0],
            'end': recent_dates_sorted[-1]
        },
        'total_updates': total_updates,
        'articles_trend': _calculate_trend_stats(articles_values),
        'groups_trend': _calculate_trend_stats(groups_values),
        'sources_trend': _calculate_trend_stats(sources_values),
        'daily_avg_articles': round(mean(articles_values), 2) if articles_values else 0.0,
        'daily_avg_groups': round(mean(groups_values), 2) if groups_values else 0.0,
        'daily_avg_sources': round(mean(sources_values), 2) if sources_values else 0.0
    }


def get_overall_statistics(daily_metrics: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate all-time statistics from daily metrics.

    Args:
        daily_metrics: Dictionary from cache or aggregate_daily_metrics()
                      Supports both cache format (with daily_total_articles)
                      and aggregated format (with total_articles['mean'])

    Returns:
        Dictionary containing all-time statistics:
        - total_days: Number of days with data
        - total_updates: Total number of updates
        - date_range: First and last dates
        - articles: All-time statistics for article counts
        - groups: All-time statistics for group counts
        - sources: All-time statistics for source counts (if available)
        - avg_updates_per_day: Average number of updates per day
    """
    if not daily_metrics:
        return _empty_overall_stats()

    sorted_dates = sorted(daily_metrics.keys())

    # Collect all values
    all_articles = []
    all_groups = []
    all_sources = []
    total_updates = 0

    for date in sorted_dates:
        metrics = daily_metrics[date]
        total_updates += metrics.get('updates_count', 0)

        # Support both cache format and aggregated format
        if 'total_articles' in metrics and isinstance(metrics['total_articles'], dict):
            # Aggregated format (from aggregate_daily_metrics)
            all_articles.append(metrics['total_articles']['mean'])
            all_groups.append(metrics['total_groups']['mean'])
            if 'unique_sources' in metrics:
                all_sources.append(metrics['unique_sources']['mean'])
        else:
            # Cache format (from CacheManager.update_daily_metrics)
            # Calculate averages from updates list
            updates = metrics.get('updates', [])
            if updates:
                avg_articles = sum(u.get('total_articles', 0) for u in updates) / len(updates)
                avg_groups = sum(u.get('total_groups', 0) for u in updates) / len(updates)
                all_articles.append(avg_articles)
                all_groups.append(avg_groups)

                # Try to get sources if available
                avg_sources = sum(u.get('unique_sources', 0) for u in updates) / len(updates)
                if avg_sources > 0:
                    all_sources.append(avg_sources)

    result = {
        'total_days': len(sorted_dates),
        'total_updates': total_updates,
        'date_range': {
            'start': sorted_dates[0],
            'end': sorted_dates[-1]
        },
        'articles': _calculate_stats(all_articles),
        'groups': _calculate_stats(all_groups),
        'avg_updates_per_day': round(total_updates / len(sorted_dates), 2) if sorted_dates else 0.0
    }

    # Add sources stats if available
    if all_sources:
        result['sources'] = _calculate_stats(all_sources)

    return result


# Helper functions

def _calculate_stats(values: List[float]) -> Dict[str, float]:
    """Calculate mean, median, min, max, and stdev for a list of values."""
    if not values:
        return {
            'mean': 0.0,
            'median': 0.0,
            'min': 0.0,
            'max': 0.0,
            'stdev': 0.0
        }

    return {
        'mean': round(mean(values), 2),
        'median': round(median(values), 2),
        'min': round(min(values), 2),
        'max': round(max(values), 2),
        'stdev': round(stdev(values), 2) if len(values) > 1 else 0.0
    }


def _calculate_trend_stats(values: List[float]) -> Dict[str, Any]:
    """Calculate trend statistics including change over time."""
    if not values:
        return {
            'current': 0.0,
            'previous': 0.0,
            'change': 0.0,
            'change_percent': 0.0,
            'trend_direction': 'stable'
        }

    current = values[-1]
    previous = values[0] if len(values) > 1 else current

    change = current - previous
    change_percent = ((change / previous) * 100) if previous != 0 else 0.0

    # Determine trend direction
    if abs(change_percent) < 1.0:
        trend_direction = 'stable'
    elif change_percent > 0:
        trend_direction = 'increasing'
    else:
        trend_direction = 'decreasing'

    return {
        'current': round(current, 2),
        'previous': round(previous, 2),
        'change': round(change, 2),
        'change_percent': round(change_percent, 2),
        'trend_direction': trend_direction,
        'statistics': _calculate_stats(values)
    }


def _empty_trends() -> Dict[str, Any]:
    """Return empty trends structure."""
    return {
        'days_analyzed': 0,
        'date_range': {'start': '', 'end': ''},
        'total_updates': 0,
        'articles_trend': _calculate_trend_stats([]),
        'groups_trend': _calculate_trend_stats([]),
        'sources_trend': _calculate_trend_stats([]),
        'daily_avg_articles': 0.0,
        'daily_avg_groups': 0.0,
        'daily_avg_sources': 0.0
    }


def _empty_overall_stats() -> Dict[str, Any]:
    """Return empty overall statistics structure."""
    return {
        'total_days': 0,
        'total_updates': 0,
        'date_range': {'start': '', 'end': ''},
        'articles': _calculate_stats([]),
        'groups': _calculate_stats([]),
        'sources': _calculate_stats([]),
        'avg_updates_per_day': 0.0
    }
