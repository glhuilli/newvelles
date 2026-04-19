"""Terminal visualization for monitoring dashboard.

This module provides rich terminal-based visualization of Newvelles production
monitoring metrics, including formatted tables, status indicators, and terminal
plots for historical trend analysis.
"""

from datetime import datetime, timezone

import plotext as plt
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from newvelles.monitor.config import DEFAULT_PLOT_DAYS


def _calculate_time_ago(timestamp_str: str) -> str:
    """Calculate human-readable time difference from now.

    Args:
        timestamp_str: ISO format timestamp (YYYY-MM-DDTHH:mm:ss)

    Returns:
        Human-readable time difference (e.g., "2 hours ago")
    """
    try:
        timestamp = datetime.fromisoformat(timestamp_str)
        # If timestamp is naive, assume UTC
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        diff = now - timestamp

        seconds = int(diff.total_seconds())

        if seconds < 60:
            return "just now"
        if seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        if seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"

        days = seconds // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"
    except (ValueError, AttributeError):
        return "unknown"


def _get_status_indicator(timestamp_str: str) -> tuple:
    """Determine health status based on last update time.

    Args:
        timestamp_str: ISO format timestamp (YYYY-MM-DDTHH:mm:ss)

    Returns:
        Tuple of (status_text, status_emoji)
    """
    try:
        timestamp = datetime.fromisoformat(timestamp_str)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        diff = now - timestamp
        hours_since = diff.total_seconds() / 3600

        if hours_since > 7:
            return ("STALE", "🔴")
        return ("HEALTHY", "🟢")
    except (ValueError, AttributeError):
        return ("UNKNOWN", "⚪")


def display_header(console: Console, metadata: dict):
    """Display dashboard header with latest update info.

    Args:
        console: Rich Console instance for output
        metadata: Dictionary with 'datetime' and 'version' keys
    """
    timestamp = metadata.get("datetime", "Unknown")
    version = metadata.get("version", "Unknown")
    time_ago = _calculate_time_ago(timestamp)
    status_text, status_emoji = _get_status_indicator(timestamp)

    header_content = f"""[bold cyan]Newvelles Production Monitoring Dashboard[/bold cyan]

[bold]Last Update:[/bold]   {timestamp} ({time_ago}) {status_emoji}
[bold]Status:[/bold]        {status_text}
[bold]Version:[/bold]       {version}"""

    panel = Panel(header_content, border_style="cyan", padding=(1, 2))
    console.print(panel)
    console.print()


def display_summary_stats(console: Console, stats: dict):
    """Display overall statistics table.

    Args:
        console: Rich Console instance for output
        stats: Dictionary containing overall statistics from get_overall_statistics():
            - total_updates: Total number of updates (int)
            - date_range: Dict with 'start' and 'end' dates
            - articles: Dict with 'mean', 'median' and other stats
            - groups: Dict with 'mean', 'median' for top-level groups only
            - subgroups_per_top_group: Dict with 'mean', 'median' for sub-groups per top group
    """
    table = Table(title="Overall Statistics", border_style="blue")

    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    # Extract values from nested structure
    total_updates = stats.get('total_updates', 0)
    date_range = stats.get('date_range', {})
    first_update = date_range.get('start', 'Unknown')
    latest_update = date_range.get('end', 'Unknown')

    articles_stats = stats.get('articles', {})
    avg_articles = articles_stats.get('mean', 0.0)
    median_articles = articles_stats.get('median', 0.0)

    groups_stats = stats.get('groups', {})
    avg_groups = groups_stats.get('mean', 0.0)
    median_groups = groups_stats.get('median', 0.0)

    subgroups_stats = stats.get('subgroups_per_top_group', {})
    avg_subgroups = subgroups_stats.get('mean', 0.0)
    median_subgroups = subgroups_stats.get('median', 0.0)

    table.add_row("Total Updates", f"{total_updates:,}")
    table.add_row("First Update", first_update)
    table.add_row("Latest Update", latest_update)
    table.add_row("Avg Articles/Update", f"{avg_articles:.1f}")
    table.add_row("Median Articles/Update (p50)", f"{median_articles:.1f}")
    table.add_row("Avg Top-Level Groups/Update", f"{avg_groups:.1f}")
    table.add_row("Median Top-Level Groups/Update (p50)", f"{median_groups:.1f}")
    table.add_row("Avg Sub-Groups per Top Group", f"{avg_subgroups:.1f}")
    table.add_row("Median Sub-Groups per Top Group (p50)", f"{median_subgroups:.1f}")

    console.print(table)
    console.print()


