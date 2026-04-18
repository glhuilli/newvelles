"""CLI interface for Newvelles monitoring dashboard."""

import logging
from typing import Optional

import click
from rich.console import Console

from newvelles.monitor.cache import CacheManager
from newvelles.monitor.config import (
    CACHE_DIR,
    DEFAULT_PLOT_DAYS,
    PRODUCTION_BUCKET,
)
from newvelles.monitor.fetcher import (
    fetch_incremental_data,
    get_latest_metadata,
)
from newvelles.monitor.metrics import (
    aggregate_daily_metrics,
    calculate_trends,
    extract_file_metrics,
    get_overall_statistics,
)
from newvelles.monitor.visualizer import display_dashboard

logger = logging.getLogger(__name__)


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
def monitor(debug: bool):
    """Newvelles production monitoring dashboard.

    Track production news data processing metrics with historical trends.
    """
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)


@monitor.command()
@click.option("--days", default=DEFAULT_PLOT_DAYS, help="Days to display in plots")
@click.option("--refresh", is_flag=True, help="Force full refresh from S3")
@click.option("--bucket", default=PRODUCTION_BUCKET, help="S3 bucket to monitor")
def dashboard(days: int, refresh: bool, bucket: str):
    """Display main monitoring dashboard with metrics and plots."""
    console = Console()

    try:
        # Initialize cache
        cache = CacheManager()

        # Get latest metadata from S3
        console.print("[cyan]Fetching latest metadata from S3...[/cyan]")
        metadata = get_latest_metadata()

        # Load or rebuild cache
        if refresh:
            console.print("[yellow]Forcing full refresh - clearing cache...[/yellow]")
            cache.save_file_index({"last_updated": "", "total_files": 0, "files": {}})
            cache.save_daily_metrics({})

        # Get known files
        known_files = cache.get_known_files()
        console.print(f"[cyan]Cached files: {len(known_files)}[/cyan]")

        # Fetch incremental data
        console.print("[cyan]Fetching new data from S3...[/cyan]")
        new_data = fetch_incremental_data(known_files, bucket=bucket)

        if new_data:
            console.print(f"[green]Processing {len(new_data)} new files...[/green]")

            # Process each new file
            for filename, data in new_data:
                # Extract metrics
                file_metrics = extract_file_metrics(data, filename)

                # Update cache
                cache.add_file(filename, {
                    "processed": True,
                    "articles": file_metrics["total_articles"],
                    "groups": file_metrics["total_groups"],
                    "timestamp": file_metrics["timestamp"],
                })

                # Update daily metrics
                date = file_metrics["timestamp"].split("T")[0]
                cache.update_daily_metrics(date, file_metrics)
        else:
            console.print("[yellow]No new files to process[/yellow]")

        # Load daily metrics
        daily_metrics = cache.load_daily_metrics()

        if not daily_metrics:
            console.print("[red]No metrics available. Try running with --refresh[/red]")
            return

        # Calculate overall statistics
        stats = get_overall_statistics(daily_metrics)

        # Display dashboard
        display_dashboard(metadata, stats, daily_metrics, days=days)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Dashboard error")
        raise click.Abort()


@monitor.command()
@click.option("--bucket", default=PRODUCTION_BUCKET, help="S3 bucket to monitor")
def update(bucket: str):
    """Update cache with latest S3 data without displaying dashboard."""
    console = Console()

    try:
        # Initialize cache
        cache = CacheManager()

        console.print("[cyan]Fetching latest data from S3...[/cyan]")

        # Get known files
        known_files = cache.get_known_files()

        # Fetch incremental data
        new_data = fetch_incremental_data(known_files, bucket=bucket)

        if not new_data:
            console.print("[yellow]Cache is up to date[/yellow]")
            return

        console.print(f"[green]Processing {len(new_data)} new files...[/green]")

        # Process each new file
        for filename, data in new_data:
            # Extract metrics
            file_metrics = extract_file_metrics(data, filename)

            # Update cache
            cache.add_file(filename, {
                "processed": True,
                "articles": file_metrics["total_articles"],
                "groups": file_metrics["total_groups"],
                "timestamp": file_metrics["timestamp"],
            })

            # Update daily metrics
            date = file_metrics["timestamp"].split("T")[0]
            cache.update_daily_metrics(date, file_metrics)

        console.print(f"[green]✓ Updated cache with {len(new_data)} new files[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Update error")
        raise click.Abort()


@monitor.command()
def stats():
    """Display quick statistics without plots."""
    console = Console()

    try:
        # Initialize cache
        cache = CacheManager()

        # Load daily metrics
        daily_metrics = cache.load_daily_metrics()

        if not daily_metrics:
            console.print("[red]No metrics available. Run 'monitor update' first.[/red]")
            return

        # Calculate overall statistics
        stats = get_overall_statistics(daily_metrics)

        # Get latest metadata
        try:
            metadata = get_latest_metadata()
        except Exception:
            metadata = {"datetime": "Unknown", "version": "Unknown"}

        # Display header and stats only (no plots)
        from newvelles.monitor.visualizer import display_header, display_summary_stats

        display_header(console, metadata)
        console.print()
        display_summary_stats(console, stats)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Stats error")
        raise click.Abort()


@monitor.command()
@click.option("--days", default=7, help="Days to analyze")
def analyze(days: int):
    """Detailed analysis and trend detection."""
    console = Console()

    try:
        # Initialize cache
        cache = CacheManager()

        # Load daily metrics
        daily_metrics = cache.load_daily_metrics()

        if not daily_metrics:
            console.print("[red]No metrics available. Run 'monitor update' first.[/red]")
            return

        # Calculate trends
        trends = calculate_trends(daily_metrics, days=days)

        console.print(f"\n[bold cyan]Trend Analysis (Last {days} Days)[/bold cyan]\n")

        # Display trend information
        from rich.table import Table

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Trend", style="yellow")
        table.add_column("Change", style="green")
        table.add_column("Current Avg", style="white")

        metrics_info = [
            ("Articles per Update", "articles", "avg_articles_per_update"),
            ("Groups per Update", "groups", "avg_groups_per_update"),
            ("Sources per Update", "sources", "avg_sources_per_update"),
        ]

        for label, key, avg_key in metrics_info:
            if key in trends:
                trend = trends[key]
                direction = trend.get("trend", "stable")
                change = trend.get("change_percent", 0.0)
                avg = trend.get("recent_avg", 0.0)

                # Format direction with emoji
                if direction == "increasing":
                    direction_str = "📈 Increasing"
                elif direction == "decreasing":
                    direction_str = "📉 Decreasing"
                else:
                    direction_str = "➡️  Stable"

                table.add_row(
                    label,
                    direction_str,
                    f"{change:+.1f}%",
                    f"{avg:.1f}"
                )

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Analysis error")
        raise click.Abort()


@monitor.command()
@click.confirmation_option(prompt="Are you sure you want to clear the cache?")
def clear_cache():
    """Clear local cache (requires confirmation)."""
    console = Console()

    try:
        import shutil

        cache_dir = str(CACHE_DIR)

        # Remove cache directory
        if CACHE_DIR.exists():
            shutil.rmtree(cache_dir)
            CACHE_DIR.mkdir()
            console.print(f"[green]✓ Cache cleared: {cache_dir}[/green]")
        else:
            console.print("[yellow]Cache directory does not exist[/yellow]")

    except Exception as e:
        console.print(f"[red]Error clearing cache: {e}[/red]")
        raise click.Abort()


def main():
    """Entry point for the monitoring CLI."""
    monitor()


if __name__ == "__main__":
    main()
