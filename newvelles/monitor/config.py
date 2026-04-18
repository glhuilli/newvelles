"""Configuration for monitoring dashboard."""

import os
from pathlib import Path

# S3 Bucket Configuration
PRODUCTION_BUCKET = "newvelles-data-bucket"
PUBLIC_BUCKET = "public-newvelles-data-bucket"
QA_BUCKET = "newvelles-qa-bucket"
PUBLIC_QA_BUCKET = "public-newvelles-qa-bucket"

# Cache Configuration
PROJECT_ROOT = Path(__file__).parent.parent.parent
CACHE_DIR = PROJECT_ROOT / ".monitor_cache"
FILE_INDEX_PATH = CACHE_DIR / "file_index.json"
DAILY_METRICS_PATH = CACHE_DIR / "daily_metrics.json"

# S3 Configuration
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# Visualization Configuration
DEFAULT_PLOT_DAYS = 30
MAX_PARALLEL_DOWNLOADS = 10
BATCH_SIZE = 100

# Ensure cache directory exists
CACHE_DIR.mkdir(exist_ok=True)
