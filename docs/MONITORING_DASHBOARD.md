# Newvelles Monitoring Dashboard

A local console-based monitoring tool that tracks production news data processing metrics with historical trend visualization.

## Features

- **Real-time Metrics**: Last update timestamp, total updates count, and current status
- **Historical Trends**: Terminal plots showing news volume, groupings, and trends over time
- **Incremental Updates**: Smart caching to fetch only new data from S3
- **Beautiful Terminal UI**: Rich formatting with tables, colors, and Unicode plots
- **Fast Performance**: Sub-second response time for cached data
- **No Database Required**: JSON-based local cache

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install the new monitoring dependencies:
- `plotext==5.3.2` - Terminal plotting
- `rich==13.9.4` - Rich text formatting

### 2. Verify AWS Credentials

The monitoring tool uses your existing AWS credentials to access S3. Ensure these environment variables are set:

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

Or use AWS CLI configuration:

```bash
aws configure
```

## Usage

### Quick Start

Display the monitoring dashboard with default settings (last 30 days):

```bash
python scripts/monitor.py dashboard
```

or

```bash
python -m newvelles.monitor.cli dashboard
```

### Available Commands

#### 1. Dashboard (Main Command)

Display the full monitoring dashboard with metrics and plots.

```bash
python scripts/monitor.py dashboard [OPTIONS]
```

**Options:**
- `--days INTEGER` - Number of days to show in plots (default: 30)
- `--refresh` - Force full refresh from S3 (clear cache and re-download all data)
- `--bucket TEXT` - S3 bucket to monitor (default: newvelles-data-bucket)
- `--debug` - Enable debug logging

**Examples:**

```bash
# Show last 7 days
python scripts/monitor.py dashboard --days 7

# Force refresh
python scripts/monitor.py dashboard --refresh

# Monitor QA environment
python scripts/monitor.py dashboard --bucket newvelles-qa-bucket

# Enable debug mode
python scripts/monitor.py --debug dashboard
```

#### 2. Update

Update the local cache with latest S3 data without displaying the dashboard.

```bash
python scripts/monitor.py update
```

Use this command to:
- Fetch new data in the background
- Keep cache up-to-date
- Faster subsequent dashboard displays

#### 3. Stats

Display quick statistics without plots (faster).

```bash
python scripts/monitor.py stats
```

Shows:
- Last update time and status
- Total updates
- Date range
- Average metrics

#### 4. Analyze

Detailed trend analysis for a specific time period.

```bash
python scripts/monitor.py analyze [--days INTEGER]
```

**Example:**

```bash
# Analyze last 7 days
python scripts/monitor.py analyze --days 7
```

Shows:
- Trend direction (increasing/decreasing/stable)
- Percentage changes
- Current averages
- Anomaly indicators

#### 5. Clear Cache

Clear the local cache (requires confirmation).

```bash
python scripts/monitor.py clear-cache
```

Use this when:
- Cache is corrupted
- You want to force a complete rebuild
- Testing changes

## Dashboard Output

### Header Section

```
╔══════════════════════════════════════════════════════════════╗
║          Newvelles Production Monitoring Dashboard          ║
║                                                              ║
║  Last Update:   2026-04-18T10:30:00 (2 hours ago) 🟢       ║
║  Status:        HEALTHY                                      ║
║  Version:       0.2.1                                        ║
╚══════════════════════════════════════════════════════════════╝
```

**Status Indicators:**
- 🟢 HEALTHY - Updated within last 7 hours
- 🔴 STALE - No updates for more than 7 hours

### Summary Statistics

```
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
```

### Terminal Plots

Three time-series plots showing:

1. **Articles Processed Per Day** - Total article count trends
2. **Groupings Per Update** - News clustering effectiveness
3. **Independent News Per Day** - Unique article trends

Plots use Unicode braille characters for smooth curves and auto-scale based on your terminal width.

## Cache Management

### Cache Location

