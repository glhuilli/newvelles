#!/usr/bin/env python3
"""Demo script to showcase the monitoring dashboard visualizer."""

from datetime import datetime, timedelta

from newvelles.monitor.visualizer import display_dashboard


def generate_sample_data():
    """Generate sample data for demonstration purposes."""
    # Sample metadata
    metadata = {"datetime": "2026-04-18T10:30:00", "version": "0.2.1"}

    # Sample overall statistics
    stats = {
        "total_updates": 8614,
        "first_update": "2021-07-10 06:00:00",
        "latest_update": "2026-04-18 10:30:00",
        "avg_articles_per_update": 150.2,
        "avg_groups_per_update": 45.8,
    }

    # Generate sample daily metrics for the last 30 days
    daily_metrics = {}
    base_date = datetime(2026, 3, 19)

    for i in range(30):
        current_date = base_date + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")

        # Simulate variable article and group counts with some randomness
        # More articles in recent days
        base_articles = 140 + i
        base_groups = 40 + (i // 3)
        base_subgroups = 25 + (i // 4)

        # Add some variation
        import random

        random.seed(i)  # Consistent randomness
        variation = random.randint(-10, 10)

        daily_metrics[date_str] = {
            "updates": [
                {
                    "timestamp": f"{date_str}T00:00:15",
                    "total_articles": base_articles + variation,
                    "total_groups": base_groups + random.randint(-3, 3),
                    "top_level_groups": 12 + random.randint(-2, 2),
                    "sub_groups": base_subgroups + random.randint(-2, 2),
                }
            ],
            "daily_total_articles": base_articles + variation,
            "daily_total_groups": base_groups + random.randint(-3, 3),
            "daily_avg_articles_per_update": float(base_articles + variation),
        }

    return metadata, stats, daily_metrics


def main():
    """Run the demo visualization."""
    print("Generating sample monitoring data...")
    metadata, stats, daily_metrics = generate_sample_data()

    print("Displaying monitoring dashboard...\n")
    display_dashboard(metadata, stats, daily_metrics, days=30)

    print("\nDemo completed successfully!")


if __name__ == "__main__":
    main()