def plot_articles_per_day(daily_metrics: dict, days: int = DEFAULT_PLOT_DAYS):
    """Terminal plot: Articles processed per day.

    Args:
        daily_metrics: Dictionary with date keys (YYYY-MM-DD) mapping to daily data
        days: Number of recent days to display
    """
    if not daily_metrics:
        print("No data available for articles per day plot")
        return

    # Sort dates and take last N days
    sorted_dates = sorted(daily_metrics.keys())[-days:]

    if not sorted_dates:
        print("No data available for articles per day plot")
        return

    # Extract dates and article counts
    dates = []
    article_counts = []

    for date in sorted_dates:
        day_data = daily_metrics[date]
        updates = day_data.get("updates", [])

        # Sum articles from all updates for this day
        total_articles = sum(update.get("total_articles", 0) for update in updates)

        dates.append(date)
        article_counts.append(total_articles)

    if not article_counts:
        print("No article data available for plotting")
        return

    # Create plot with numeric x-axis
    plt.clear_figure()
    x_values = list(range(len(dates)))
    plt.plot(x_values, article_counts, marker="braille")
    plt.title("Articles Processed Per Day")
    plt.xlabel("Date")
    plt.ylabel("Total Articles")

    # Format x-axis to show date labels
    if len(dates) > 15:
        # Show start, middle, end dates
        label_indices = [0, len(dates) // 2, len(dates) - 1]
        label_positions = [x_values[i] for i in label_indices]
        label_texts = [dates[i] for i in label_indices]
        plt.xticks(label_positions, label_texts)
    elif len(dates) > 7:
        # Show every Nth date
        step = max(1, len(dates) // 5)
        label_indices = list(range(0, len(dates), step))
        label_positions = [x_values[i] for i in label_indices]
        label_texts = [dates[i] for i in label_indices]
        plt.xticks(label_positions, label_texts)
    else:
        # Show all dates
        plt.xticks(x_values, dates)

    plt.theme("clear")
    plt.plotsize(100, 20)
    plt.show()
    print()


def plot_groups_per_update(daily_metrics: dict, days: int = DEFAULT_PLOT_DAYS):
    """Terminal plot: Groups per update per day.

    Args:
        daily_metrics: Dictionary with date keys (YYYY-MM-DD) mapping to daily data
        days: Number of recent days to display
    """
    if not daily_metrics:
        print("No data available for groups per update plot")
        return

    # Sort dates and take last N days
    sorted_dates = sorted(daily_metrics.keys())[-days:]

    if not sorted_dates:
        print("No data available for groups per update plot")
        return

    # Extract dates and group counts
    dates = []
    group_counts = []

    for date in sorted_dates:
        day_data = daily_metrics[date]
        updates = day_data.get("updates", [])

        # Sum groups from all updates for this day
        total_groups = sum(update.get("total_groups", 0) for update in updates)

        dates.append(date)
        group_counts.append(total_groups)

    if not group_counts:
        print("No group data available for plotting")
        return

    # Create plot with numeric x-axis
    plt.clear_figure()
    x_values = list(range(len(dates)))
    plt.plot(x_values, group_counts, marker="braille")
    plt.title("Groups Per Update Per Day")
    plt.xlabel("Date")
    plt.ylabel("Total Groups")

    # Format x-axis to show date labels
    if len(dates) > 15:
        # Show start, middle, end dates
        label_indices = [0, len(dates) // 2, len(dates) - 1]
        label_positions = [x_values[i] for i in label_indices]
        label_texts = [dates[i] for i in label_indices]
        plt.xticks(label_positions, label_texts)
    elif len(dates) > 7:
        # Show every Nth date
        step = max(1, len(dates) // 5)
        label_indices = list(range(0, len(dates), step))
        label_positions = [x_values[i] for i in label_indices]
        label_texts = [dates[i] for i in label_indices]
        plt.xticks(label_positions, label_texts)
    else:
        # Show all dates
        plt.xticks(x_values, dates)

    plt.theme("clear")
    plt.plotsize(100, 20)
    plt.show()
    print()


def plot_independent_news_per_day(daily_metrics: dict, days: int = DEFAULT_PLOT_DAYS):
    """Terminal plot: Independent news articles per day.

    Independent news are articles that don't belong to any group
    (i.e., standalone articles).

    Args:
        daily_metrics: Dictionary with date keys (YYYY-MM-DD) mapping to daily data
        days: Number of recent days to display
    """
    if not daily_metrics:
        print("No data available for independent news plot")
        return

    # Sort dates and take last N days
    sorted_dates = sorted(daily_metrics.keys())[-days:]

    if not sorted_dates:
        print("No data available for independent news plot")
        return

    # Extract dates and independent article counts
    dates = []
    independent_counts = []

    for date in sorted_dates:
        day_data = daily_metrics[date]
        updates = day_data.get("updates", [])

        # Calculate independent news for this day
        total_independent = 0
        for update in updates:
            total_articles = update.get("total_articles", 0)
            total_groups = update.get("total_groups", 0)
            sub_groups = update.get("sub_groups", 0)

            # Estimate independent articles
            # (articles not in groups = total - groups - subgroups)
            # This is an approximation; actual calculation may vary
            independent = max(0, total_articles - total_groups - sub_groups)
            total_independent += independent

        dates.append(date)
        independent_counts.append(total_independent)

    if not independent_counts:
        print("No independent news data available for plotting")
        return

    # Create plot with numeric x-axis
    plt.clear_figure()
    x_values = list(range(len(dates)))
    plt.plot(x_values, independent_counts, marker="braille")
    plt.title("Independent News Articles Per Day")
    plt.xlabel("Date")
    plt.ylabel("Independent Articles")

    # Format x-axis to show date labels
    if len(dates) > 15:
        # Show start, middle, end dates
        label_indices = [0, len(dates) // 2, len(dates) - 1]
        label_positions = [x_values[i] for i in label_indices]
        label_texts = [dates[i] for i in label_indices]
        plt.xticks(label_positions, label_texts)
    elif len(dates) > 7:
        # Show every Nth date
        step = max(1, len(dates) // 5)
        label_indices = list(range(0, len(dates), step))
        label_positions = [x_values[i] for i in label_indices]
        label_texts = [dates[i] for i in label_indices]
        plt.xticks(label_positions, label_texts)
    else:
        # Show all dates
        plt.xticks(x_values, dates)

    plt.theme("clear")
    plt.plotsize(100, 20)
    plt.show()
    print()


def display_dashboard(
    metadata: dict, stats: dict, daily_metrics: dict, days: int = DEFAULT_PLOT_DAYS
):
    """Main dashboard display orchestrator.

    Combines all visualization elements into a comprehensive dashboard view.

    Args:
        metadata: Latest metadata with 'datetime' and 'version'
        stats: Overall statistics dictionary
        daily_metrics: Daily metrics dictionary
        days: Number of days to show in plots
    """
    console = Console()

    # Display header
    display_header(console, metadata)

    # Display summary statistics
    display_summary_stats(console, stats)

    # Display plots
    console.print("[bold cyan]Historical Trends[/bold cyan]")
    console.print()

    plot_articles_per_day(daily_metrics, days)
    plot_groups_per_update(daily_metrics, days)
    plot_independent_news_per_day(daily_metrics, days)

    # Footer
    console.print("[dim]Tip: Use --days to adjust the time window for plots[/dim]")