```
.monitor_cache/
├── file_index.json          # Processed S3 files index
├── daily_metrics.json       # Aggregated daily statistics
└── raw_data/                # Raw visualization data (organized by year/month)
    ├── 2021/
    │   ├── 07/
    │   │   └── newvelles_visualization_0.2.1_2021-07-10T01:55:22.json
    │   └── 08/
    ├── 2022/
    └── 2026/
        └── 04/
            └── newvelles_visualization_0.2.1_2026-04-18T10:30:00.json
```

**Note:** Cache files and raw data are excluded from git (already in `.gitignore`).

### Cache Structure

#### file_index.json

```json
{
  "last_updated": "2026-04-18T10:30:00",
  "total_files": 8614,
  "files": {
    "newvelles_visualization_0.2.1_2026-04-16T13:14:38.json": {
      "processed": true,
      "articles": 150,
      "groups": 45,
      "timestamp": "2026-04-16T13:14:38"
    }
  }
}
```

#### daily_metrics.json

```json
{
  "2026-04-16": {
    "updates": [
      {
        "timestamp": "2026-04-16T00:00:15",
        "total_articles": 150,
        "total_groups": 45,
        "top_level_groups": 12,
        "sub_groups": 33
      }
    ],
    "daily_total_articles": 600,
    "daily_total_groups": 180,
    "daily_avg_articles_per_update": 150.0
  }
}
```

### Cache Behavior

**First Run:**
- Downloads all historical files from S3 (8,614+ files)
- Saves raw data to `.monitor_cache/raw_data/YYYY/MM/`
- Takes 5-10 minutes depending on connection
- Shows progress indicators

**Subsequent Runs:**
- Only fetches new files since last run
- Saves new raw files locally
- Typically completes in seconds
- Updates cache incrementally

**Refresh:**
- Use `--refresh` flag to rebuild entire cache
- Raw data files are preserved (not deleted)
- Useful after S3 changes or cache corruption

### Raw Data Persistence

**Automatic Saving:**
- Every file downloaded from S3 is automatically saved to local cache
- Files are organized by year and month: `.monitor_cache/raw_data/YYYY/MM/filename.json`
- Raw files are never deleted (persist across cache refreshes)

**Benefits:**
- Re-analyze data without re-downloading from S3
- Faster iterations when testing metrics changes
- Historical backup of all processed data
- Organized structure for easy access

**Duplicate Prevention:**
- Daily metrics automatically prevent duplicate updates
- Updates with same timestamp are skipped
- Safe to re-process the same data multiple times

**Storage Considerations:**
- Raw data files are ~250-500 KB each
- 8,614 files ≈ 2-4 GB total storage
- Organized by year/month for easy cleanup if needed
- Excluded from git to avoid repository bloat

## Metrics Tracked

### Per-Update Metrics

- **Total Articles**: Count of all news articles processed
- **Total Groups**: Combined top-level groups + sub-groups
- **Top-Level Groups**: Major news topic clusters
- **Sub-Groups**: Fine-grained topic subdivisions
- **Unique Sources**: Number of distinct RSS feeds contributing articles
- **Articles Per Group**: Distribution statistics (mean, median, min, max)

### Daily Aggregations

- **Updates Count**: Number of processing runs per day
- **Daily Totals**: Sum of articles and groups for the day
- **Daily Averages**: Mean articles/groups per update
- **Min/Max**: Range of values for the day

### Trend Analysis

- **Direction**: Increasing, decreasing, or stable trends
- **Change Percent**: Percentage change over analysis period
- **Recent Average**: Average for the selected time window
- **Comparison**: Current vs. historical averages

## Troubleshooting

### No metrics available

**Error:** "No metrics available. Run 'monitor update' first."

**Solution:**
```bash
python scripts/monitor.py update
```

Wait for the initial cache to build (5-10 minutes on first run).

### AWS credentials not configured

**Error:** "NoCredentialsError: Unable to locate credentials"

**Solution:**
```bash
# Set environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"

# Or use AWS CLI
aws configure
```

### Cache is up to date but no data shown

**Solution:**
```bash
# Clear cache and refresh
python scripts/monitor.py clear-cache
python scripts/monitor.py dashboard --refresh
```

### S3 access denied

**Error:** "An error occurred (AccessDenied) when calling the ListObjectsV2 operation"

