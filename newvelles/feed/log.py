import json
import os
from datetime import datetime
from typing import Any, Dict, List

from newvelles.config import config
from newvelles.models.grouping import VISUALIZATION_VERSION
from newvelles.utils.s3 import upload_to_s3

# Lambda-compatible paths (no local file writes)
# These are kept for reference but not used for file operations
_LATEST_PATH = "/tmp/newvelles"  # Writable in Lambda, but we don't use local files
_LOG_PATH = "/tmp/newvelles/logs"  # Writable in Lambda, but we don't use local files
_LOG_NAME = "all_entries"
_LOG_GROUPED_NAME = "all_grouped_entries"
_LOG_VISUALIZATION_NAME = "newvelles_visualization"
_LOG_LATEST_VISUALIZATION_NAME = "latest_news"
_LOG_LATEST_VISUALIZATION_METADATA_NAME = "latest_news_metadata"

# Load S3 bucket names from config with fallbacks
CONFIG = config()
_S3_BUCKET = os.getenv(
    "AWS_S3_BUCKET", CONFIG.get("S3", "bucket", fallback="newvelles-data-bucket")
)
_S3_PUBLIC_BUCKET = os.getenv(
    "AWS_S3_PUBLIC_BUCKET",
    CONFIG.get("S3", "public_bucket", fallback="public-newvelles-data-bucket"),
)


def _current_datetime():
    iso_str = datetime.now().isoformat()
    # Remove microseconds if present
    if "." in iso_str:
        return iso_str.split(".")[0]
    return iso_str


def log_entries(
    title_data: Dict[str, Any],
    news_data: Dict[str, Any],
    output_path: str = _LOG_PATH,  # pylint: disable=unused-argument
) -> None:
    """
    Lambda-compatible logging function - S3 only, no local file writes.

    In Lambda environment, we skip local file operations since:
    1. /var/data is read-only
    2. /tmp has limited space
    3. All final output goes to S3 via log_s3() anyway

    This function now just logs statistics for monitoring.
    """
    print("📊 Log entries summary:")
    print(f"   • Title data entries: {len(title_data)}")
    print(f"   • News feeds processed: {len(news_data)}")

    # Show top feeds by article count
    if news_data:
        feed_counts = [(feed, len(articles)) for feed, articles in news_data.items()]
        feed_counts.sort(key=lambda x: x[1], reverse=True)
        top_feeds_str = ', '.join([f'{feed}({count})' for feed, count in feed_counts[:3]])
        print(f"   • Top feeds: {top_feeds_str}")

    # Note: Actual file outputs are handled by log_s3() which uploads directly to S3


def log_groups(
    grouped_sentences: Dict[int, List[str]],
    output_path: str = _LOG_PATH  # pylint: disable=unused-argument
) -> None:
    """
    Lambda-compatible group logging - statistics only, no local files.
    """
    print("📊 Group logging summary:")
    print(f"   • Grouped sentences: {len(grouped_sentences)}")
    if grouped_sentences:
        group_sizes = [len(sentences) for sentences in grouped_sentences.values()]
        print(f"   • Average group size: {sum(group_sizes) / len(group_sizes):.1f}")
        print(f"   • Largest group: {max(group_sizes)} sentences")

    # Note: Actual outputs are handled by log_s3() which uploads directly to S3


def log_visualization(visualization_data, output_path: str = _LOG_PATH, s3: bool = False) -> str:
    # Create directories if they don't exist
    os.makedirs(_LATEST_PATH, exist_ok=True)
    os.makedirs(output_path, exist_ok=True)

    current_datetime = _current_datetime()
    viz_file_name = f"{_LOG_VISUALIZATION_NAME}_{VISUALIZATION_VERSION}"
    log_path = f"{output_path}/{viz_file_name}_{current_datetime}.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(visualization_data, f)

    if s3:
        upload_to_s3(
            bucket_name=_S3_BUCKET,
            file_name=f"{viz_file_name}_{current_datetime}.json",
            string_byte=json.dumps(visualization_data).encode("utf-8"),
        )

    log_path_latest = f"{_LATEST_PATH}/{_LOG_LATEST_VISUALIZATION_NAME}.json"
    with open(log_path_latest, "w", encoding="utf-8") as f:
        json.dump(visualization_data, f)

    log_path_latest_current = f"./{_LOG_LATEST_VISUALIZATION_NAME}.json"
    with open(log_path_latest_current, "w", encoding="utf-8") as f:
        json.dump(visualization_data, f)

    if s3:
        upload_to_s3(
            bucket_name=_S3_PUBLIC_BUCKET,
            file_name=f"{_LOG_LATEST_VISUALIZATION_NAME}.json",
            string_byte=json.dumps(visualization_data).encode("utf-8"),
            public_read=True,
        )

    latest_metadata = {
        "datetime": current_datetime,
        "version": VISUALIZATION_VERSION,
        "latest_log_reference": log_path,
    }
    log_path_latest_metadata = f"{_LATEST_PATH}/{_LOG_LATEST_VISUALIZATION_METADATA_NAME}.json"
    with open(log_path_latest_metadata, "w", encoding="utf-8") as f:
        json.dump(latest_metadata, f)

    if s3:
        upload_to_s3(
            bucket_name=_S3_PUBLIC_BUCKET,
            file_name=f"{_LOG_LATEST_VISUALIZATION_METADATA_NAME}.json",
            string_byte=json.dumps(latest_metadata).encode("utf-8"),
            public_read=True,
        )

    return log_path


def log_s3(visualization_data) -> str:
    current_datetime = _current_datetime()
    viz_file_name = f"{_LOG_VISUALIZATION_NAME}_{VISUALIZATION_VERSION}"
    s3_file_name = f"{viz_file_name}_{current_datetime}.json"

    # Prepare metadata
    latest_metadata = {"datetime": current_datetime, "version": VISUALIZATION_VERSION}

    # Upload directly to S3 (skip local file operations for Lambda)
    # 1. Upload timestamped visualization file to private bucket
    upload_to_s3(
        bucket_name=_S3_BUCKET,
        file_name=s3_file_name,
        string_byte=json.dumps(visualization_data).encode("utf-8"),
    )

    # 2. Upload latest visualization to public bucket
    upload_to_s3(
        bucket_name=_S3_PUBLIC_BUCKET,
        file_name=f"{_LOG_LATEST_VISUALIZATION_NAME}.json",
        string_byte=json.dumps(visualization_data).encode("utf-8"),
        public_read=True,
    )

    # 3. Upload metadata to public bucket
    upload_to_s3(
        bucket_name=_S3_PUBLIC_BUCKET,
        file_name=f"{_LOG_LATEST_VISUALIZATION_METADATA_NAME}.json",
        string_byte=json.dumps(latest_metadata).encode("utf-8"),
        public_read=True,
    )

    return s3_file_name
