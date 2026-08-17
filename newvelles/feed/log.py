import json
import os
from datetime import datetime
from typing import Any, Dict, List

from newvelles.config import config
from newvelles.models.grouping import VISUALIZATION_VERSION
from newvelles.utils.publish_gate import evaluate_stories_gate
from newvelles.utils.s3 import read_json_from_s3, upload_to_s3

# Lambda-compatible paths (no local file writes)
# These are kept for reference but not used for file operations
_LATEST_PATH = "/tmp/newvelles"  # Writable in Lambda, but we don't use local files
_LOG_PATH = "/tmp/newvelles/logs"  # Writable in Lambda, but we don't use local files
_LOG_NAME = "all_entries"
_LOG_GROUPED_NAME = "all_grouped_entries"
_LOG_VISUALIZATION_NAME = "newvelles_visualization"
_LOG_LATEST_VISUALIZATION_NAME = "latest_news"
_LOG_LATEST_VISUALIZATION_METADATA_NAME = "latest_news_metadata"
_LOG_STORIES_NAME = "stories"

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


def emit_visualization(
    visualization_data,
    writers: str = "local",
    output_path: str = _LOG_PATH,
    stories_data=None,
) -> str:
    """Single emit path for visualization outputs.

    writers: "local" (CLI), "s3" (Lambda), "both" (CLI --s3).
    The metadata's latest_log_reference exists only when a local log file
    exists to reference — preserving the historical difference between the
    CLI and Lambda outputs.
    """
    if writers not in ("local", "s3", "both"):
        raise ValueError(f"writers must be local|s3|both, got {writers!r}")
    write_local = writers in ("local", "both")
    write_s3 = writers in ("s3", "both")

    current_datetime = _current_datetime()
    viz_file_name = f"{_LOG_VISUALIZATION_NAME}_{VISUALIZATION_VERSION}"
    timestamped_name = f"{viz_file_name}_{current_datetime}.json"
    log_path = f"{output_path}/{timestamped_name}"

    if write_local:
        os.makedirs(_LATEST_PATH, exist_ok=True)
        os.makedirs(output_path, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(visualization_data, f)
    if write_s3:
        upload_to_s3(
            bucket_name=_S3_BUCKET,
            file_name=timestamped_name,
            string_byte=json.dumps(visualization_data).encode("utf-8"),
        )

    if write_local:
        for latest_path in (
            f"{_LATEST_PATH}/{_LOG_LATEST_VISUALIZATION_NAME}.json",
            f"./{_LOG_LATEST_VISUALIZATION_NAME}.json",
        ):
            with open(latest_path, "w", encoding="utf-8") as f:
                json.dump(visualization_data, f)
    if write_s3:
        upload_to_s3(
            bucket_name=_S3_PUBLIC_BUCKET,
            file_name=f"{_LOG_LATEST_VISUALIZATION_NAME}.json",
            string_byte=json.dumps(visualization_data).encode("utf-8"),
            public_read=True,
        )

    latest_metadata = {"datetime": current_datetime, "version": VISUALIZATION_VERSION}
    if write_local:
        latest_metadata["latest_log_reference"] = log_path
        metadata_path = f"{_LATEST_PATH}/{_LOG_LATEST_VISUALIZATION_METADATA_NAME}.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(latest_metadata, f)
    if write_s3:
        upload_to_s3(
            bucket_name=_S3_PUBLIC_BUCKET,
            file_name=f"{_LOG_LATEST_VISUALIZATION_METADATA_NAME}.json",
            string_byte=json.dumps(latest_metadata).encode("utf-8"),
            public_read=True,
        )

    if stories_data is not None:
        _emit_stories(stories_data, write_local=write_local, write_s3=write_s3)

    return log_path if write_local else timestamped_name


def _emit_stories(stories_data, write_local: bool, write_s3: bool) -> None:
    if write_local:
        for stories_path in (
            f"{_LATEST_PATH}/{_LOG_STORIES_NAME}.json",
            f"./{_LOG_STORIES_NAME}.json",
        ):
            with open(stories_path, "w", encoding="utf-8") as f:
                json.dump(stories_data, f)
    if write_s3:
        # Pre-publish sanity gate: compare against the previously published
        # run and refuse to overwrite it with an anomalous one.
        previous = read_json_from_s3(_S3_PUBLIC_BUCKET, f"{_LOG_STORIES_NAME}.json")
        previous_count = previous.get("story_count") if previous else None
        ok, reason = evaluate_stories_gate(stories_data, previous_count)
        if not ok:
            print(f"❌ Stories sanity gate blocked publish: {reason}")
            print("   Previous stories.json left in place; legacy files published normally.")
            return
        upload_to_s3(
            bucket_name=_S3_PUBLIC_BUCKET,
            file_name=f"{_LOG_STORIES_NAME}.json",
            string_byte=json.dumps(stories_data).encode("utf-8"),
            public_read=True,
        )


def log_visualization(visualization_data, output_path: str = _LOG_PATH, s3: bool = False) -> str:
    return emit_visualization(
        visualization_data,
        writers="both" if s3 else "local",
        output_path=output_path,
    )


def log_s3(visualization_data, stories_data=None) -> str:
    return emit_visualization(visualization_data, writers="s3", stories_data=stories_data)