**Solution:**
- Verify your AWS credentials have read access to the S3 buckets
- Check that bucket names are correct (`newvelles-data-bucket`, `public-newvelles-data-bucket`)
- Ensure you're using the correct AWS account

### Slow performance

**Solutions:**
1. **First run is slow (normal)**: Initial download of 8,614+ files takes time
2. **Use update command**: Run `monitor update` in background to pre-populate cache
3. **Reduce plot days**: Use `--days 7` instead of default 30
4. **Check network**: Slow S3 downloads may indicate network issues

### Terminal plots not displaying correctly

**Solutions:**
- Ensure terminal supports Unicode (most modern terminals do)
- Increase terminal width for better plot rendering
- Try a different terminal emulator if issues persist
- Check that `plotext` and `rich` are installed correctly

## Performance

### Typical Performance Metrics

- **First run**: 5-10 minutes (downloads all historical data)
- **Incremental update**: 5-30 seconds (fetches only new files)
- **Cached dashboard**: <1 second (reads from local cache)
- **Stats command**: <1 second (no plots to render)

### Data Volume

- **Historical files**: 8,614+ JSON files (as of April 2026)
- **Average file size**: 250-500 KB
- **Cache size**: ~50 MB (compressed metrics)
- **S3 API calls**: 1-10 per run (with pagination)

## Architecture

### Components

```
newvelles/monitor/
├── __init__.py       # Package initialization
├── config.py         # Configuration constants
├── fetcher.py        # S3 data fetcher
├── cache.py          # Local cache manager
├── metrics.py        # Metrics calculator
├── visualizer.py     # Terminal visualization
└── cli.py            # CLI interface
```

### Data Flow

```
1. CLI Command
   ↓
2. Load Local Cache (file_index.json, daily_metrics.json)
   ↓
3. Fetch Incremental Data from S3 (only new files)
   ↓
4. Extract Metrics (parse JSON structure)
   ↓
5. Update Cache (add new files and daily aggregations)
   ↓
6. Calculate Statistics (trends, aggregations)
   ↓
7. Display Dashboard (rich tables + plotext graphs)
```

## Development

### Running Tests

```bash
# Run all monitoring tests
pytest test/test_monitor_*.py -v

# Run with coverage
pytest test/test_monitor_*.py --cov=newvelles.monitor --cov-report=html

# Run specific test file
pytest test/test_monitor_fetcher.py -v
```

### Adding New Metrics

1. Update `extract_file_metrics()` in `metrics.py`
2. Update cache schema in `cache.py` if needed
3. Add visualization in `visualizer.py`
4. Update documentation

### Debugging

Enable debug logging to see detailed execution:

```bash
python scripts/monitor.py --debug dashboard
```

This shows:
- S3 API calls
- Cache operations
- Metric calculations
- Error stack traces

## FAQ

### How often should I run the monitor?

- **Dashboard**: On-demand when you want to check status
- **Update**: Optionally run daily/hourly to keep cache fresh
- **Analyze**: When investigating trends or anomalies

### Can I monitor QA environment?

Yes! Use the `--bucket` option:

```bash
python scripts/monitor.py dashboard --bucket newvelles-qa-bucket
```

### Does this affect production?

No. The monitoring tool only reads from S3 (no writes). It does not affect the production Lambda function or news processing.

### How much does S3 access cost?

Minimal. Monitoring uses:
- ListObjects API calls: ~$0.005 per 1,000 calls
- GetObject API calls: ~$0.0004 per 1,000 calls
- Data transfer: First 1 GB/month free

Typical monthly cost: <$0.10

### Can I export data to CSV?

Not currently implemented, but you can access cache files directly:

```bash
# Read daily metrics
cat .monitor_cache/daily_metrics.json | jq '.'

# Read file index
cat .monitor_cache/file_index.json | jq '.'
```

Future enhancement: Add CSV export command.

## Support

For issues or questions:

1. Check this documentation
2. Review logs with `--debug` flag
3. Check AWS credentials and S3 access
4. Clear cache and try `--refresh`
5. File an issue with error details

## License

Part of the Newvelles project. See main project LICENSE file.
