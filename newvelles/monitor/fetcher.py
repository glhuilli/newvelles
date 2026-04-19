"""S3 data fetcher for monitoring dashboard.

Handles fetching, parsing, and incremental downloads of visualization data from S3.
Supports pagination for large buckets and parallel downloads for efficiency.
"""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from newvelles.monitor.config import (AWS_REGION, BATCH_SIZE, MAX_PARALLEL_DOWNLOADS,
                                      PRODUCTION_BUCKET, PUBLIC_BUCKET, RAW_DATA_DIR)

logger = logging.getLogger(__name__)

# Ensure raw data directory exists
RAW_DATA_DIR.mkdir(exist_ok=True)


def list_s3_files(bucket: str, prefix: str = "") -> List[str]:
    """
    List all files in S3 bucket with pagination support.

    Handles large buckets (8,614+ files) using S3 pagination to fetch all objects.

    Args:
        bucket: S3 bucket name
        prefix: Optional prefix to filter objects (e.g., "newvelles_visualization_")

    Returns:
        List of S3 object keys

    Raises:
        NoCredentialsError: If AWS credentials are not configured
        ClientError: If S3 operation fails
    """
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    files = []

    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix)

        for page in page_iterator:
            if "Contents" in page:
                for obj in page["Contents"]:
                    files.append(obj["Key"])

        logger.info(f"Listed {len(files)} files from s3://{bucket}/{prefix}")
        return files

    except NoCredentialsError:
        logger.error("AWS credentials not found. Please configure your credentials.")
        raise
    except ClientError as e:
        logger.error(f"Error listing files from s3://{bucket}/{prefix}: {e}")
        raise


def get_latest_metadata() -> Dict:
    """
    Fetch latest_news_metadata.json from public bucket.

    Returns:
        Dictionary containing metadata with keys:
        - datetime: Timestamp of latest update
        - version: Visualization schema version

    Raises:
        ClientError: If file doesn't exist or S3 operation fails
    """
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    key = "latest_news_metadata.json"

    try:
        response = s3_client.get_object(Bucket=PUBLIC_BUCKET, Key=key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        logger.info(f"Fetched metadata from s3://{PUBLIC_BUCKET}/{key}")
        return data

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchKey":
            logger.error(f"Metadata file not found: s3://{PUBLIC_BUCKET}/{key}")
        else:
            logger.error(f"Error fetching metadata: {e}")
        raise


def download_file(bucket: str, key: str) -> Dict:
    """
    Download and parse a single S3 JSON file.

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        Parsed JSON data as dictionary

    Raises:
        ClientError: If S3 operation fails
        json.JSONDecodeError: If file is not valid JSON
    """
    s3_client = boto3.client("s3", region_name=AWS_REGION)

    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        logger.debug(f"Downloaded s3://{bucket}/{key}")
        return data

    except ClientError as e:
        logger.error(f"Error downloading s3://{bucket}/{key}: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in s3://{bucket}/{key}: {e}")
        raise


def _download_file_with_retry(
    bucket: str, key: str, max_retries: int = 3
) -> Optional[Tuple[str, Dict]]:
    """
    Download a file with retry logic.

    Internal helper for parallel downloads with error handling.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        max_retries: Maximum number of retry attempts

    Returns:
        Tuple of (key, data) if successful, None if all retries fail
    """
    for attempt in range(max_retries):
        try:
            data = download_file(bucket, key)
            return (key, data)
        except (ClientError, json.JSONDecodeError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"Retry {attempt + 1}/{max_retries} for {key}: {e}")
            else:
                logger.error(
                    f"Failed to download {key} after {max_retries} attempts: {e}"
                )

    return None


def fetch_incremental_data(
    known_files: Set[str], bucket: str = PRODUCTION_BUCKET, prefix: str = ""
) -> List[Tuple[str, Dict]]:
    """
    Fetch only new files not in known_files set.

    Uses parallel downloads for efficiency, processing files in batches
    to avoid memory exhaustion.

    Args:
        known_files: Set of S3 keys that have already been processed
        bucket: S3 bucket name (defaults to production bucket)
        prefix: Optional prefix to filter objects

    Returns:
        List of (filename, data) tuples for new files only

    Raises:
        NoCredentialsError: If AWS credentials are not configured
        ClientError: If S3 operations fail
    """
    logger.info(f"Fetching incremental data from s3://{bucket}/{prefix}")

    # List all files in bucket
    all_files = list_s3_files(bucket, prefix)

    # Filter for new files only
    new_files = [f for f in all_files if f not in known_files and f.endswith(".json")]

    if not new_files:
        logger.info("No new files to fetch")
        return []

    logger.info(f"Found {len(new_files)} new files to download")

    results = []
    total_files = len(new_files)

    # Process in batches to avoid memory issues
    for batch_start in range(0, total_files, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_files)
        batch = new_files[batch_start:batch_end]

        logger.info(
            f"Processing batch {batch_start // BATCH_SIZE + 1} "
            f"({batch_start + 1}-{batch_end} of {total_files})"
        )

        # Download batch in parallel
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_DOWNLOADS) as executor:
            futures = {
                executor.submit(_download_file_with_retry, bucket, key): key
                for key in batch
            }

            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    results.append(result)

    logger.info(f"Successfully downloaded {len(results)} files")
    return results


