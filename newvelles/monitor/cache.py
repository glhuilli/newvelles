"""Cache manager for monitoring dashboard."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Set, Optional

from newvelles.monitor.config import CACHE_DIR, FILE_INDEX_PATH, DAILY_METRICS_PATH

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages local JSON cache files for the monitoring dashboard.

    Handles two cache files:
    - file_index.json: Tracks processed S3 files with metadata
    - daily_metrics.json: Stores daily metrics aggregations
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize cache manager.

        Args:
            cache_dir: Optional custom cache directory path. If not provided,
                      uses default CACHE_DIR from config.
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
            self.file_index_path = self.cache_dir / "file_index.json"
            self.daily_metrics_path = self.cache_dir / "daily_metrics.json"
        else:
            self.cache_dir = CACHE_DIR
            self.file_index_path = FILE_INDEX_PATH
            self.daily_metrics_path = DAILY_METRICS_PATH

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Cache manager initialized with cache_dir: {self.cache_dir}")

    def load_file_index(self) -> dict:
        """
        Load file index from cache.

        Returns:
            Dictionary containing file index data. If file doesn't exist or
            is invalid, returns empty structure with defaults.

        Structure:
            {
                "last_updated": "2026-04-18T10:30:00",
                "total_files": 8614,
                "files": {
                    "filename.json": {
                        "processed": true,
                        "size_kb": 255,
                        "articles": 150,
                        "groups": 45,
                        "timestamp": "2026-04-16T13:14:38"
                    }
                }
            }
        """
        if not self.file_index_path.exists():
            logger.debug("File index not found, returning empty structure")
            return {
                "last_updated": datetime.utcnow().isoformat(),
                "total_files": 0,
                "files": {}
            }

        try:
            with open(self.file_index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"Loaded file index with {len(data.get('files', {}))} files")
                return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode file index JSON: {e}")
            return {
                "last_updated": datetime.utcnow().isoformat(),
                "total_files": 0,
                "files": {}
            }
        except Exception as e:
            logger.error(f"Failed to load file index: {e}")
            return {
                "last_updated": datetime.utcnow().isoformat(),
                "total_files": 0,
                "files": {}
            }

    def save_file_index(self, index: dict) -> None:
        """
        Save file index to cache.

        Args:
            index: Dictionary containing file index data

        Raises:
            Exception: If save operation fails
        """
        try:
            # Update last_updated timestamp and total_files count
            index["last_updated"] = datetime.utcnow().isoformat()
            index["total_files"] = len(index.get("files", {}))

            with open(self.file_index_path, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved file index with {index['total_files']} files")
        except Exception as e:
            logger.error(f"Failed to save file index: {e}")
            raise

    def load_daily_metrics(self) -> dict:
        """
        Load daily metrics from cache.

        Returns:
            Dictionary containing daily metrics data. If file doesn't exist or
            is invalid, returns empty structure.

        Structure:
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
        """
        if not self.daily_metrics_path.exists():
            logger.debug("Daily metrics not found, returning empty structure")
            return {}

        try:
            with open(self.daily_metrics_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"Loaded daily metrics for {len(data)} days")
                return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode daily metrics JSON: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load daily metrics: {e}")
            return {}

    def save_daily_metrics(self, metrics: dict) -> None:
        """
        Save daily metrics to cache.

        Args:
            metrics: Dictionary containing daily metrics data

        Raises:
            Exception: If save operation fails
        """
        try:
            with open(self.daily_metrics_path, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved daily metrics for {len(metrics)} days")
        except Exception as e:
            logger.error(f"Failed to save daily metrics: {e}")
            raise

    def get_known_files(self) -> Set[str]:
        """
        Get set of filenames that have been processed.

        Returns:
            Set of processed filenames from the file index
        """
        index = self.load_file_index()
        known_files = set(index.get("files", {}).keys())
        logger.debug(f"Retrieved {len(known_files)} known files from cache")
        return known_files

    def add_file(self, filename: str, metadata: dict) -> None:
        """
        Add a file to the index with its metadata.

        Args:
            filename: Name of the S3 file
            metadata: Dictionary containing file metadata with keys:
                     - processed (bool): Whether file has been processed
                     - size_kb (int): File size in kilobytes
                     - articles (int): Number of articles
                     - groups (int): Number of groups
                     - timestamp (str): ISO format timestamp

        Raises:
            Exception: If save operation fails
        """
        try:
            index = self.load_file_index()

            # Ensure files dict exists
            if "files" not in index:
                index["files"] = {}

            # Add or update file metadata
            index["files"][filename] = metadata

            # Save updated index
            self.save_file_index(index)

            logger.debug(f"Added file to index: {filename}")
        except Exception as e:
            logger.error(f"Failed to add file to index: {e}")
            raise

    def update_daily_metrics(self, date: str, update_data: dict) -> None:
        """
        Update daily metrics with new update data.

        Args:
            date: Date string in YYYY-MM-DD format
            update_data: Dictionary containing update metrics with keys:
                        - timestamp (str): ISO format timestamp
                        - total_articles (int): Total articles in update
                        - total_groups (int): Total groups in update
                        - top_level_groups (int): Number of top-level groups
                        - sub_groups (int): Number of sub-groups

        Raises:
            Exception: If save operation fails
        """
        try:
            metrics = self.load_daily_metrics()

            # Initialize date entry if it doesn't exist
            if date not in metrics:
                metrics[date] = {
                    "updates": [],
                    "daily_total_articles": 0,
                    "daily_total_groups": 0,
                    "daily_avg_articles_per_update": 0.0
                }

            # Add update to the list
            metrics[date]["updates"].append(update_data)

            # Recalculate daily aggregations
            updates = metrics[date]["updates"]
            total_articles = sum(u.get("total_articles", 0) for u in updates)
            total_groups = sum(u.get("total_groups", 0) for u in updates)
            num_updates = len(updates)

            metrics[date]["updates_count"] = num_updates
            metrics[date]["daily_total_articles"] = total_articles
            metrics[date]["daily_total_groups"] = total_groups
            metrics[date]["daily_avg_articles_per_update"] = (
                total_articles / num_updates if num_updates > 0 else 0.0
            )

            # Save updated metrics
            self.save_daily_metrics(metrics)

            logger.debug(f"Updated daily metrics for {date}: {len(updates)} updates")
        except Exception as e:
            logger.error(f"Failed to update daily metrics: {e}")
            raise
