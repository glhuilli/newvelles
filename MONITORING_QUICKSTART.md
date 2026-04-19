# Monitoring Dashboard - Quick Start

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Verify AWS credentials are configured
aws s3 ls s3://newvelles-data-bucket/ --max-items 1
```

## Basic Usage

### Display Dashboard (Recommended First Command)

```bash
python scripts/monitor.py dashboard
```

This will:
1. Fetch latest metadata from S3
2. Download only new files not in cache (incremental update)
3. Calculate metrics and statistics
4. Display beautiful terminal dashboard with plots

**First run**: Takes 5-10 minutes (downloads all historical data)
**Subsequent runs**: Takes 5-30 seconds (only fetches new files)

### Available Commands

```bash
# Main dashboard (last 30 days)
python scripts/monitor.py dashboard

# Show last 7 days
python scripts/monitor.py dashboard --days 7

# Force full refresh (clear cache and re-download)
python scripts/monitor.py dashboard --refresh

# Monitor QA environment
python scripts/monitor.py dashboard --bucket newvelles-qa-bucket

# Update cache without displaying (background update)
python scripts/monitor.py update

# Quick stats (no plots, faster)
python scripts/monitor.py stats

# Detailed trend analysis
python scripts/monitor.py analyze --days 7

# Clear local cache
python scripts/monitor.py clear-cache

# Enable debug logging
python scripts/monitor.py --debug dashboard
```

## What You'll See

```
╔══════════════════════════════════════════════════════════════╗
║          Newvelles Production Monitoring Dashboard          ║
║                                                              ║
║  Last Update:   2026-04-18T10:30:00 (2 hours ago) 🟢       ║
║  Status:        HEALTHY                                      ║
║  Version:       0.2.1                                        ║
╚══════════════════════════════════════════════════════════════╝

             Overall Statistics
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric                       ┃ Value               ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ Total Updates                │ 8,614               │
│ First Update                 │ 2021-07-10 06:00:00 │
│ Latest Update                │ 2026-04-18 10:30:00 │
│ Avg Articles/Update          │ 150.2               │
│ Median Articles/Update (p50) │ 135.5               │
│ Avg Groups/Update            │ 45.8                │
└──────────────────────────────┴─────────────────────┘

[Terminal plots showing 30-day trends]
```

## Cache Location

All cache files are stored in `.monitor_cache/`:
- `file_index.json` - Tracks processed S3 files
- `daily_metrics.json` - Aggregated daily statistics
- `raw_data/YYYY/MM/` - Raw visualization data files (organized by year/month)

Cache is automatically managed (no manual intervention needed).

**Raw Data Persistence:**
- All downloaded files are saved to `.monitor_cache/raw_data/`
- Organized by year and month for easy access
- Never deleted (persist across cache refreshes)
- ~2-4 GB total for all historical data
- Excluded from git

## Troubleshooting

### "No metrics available"
```bash
python scripts/monitor.py update
```

### "Unable to locate credentials"
```bash
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_DEFAULT_REGION="us-east-1"
```

### Cache issues
```bash
python scripts/monitor.py clear-cache
python scripts/monitor.py dashboard --refresh
```

## Performance

- **First run**: 5-10 minutes (8,614+ files)
- **Incremental update**: 5-30 seconds
- **Cached dashboard**: <1 second
- **Cache size**: ~50 MB

## Documentation

See `docs/MONITORING_DASHBOARD.md` for complete documentation.

## Implementation Details

- **Data Source**: S3 buckets (newvelles-data-bucket, public-newvelles-data-bucket)
- **Historical Data**: 8,614+ timestamped files (July 2021 - Present)
- **Update Frequency**: Every 6 hours (production)
- **Metrics Tracked**: Articles, groups, sources, trends
- **Visualization**: Terminal plots using plotext + rich formatting

## Project Structure

```
newvelles/monitor/
├── __init__.py       # Package initialization
├── config.py         # Configuration constants
├── fetcher.py        # S3 data fetcher (incremental updates)
├── cache.py          # Local JSON cache manager
├── metrics.py        # Metrics calculator and aggregator
├── visualizer.py     # Terminal visualization (plots + tables)
└── cli.py            # CLI interface (Click-based)

.monitor_cache/
├── file_index.json   # Processed files index
└── daily_metrics.json # Daily aggregations

scripts/
└── monitor.py        # Entry point script
```

## Testing

```bash
# Run all monitoring tests (34 fetcher + 9 integration)
pytest test/test_monitor_*.py -v

# Run with coverage
pytest test/test_monitor_*.py --cov=newvelles.monitor

# Run integration tests only
pytest test/test_monitor_integration.py -v
```

All 43 tests passing ✓

---

**Built**: April 18, 2026
**Version**: 0.1.0
**Python**: 3.12+
**Dependencies**: boto3, click, plotext, rich