def parse_visualization_filename(filename: str) -> Optional[Dict[str, str]]:
    """
    Parse visualization filename to extract metadata.

    Expected format: newvelles_visualization_{version}_{timestamp}.json
    Example: newvelles_visualization_0.2.1_2026-04-16T13:14:38.json

    Args:
        filename: S3 object key or filename

    Returns:
        Dictionary with keys:
        - version: Schema version (e.g., "0.2.1")
        - timestamp: ISO 8601 timestamp string
        - datetime: Parsed datetime object
        Returns None if filename doesn't match expected pattern

    Examples:
        >>> parse_visualization_filename("newvelles_visualization_0.2.1_2025-01-16T10:30:45.json")
        {
            'version': '0.2.1',
            'timestamp': '2025-01-16T10:30:45',
            'datetime': datetime(2025, 1, 16, 10, 30, 45)
        }
    """
    # Pattern: newvelles_visualization_{version}_{YYYY-MM-DDTHH:mm:ss}.json
    pattern = r"newvelles_visualization_(\d+\.\d+\.\d+)_(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.json"
    match = re.match(pattern, filename)

    if not match:
        logger.debug(f"Filename does not match pattern: {filename}")
        return None

    version = match.group(1)
    timestamp = match.group(2)

    try:
        dt = datetime.fromisoformat(timestamp)
        return {"version": version, "timestamp": timestamp, "datetime": dt}
    except ValueError as e:
        logger.warning(f"Invalid timestamp in filename {filename}: {e}")
        return None


def get_file_count(bucket: str, prefix: str = "") -> int:
    """
    Get count of files in S3 bucket without downloading them.

    Efficient for checking bucket size without full listing.

    Args:
        bucket: S3 bucket name
        prefix: Optional prefix to filter objects

    Returns:
        Number of files matching the prefix

    Raises:
        ClientError: If S3 operation fails
    """
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    count = 0

    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix)

        for page in page_iterator:
            if "Contents" in page:
                count += len(page["Contents"])

        logger.info(f"Counted {count} files in s3://{bucket}/{prefix}")
        return count

    except ClientError as e:
        logger.error(f"Error counting files in s3://{bucket}/{prefix}: {e}")
        raise


def save_raw_file(filename: str, data: Dict) -> None:
    """
    Save raw visualization data to local cache organized by year/month.

    Files are stored in: .monitor_cache/raw_data/YYYY/MM/filename.json

    Args:
        filename: Name of the file (e.g., newvelles_visualization_0.2.1_2026-04-18T10:00:00.json)
        data: Raw JSON data dictionary to save

    Example:
        >>> save_raw_file("newvelles_visualization_0.2.1_2026-04-18T10:00:00.json", {...})
        # Saves to: .monitor_cache/raw_data/2026/04/newvelles_visualization_0.2.1_2026-04-18T10:00:00.json
    """
    # Parse filename to extract date
    parsed = parse_visualization_filename(filename)
    if not parsed:
        logger.warning(f"Cannot save raw file with invalid filename: {filename}")
        return

    # Extract year and month from datetime
    dt = parsed["datetime"]
    year = str(dt.year)
    month = f"{dt.month:02d}"

    # Create directory structure: raw_data/YYYY/MM/
    save_dir = RAW_DATA_DIR / year / month
    save_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    file_path = save_dir / filename
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"Saved raw file to {file_path}")
    except Exception as e:
        logger.error(f"Failed to save raw file {filename}: {e}")


def load_raw_file(filename: str) -> Optional[Dict]:
    """
    Load raw visualization data from local cache.

    Looks for file in: .monitor_cache/raw_data/YYYY/MM/filename.json

    Args:
        filename: Name of the file to load

    Returns:
        Parsed JSON data dictionary, or None if file not found

    Example:
        >>> data = load_raw_file("newvelles_visualization_0.2.1_2026-04-18T10:00:00.json")
    """
    # Parse filename to extract date
    parsed = parse_visualization_filename(filename)
    if not parsed:
        logger.debug(f"Cannot load raw file with invalid filename: {filename}")
        return None

    # Extract year and month from datetime
    dt = parsed["datetime"]
    year = str(dt.year)
    month = f"{dt.month:02d}"

    # Construct file path
    file_path = RAW_DATA_DIR / year / month / filename

    if not file_path.exists():
        logger.debug(f"Raw file not found: {file_path}")
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.debug(f"Loaded raw file from {file_path}")
        return data
    except Exception as e:
        logger.error(f"Failed to load raw file {filename}: {e}")
        return None


def has_raw_file(filename: str) -> bool:
    """
    Check if raw file exists in local cache.

    Args:
        filename: Name of the file to check

    Returns:
        True if file exists in cache, False otherwise
    """
    parsed = parse_visualization_filename(filename)
    if not parsed:
        return False

    dt = parsed["datetime"]
    year = str(dt.year)
    month = f"{dt.month:02d}"

    file_path = RAW_DATA_DIR / year / month / filename
    return file_path.exists()
