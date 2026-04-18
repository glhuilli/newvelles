# Monitoring Dashboard Implementation Plan

## Overview

Build a local console-based monitoring tool that tracks production news data processing metrics with historical trend visualization.

## Requirements

### Core Features
1. **Real-time Metrics Display**
   - Last news update timestamp
   - Total news updates processed (all-time)
   - Current status indicator

2. **Historical Trend Visualization** (Terminal Plots)
   - News processed per day
   - Total groupings per update per day
   - Independent news articles per update per day

3. **Incremental Data Fetching**
   - Cache historical data locally in JSON
   - Only fetch new S3 files not in cache
   - Minimize S3 API calls and data transfer

### Technical Constraints
- No database - JSON files only
- Terminal-only interface (no web UI)
- Must work with existing S3 bucket structure
- Production bucket: `newvelles-data-bucket` (8,614+ files)
- Metadata bucket: `public-newvelles-data-bucket`

## Architecture

### Component Structure

```
newvelles/
├── monitor/                     # New monitoring module
│   ├── __init__.py
│   ├── fetcher.py              # S3 data fetcher with incremental updates
│   ├── cache.py                # Local JSON cache manager
│   ├── metrics.py              # Metrics calculator and aggregator
│   ├── visualizer.py           # Terminal plots and display
│   └── cli.py                  # Main CLI interface
├── .monitor_cache/             # Local cache directory (git-ignored)
│   ├── file_index.json         # Index of processed S3 files
│   ├── daily_metrics.json      # Aggregated daily statistics
│   └── raw_data/               # Downloaded S3 files (optional)
└── scripts/
    └── monitor.py              # Entry point script
```

### Data Flow

```
1. Check local cache → 2. List S3 files → 3. Identify new files
                                                    ↓
6. Display dashboard ← 5. Calculate metrics ← 4. Fetch new data
                                                    ↓
                                              7. Update cache
```

## Implementation Plan

### Phase 1: Project Structure and Configuration

**Files to create:**
- `newvelles/monitor/__init__.py`
- `newvelles/monitor/config.py` - Configuration management
- `.monitor_cache/.gitkeep` - Cache directory placeholder

**Configuration:**
```python
# monitor/config.py
PRODUCTION_BUCKET = "newvelles-data-bucket"
PUBLIC_BUCKET = "public-newvelles-data-bucket"
CACHE_DIR = ".monitor_cache"
FILE_INDEX_PATH = f"{CACHE_DIR}/file_index.json"
DAILY_METRICS_PATH = f"{CACHE_DIR}/daily_metrics.json"
```

### Phase 2: S3 Data Fetcher

**File:** `newvelles/monitor/fetcher.py`

**Key Functions:**
```python
def list_s3_files(bucket: str, prefix: str = "") -> List[str]:
    """List all files in S3 bucket with optional prefix filter"""
    # Uses boto3 S3 client
    # Returns list of file keys sorted by timestamp

def get_latest_metadata() -> dict:
    """Fetch latest_news_metadata.json from public bucket"""
    # Returns: {"datetime": "...", "version": "..."}

def download_file(bucket: str, key: str) -> dict:
    """Download and parse a single S3 JSON file"""
    # Returns parsed JSON data

def fetch_incremental_data(known_files: Set[str]) -> List[Tuple[str, dict]]:
    """Fetch only new files not in known_files set"""
    # Returns list of (filename, data) tuples
```

**Features:**
- Pagination support for large S3 listings
- Parallel downloads using ThreadPoolExecutor
- Error handling with retries
- Progress bar for long operations

### Phase 3: Local Cache System

**File:** `newvelles/monitor/cache.py`

**Cache Structure:**

**file_index.json:**
```json
{
  "last_updated": "2026-04-18T10:30:00",
  "total_files": 8614,
  "files": {
    "newvelles_visualization_0.2.1_2026-04-16T13:14:38.json": {
      "processed": true,
      "size_kb": 255,
      "articles": 150,
      "groups": 45,
      "timestamp": "2026-04-16T13:14:38"
    }
  }
}
```

**daily_metrics.json:**
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

**Key Functions:**
```python
class CacheManager:
    def __init__(self, cache_dir: str):
        """Initialize cache with directory path"""

    def load_file_index(self) -> dict:
        """Load file index from disk or create new"""

    def save_file_index(self, index: dict):
        """Persist file index to disk"""

    def load_daily_metrics(self) -> dict:
        """Load daily metrics from disk or create new"""

    def save_daily_metrics(self, metrics: dict):
        """Persist daily metrics to disk"""

    def get_known_files(self) -> Set[str]:
        """Return set of already processed S3 file keys"""

    def add_file(self, filename: str, metadata: dict):
        """Add new file to index with metadata"""

    def update_daily_metrics(self, date: str, update_data: dict):
        """Append update data to specific date"""
```

### Phase 4: Metrics Calculator

**File:** `newvelles/monitor/metrics.py`

**Key Functions:**
```python
def extract_file_metrics(data: dict, filename: str) -> dict:
    """Extract metrics from a single visualization file"""
    # Parse hierarchical structure to count:
    # - Total top-level groups
    # - Total sub-groups
    # - Total articles
    # - Unique RSS sources
    # - Articles per group distribution
    # Returns: {
    #     "timestamp": "...",
    #     "total_articles": int,
    #     "total_groups": int,
    #     "top_level_groups": int,
    #     "sub_groups": int,
    #     "unique_sources": int
    # }

def aggregate_daily_metrics(file_metrics: List[dict]) -> dict:
    """Aggregate multiple updates into daily statistics"""
    # Groups by date (YYYY-MM-DD)
    # Calculates:
    # - Total updates per day
    # - Average articles per update
    # - Min/max articles per update
    # - Average groups per update

def calculate_trends(daily_metrics: dict, days: int = 30) -> dict:
    """Calculate trend statistics for last N days"""
    # Returns:
    # - Daily averages
    # - Week-over-week changes
    # - Moving averages
    # - Anomaly detection (outliers)

def get_overall_statistics(daily_metrics: dict) -> dict:
    """Calculate all-time statistics"""
    # Returns:
    # - Total updates
    # - First update date
    # - Latest update date
    # - All-time averages
    # - Peak values
```

### Phase 5: Terminal Visualization

**File:** `newvelles/monitor/visualizer.py`

**Libraries:**
- `plotext` - Terminal plotting library
- `rich` - Rich text formatting and tables
- `colorama` - Cross-platform colored terminal text

**Key Functions:**
```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import plotext as plt

def display_header(console: Console, metadata: dict):
    """Display monitoring dashboard header with latest update info"""
    # Shows:
    # - Dashboard title
    # - Last update timestamp
    # - Time since last update (human-readable)
    # - Status indicator (🟢 or 🔴)

def display_summary_stats(console: Console, stats: dict):
    """Display overall statistics in rich table"""
    # Table with:
    # - Total updates (all-time)
    # - First update date
    # - Latest update date
    # - Average articles per update
    # - Average groups per update

def plot_articles_per_day(daily_metrics: dict, days: int = 30):
    """Terminal plot: Articles processed per day"""
    # X-axis: Dates
    # Y-axis: Total articles
    # Shows last N days
    # Includes trend line

def plot_groups_per_update(daily_metrics: dict, days: int = 30):
    """Terminal plot: Groupings per update per day"""
    # Box plot or scatter plot
    # Shows distribution of group counts

def plot_independent_news_per_day(daily_metrics: dict, days: int = 30):
    """Terminal plot: Independent news per update per day"""
    # Similar to articles plot
    # Can show multiple metrics on same plot

def display_dashboard(metadata: dict, stats: dict, daily_metrics: dict):
    """Main dashboard display orchestrator"""
    # Combines all visualization elements
    # Adds spacing and formatting
    # Handles terminal resizing
```

**Example Output:**
```
╔══════════════════════════════════════════════════════════════╗
║          Newvelles Production Monitoring Dashboard          ║
║                                                              ║
║  Last Update:   2026-04-16 13:14:38 (2 hours ago) 🟢       ║
║  Status:        HEALTHY                                      ║
╚══════════════════════════════════════════════════════════════╝

┌─────────────────────── Overall Statistics ───────────────────────┐
│  Total Updates:           8,614                                   │
│  First Update:            2021-07-10 06:00:00                     │
│  Latest Update:           2026-04-16 13:14:38                     │
│  Avg Articles/Update:     150.2                                   │
│  Avg Groups/Update:       45.8                                    │
└───────────────────────────────────────────────────────────────────┘

Articles Processed Per Day (Last 30 Days)
200 ┤         ╭──╮
180 ┤     ╭───╯  ╰──╮
160 ┤   ╭─╯          ╰─╮
140 ┤╭──╯              ╰──╮
120 ┤╯                    ╰─
    └──────────────────────────────
    Mar 17        Apr 1         Apr 16

Groupings Per Update Per Day (Last 30 Days)
60 ┤     •  •
50 ┤   • • •• •
40 ┤  •• ••••••
30 ┤ •••••••••••
20 ┤••••••••••••
   └──────────────────────────────
   Mar 17        Apr 1         Apr 16
```

### Phase 6: Main CLI Interface

**File:** `newvelles/monitor/cli.py`

**CLI Commands:**
```python
import click

@click.group()
def monitor():
    """Newvelles production monitoring dashboard"""
    pass

@monitor.command()
@click.option('--days', default=30, help='Days to display in plots')
@click.option('--refresh', is_flag=True, help='Force refresh from S3')
def dashboard(days: int, refresh: bool):
    """Display main monitoring dashboard"""
    # 1. Load or create cache
    # 2. Fetch incremental data (unless --refresh)
    # 3. Calculate metrics
    # 4. Display visualization
    # 5. Update cache

@monitor.command()
def update():
    """Update cache with latest S3 data"""
    # Fetch new files and update cache only
    # No visualization

@monitor.command()
def stats():
    """Display quick statistics (no plots)"""
    # Fast summary view

@monitor.command()
@click.option('--days', default=7, help='Days to analyze')
def analyze(days: int):
    """Detailed analysis and anomaly detection"""
    # Advanced analytics
    # Anomaly detection
    # Trend analysis

@monitor.command()
def clear_cache():
    """Clear local cache (force full rebuild)"""
    # Delete cache files
    # Confirmation prompt
```

**Entry Point Script:** `scripts/monitor.py`
```python
#!/usr/bin/env python3
from newvelles.monitor.cli import monitor

if __name__ == '__main__':
    monitor()
```

### Phase 7: Configuration and Documentation

**Files to create:**
- `.gitignore` - Add `.monitor_cache/` exclusion
- `docs/MONITORING_DASHBOARD.md` - User documentation
- `requirements.txt` - Add new dependencies

**New Dependencies:**
```txt
plotext>=5.2.8      # Terminal plotting
rich>=13.7.0        # Rich terminal formatting
colorama>=0.4.6     # Cross-platform colors
```

**Documentation Sections:**
1. Installation and setup
2. Usage examples
3. Command reference
4. Cache management
5. Troubleshooting
6. Architecture overview

## Implementation Phases

### Phase 1: Foundation (20 minutes)
- Create project structure
- Set up configuration
- Initialize cache system

### Phase 2: Data Layer (30 minutes)
- Implement S3 fetcher with pagination
- Build cache manager
- Test incremental updates

### Phase 3: Analytics (25 minutes)
- Implement metrics calculator
- Test with sample data
- Validate aggregations

### Phase 4: Visualization (30 minutes)
- Create terminal plots
- Design dashboard layout
- Test with real data

### Phase 5: CLI & Polish (20 minutes)
- Build CLI interface
- Add documentation
- End-to-end testing

**Total Estimated Time: ~2 hours**

## Key Design Decisions

### 1. Incremental Updates Strategy
- Store file index with processed files
- Only fetch new files on each run
- Use S3 ListObjects with pagination
- Cache expensive calculations (daily aggregations)

### 2. Cache Structure
- Two-tier cache: file index + daily metrics
- File index tracks every S3 file
- Daily metrics pre-aggregates by date
- Rebuild mechanism for corrupted cache

### 3. S3 Optimization
- Parallel downloads using ThreadPoolExecutor
- Batch processing (100 files at a time)
- Progress indicators for long operations
- Retry logic with exponential backoff

### 4. Visualization Choices
- `plotext` for terminal plots (simple, effective)
- `rich` for tables and formatting (beautiful output)
- Auto-scaling plots based on terminal size
- Support for multiple plot types (line, bar, scatter)

### 5. Error Handling
- Graceful degradation if S3 unavailable
- Cache corruption recovery
- Partial data display if fetch incomplete
- Clear error messages with actionable advice

## Testing Strategy

### Unit Tests
- Cache manager operations
- Metrics calculations
- File parsing logic

### Integration Tests
- S3 fetcher with mock boto3
- End-to-end cache update
- Dashboard rendering with sample data

### Manual Testing
- Run with production data
- Test incremental updates
- Verify cache persistence
- Check plot rendering on different terminal sizes

## Success Criteria

1. ✅ Dashboard displays last update time correctly
2. ✅ Shows total updates count matching S3 file count
3. ✅ Plots render correctly in terminal
4. ✅ Incremental updates only fetch new files
5. ✅ Cache persists between runs
6. ✅ Sub-second response time for cached data
7. ✅ Handles 8,614+ files efficiently
8. ✅ Clear error messages for common issues

## Future Enhancements

- Email/Slack alerts for anomalies
- Export metrics to CSV/Excel
- Compare QA vs production environments
- RSS source contribution analysis
- Clustering quality metrics
- Web dashboard (optional)
