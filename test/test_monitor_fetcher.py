"""Tests for newvelles.monitor.fetcher module."""

import json
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import ClientError, NoCredentialsError

from newvelles.monitor.fetcher import (_download_file_with_retry, download_file,
                                       fetch_incremental_data, get_file_count, get_latest_metadata,
                                       list_s3_files, parse_visualization_filename)


class TestListS3Files:
    """Test list_s3_files function."""

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_list_s3_files_basic(self, mock_boto3_client):
        """Test basic listing of S3 files."""
        # Mock S3 client and paginator
        mock_s3_client = Mock()
        mock_paginator = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_paginator.return_value = mock_paginator

        # Mock single page response
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "file1.json"},
                    {"Key": "file2.json"},
                    {"Key": "file3.json"},
                ]
            }
        ]

        bucket = "test-bucket"
        result = list_s3_files(bucket)

        assert len(result) == 3
        assert "file1.json" in result
        assert "file2.json" in result
        assert "file3.json" in result

        mock_s3_client.get_paginator.assert_called_once_with("list_objects_v2")
        mock_paginator.paginate.assert_called_once_with(Bucket=bucket, Prefix="")

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_list_s3_files_with_prefix(self, mock_boto3_client):
        """Test listing S3 files with prefix filter."""
        mock_s3_client = Mock()
        mock_paginator = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_paginator.return_value = mock_paginator

        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": "prefix/file1.json"}, {"Key": "prefix/file2.json"}]}
        ]

        bucket = "test-bucket"
        prefix = "prefix/"
        result = list_s3_files(bucket, prefix)

        assert len(result) == 2
        mock_paginator.paginate.assert_called_once_with(Bucket=bucket, Prefix=prefix)

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_list_s3_files_pagination(self, mock_boto3_client):
        """Test listing S3 files with multiple pages (large bucket)."""
        mock_s3_client = Mock()
        mock_paginator = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_paginator.return_value = mock_paginator

        # Mock multiple pages
        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": f"file{i}.json"} for i in range(1000)]},
            {"Contents": [{"Key": f"file{i}.json"} for i in range(1000, 2000)]},
            {"Contents": [{"Key": f"file{i}.json"} for i in range(2000, 2500)]},
        ]

        result = list_s3_files("test-bucket")

        assert len(result) == 2500

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_list_s3_files_empty_bucket(self, mock_boto3_client):
        """Test listing files from empty bucket."""
        mock_s3_client = Mock()
        mock_paginator = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_paginator.return_value = mock_paginator

        # Empty bucket has no Contents key
        mock_paginator.paginate.return_value = [{}]

        result = list_s3_files("test-bucket")

        assert len(result) == 0

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_list_s3_files_no_credentials(self, mock_boto3_client):
        """Test handling of missing AWS credentials."""
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_paginator.side_effect = NoCredentialsError()

        with pytest.raises(NoCredentialsError):
            list_s3_files("test-bucket")

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_list_s3_files_client_error(self, mock_boto3_client):
        """Test handling of S3 client errors."""
        mock_s3_client = Mock()
        mock_paginator = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_paginator.return_value = mock_paginator

        error_response = {"Error": {"Code": "NoSuchBucket"}}
        mock_paginator.paginate.side_effect = ClientError(error_response, "ListObjects")

        with pytest.raises(ClientError):
            list_s3_files("nonexistent-bucket")


class TestGetLatestMetadata:
    """Test get_latest_metadata function."""

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_get_latest_metadata_success(self, mock_boto3_client):
        """Test successful metadata fetch."""
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client

        metadata = {
            "datetime": "2025-01-16T10:30:45",
            "version": "0.2.1",
        }

        mock_response = {
            "Body": MagicMock(read=lambda: json.dumps(metadata).encode("utf-8"))
        }
        mock_s3_client.get_object.return_value = mock_response

        result = get_latest_metadata()

        assert result == metadata
        mock_s3_client.get_object.assert_called_once()

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_get_latest_metadata_not_found(self, mock_boto3_client):
        """Test handling of missing metadata file."""
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client

        error_response = {"Error": {"Code": "NoSuchKey"}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, "GetObject")

        with pytest.raises(ClientError):
            get_latest_metadata()

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_get_latest_metadata_access_denied(self, mock_boto3_client):
        """Test handling of access denied error."""
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client

        error_response = {"Error": {"Code": "AccessDenied"}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, "GetObject")

        with pytest.raises(ClientError):
            get_latest_metadata()


class TestDownloadFile:
    """Test download_file function."""

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_download_file_success(self, mock_boto3_client):
        """Test successful file download."""
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client

        test_data = {"test": "data", "number": 123}
        mock_response = {
            "Body": MagicMock(read=lambda: json.dumps(test_data).encode("utf-8"))
        }
        mock_s3_client.get_object.return_value = mock_response

        result = download_file("test-bucket", "test-file.json")

        assert result == test_data
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="test-file.json"
        )

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_download_file_invalid_json(self, mock_boto3_client):
        """Test handling of invalid JSON in downloaded file."""
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client

        mock_response = {"Body": MagicMock(read=lambda: b"not valid json")}
        mock_s3_client.get_object.return_value = mock_response

        with pytest.raises(json.JSONDecodeError):
            download_file("test-bucket", "invalid-file.json")

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_download_file_not_found(self, mock_boto3_client):
        """Test handling of missing file."""
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client

        error_response = {"Error": {"Code": "NoSuchKey"}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, "GetObject")

        with pytest.raises(ClientError):
            download_file("test-bucket", "missing-file.json")

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_download_file_empty_json(self, mock_boto3_client):
        """Test downloading empty JSON object."""
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client

        mock_response = {"Body": MagicMock(read=lambda: b"{}")}
        mock_s3_client.get_object.return_value = mock_response

        result = download_file("test-bucket", "empty-file.json")

        assert result == {}


class TestDownloadFileWithRetry:
    """Test _download_file_with_retry internal helper."""

    @patch("newvelles.monitor.fetcher.download_file")
    def test_download_file_with_retry_success_first_try(self, mock_download_file):
        """Test successful download on first attempt."""
        test_data = {"test": "data"}
        mock_download_file.return_value = test_data

        result = _download_file_with_retry("test-bucket", "test-file.json")

        assert result == ("test-file.json", test_data)
        assert mock_download_file.call_count == 1

    @patch("newvelles.monitor.fetcher.download_file")
    def test_download_file_with_retry_success_after_retries(self, mock_download_file):
        """Test successful download after failed attempts."""
        test_data = {"test": "data"}
        error_response = {"Error": {"Code": "ServiceUnavailable"}}

        # Fail twice, succeed on third attempt
        mock_download_file.side_effect = [
            ClientError(error_response, "GetObject"),
            ClientError(error_response, "GetObject"),
            test_data,
        ]

        result = _download_file_with_retry("test-bucket", "test-file.json")

        assert result == ("test-file.json", test_data)
        assert mock_download_file.call_count == 3

    @patch("newvelles.monitor.fetcher.download_file")
    def test_download_file_with_retry_all_retries_fail(self, mock_download_file):
        """Test failure after all retries exhausted."""
        error_response = {"Error": {"Code": "ServiceUnavailable"}}
        mock_download_file.side_effect = ClientError(error_response, "GetObject")

        result = _download_file_with_retry(
            "test-bucket", "test-file.json", max_retries=3
        )

        assert result is None
        assert mock_download_file.call_count == 3

    @patch("newvelles.monitor.fetcher.download_file")
    def test_download_file_with_retry_json_error(self, mock_download_file):
        """Test retry behavior with JSON decode errors."""
        mock_download_file.side_effect = json.JSONDecodeError("Invalid", "", 0)

        result = _download_file_with_retry(
            "test-bucket", "test-file.json", max_retries=2
        )

        assert result is None
        assert mock_download_file.call_count == 2


class TestFetchIncrementalData:
    """Test fetch_incremental_data function."""

    @patch("newvelles.monitor.fetcher.list_s3_files")
    @patch("newvelles.monitor.fetcher._download_file_with_retry")
    def test_fetch_incremental_data_basic(
        self, mock_download_with_retry, mock_list_s3_files
    ):
        """Test basic incremental data fetch."""
        # Mock S3 listing
        all_files = [
            "file1.json",
            "file2.json",
            "file3.json",
            "file4.json",
        ]
        mock_list_s3_files.return_value = all_files

        # Known files (already processed)
        known_files = {"file1.json", "file2.json"}

        # Mock downloads
        mock_download_with_retry.side_effect = [
            ("file3.json", {"data": "3"}),
            ("file4.json", {"data": "4"}),
        ]

        result = fetch_incremental_data(known_files, bucket="test-bucket")

        # Should only download new files
        assert len(result) == 2
        assert ("file3.json", {"data": "3"}) in result
        assert ("file4.json", {"data": "4"}) in result

    @patch("newvelles.monitor.fetcher.list_s3_files")
    @patch("newvelles.monitor.fetcher._download_file_with_retry")
    def test_fetch_incremental_data_no_new_files(
        self, mock_download_with_retry, mock_list_s3_files
    ):
        """Test when all files are already known."""
        all_files = ["file1.json", "file2.json"]
        mock_list_s3_files.return_value = all_files

        known_files = {"file1.json", "file2.json"}

        result = fetch_incremental_data(known_files, bucket="test-bucket")

        assert len(result) == 0
        mock_download_with_retry.assert_not_called()

    @patch("newvelles.monitor.fetcher.list_s3_files")
    @patch("newvelles.monitor.fetcher._download_file_with_retry")
    def test_fetch_incremental_data_all_new_files(
        self, mock_download_with_retry, mock_list_s3_files
    ):
        """Test when all files are new."""
        all_files = ["file1.json", "file2.json", "file3.json"]
        mock_list_s3_files.return_value = all_files

        known_files = set()  # No known files

        mock_download_with_retry.side_effect = [
            ("file1.json", {"data": "1"}),
            ("file2.json", {"data": "2"}),
            ("file3.json", {"data": "3"}),
        ]

        result = fetch_incremental_data(known_files, bucket="test-bucket")

        assert len(result) == 3

    @patch("newvelles.monitor.fetcher.list_s3_files")
    @patch("newvelles.monitor.fetcher._download_file_with_retry")
    def test_fetch_incremental_data_filters_non_json(
        self, mock_download_with_retry, mock_list_s3_files
    ):
        """Test that non-JSON files are filtered out."""
        all_files = [
            "file1.json",
            "file2.txt",
            "file3.csv",
            "file4.json",
        ]
        mock_list_s3_files.return_value = all_files

        known_files = set()

        mock_download_with_retry.side_effect = [
            ("file1.json", {"data": "1"}),
            ("file4.json", {"data": "4"}),
        ]

        result = fetch_incremental_data(known_files, bucket="test-bucket")

        # Should only download JSON files
        assert len(result) == 2
        assert mock_download_with_retry.call_count == 2

    @patch("newvelles.monitor.fetcher.list_s3_files")
    @patch("newvelles.monitor.fetcher._download_file_with_retry")
    def test_fetch_incremental_data_handles_failed_downloads(
        self, mock_download_with_retry, mock_list_s3_files
    ):
        """Test handling of failed downloads (returns None)."""
        all_files = ["file1.json", "file2.json", "file3.json"]
        mock_list_s3_files.return_value = all_files

        known_files = set()

        # One download fails (returns None)
        mock_download_with_retry.side_effect = [
            ("file1.json", {"data": "1"}),
            None,  # file2.json fails
            ("file3.json", {"data": "3"}),
        ]

        result = fetch_incremental_data(known_files, bucket="test-bucket")

        # Should only include successful downloads
        assert len(result) == 2
        assert ("file1.json", {"data": "1"}) in result
        assert ("file3.json", {"data": "3"}) in result

    @patch("newvelles.monitor.fetcher.list_s3_files")
    @patch("newvelles.monitor.fetcher.ThreadPoolExecutor")
    def test_fetch_incremental_data_uses_parallel_downloads(
        self, mock_executor_class, mock_list_s3_files
    ):
        """Test that parallel downloads are used."""
        all_files = [f"file{i}.json" for i in range(5)]
        mock_list_s3_files.return_value = all_files
        known_files = set()

        # Mock ThreadPoolExecutor
        mock_executor = MagicMock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        # Mock futures
        mock_futures = []
        for i in range(5):
            mock_future = Mock()
            mock_future.result.return_value = (f"file{i}.json", {"data": str(i)})
            mock_futures.append(mock_future)

        mock_executor.submit.side_effect = mock_futures

        # Mock as_completed
        with patch("newvelles.monitor.fetcher.as_completed", return_value=mock_futures):
            result = fetch_incremental_data(known_files, bucket="test-bucket")

        assert len(result) == 5
        # Verify ThreadPoolExecutor was used
        assert mock_executor.submit.call_count == 5


class TestParseVisualizationFilename:
    """Test parse_visualization_filename function."""

    def test_parse_visualization_filename_valid(self):
        """Test parsing valid visualization filename."""
        filename = "newvelles_visualization_0.2.1_2025-01-16T10:30:45.json"
        result = parse_visualization_filename(filename)

        assert result is not None
        assert result["version"] == "0.2.1"
        assert result["timestamp"] == "2025-01-16T10:30:45"
        assert result["datetime"] == datetime(2025, 1, 16, 10, 30, 45)

    def test_parse_visualization_filename_different_version(self):
        """Test parsing with different version number."""
        filename = "newvelles_visualization_1.0.0_2026-04-16T13:14:38.json"
        result = parse_visualization_filename(filename)

        assert result is not None
        assert result["version"] == "1.0.0"
        assert result["timestamp"] == "2026-04-16T13:14:38"
        assert result["datetime"] == datetime(2026, 4, 16, 13, 14, 38)

    def test_parse_visualization_filename_invalid_format(self):
        """Test parsing invalid filename format."""
        invalid_filenames = [
            "wrong_format.json",
            "newvelles_0.2.1_2025-01-16T10:30:45.json",  # Missing visualization
            "newvelles_visualization_2025-01-16T10:30:45.json",  # Missing version
            "newvelles_visualization_0.2.1.json",  # Missing timestamp
            "random_file.json",
        ]

        for filename in invalid_filenames:
            result = parse_visualization_filename(filename)
            assert result is None, f"Should reject invalid filename: {filename}"

    def test_parse_visualization_filename_invalid_timestamp(self):
        """Test parsing with invalid timestamp format."""
        filename = "newvelles_visualization_0.2.1_2025-99-99T99:99:99.json"
        result = parse_visualization_filename(filename)

        # Should match pattern but fail datetime parsing
        assert result is None

    def test_parse_visualization_filename_edge_cases(self):
        """Test edge cases for filename parsing."""
        # Valid edge cases
        valid_cases = [
            "newvelles_visualization_10.20.30_2025-01-01T00:00:00.json",
            "newvelles_visualization_0.0.1_2025-12-31T23:59:59.json",
        ]

        for filename in valid_cases:
            result = parse_visualization_filename(filename)
            assert result is not None, f"Should accept valid filename: {filename}"

    def test_parse_visualization_filename_no_extension(self):
        """Test parsing filename without .json extension."""
        filename = "newvelles_visualization_0.2.1_2025-01-16T10:30:45"
        result = parse_visualization_filename(filename)

        assert result is None


class TestGetFileCount:
    """Test get_file_count function."""

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_get_file_count_basic(self, mock_boto3_client):
        """Test basic file count."""
        mock_s3_client = Mock()
        mock_paginator = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_paginator.return_value = mock_paginator

        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": f"file{i}.json"} for i in range(50)]}
        ]

        count = get_file_count("test-bucket")

        assert count == 50

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_get_file_count_multiple_pages(self, mock_boto3_client):
        """Test file count with pagination."""
        mock_s3_client = Mock()
        mock_paginator = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_paginator.return_value = mock_paginator

        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": f"file{i}.json"} for i in range(1000)]},
            {"Contents": [{"Key": f"file{i}.json"} for i in range(500)]},
        ]

        count = get_file_count("test-bucket")

        assert count == 1500

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_get_file_count_empty_bucket(self, mock_boto3_client):
        """Test file count on empty bucket."""
        mock_s3_client = Mock()
        mock_paginator = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_paginator.return_value = mock_paginator

        mock_paginator.paginate.return_value = [{}]

        count = get_file_count("test-bucket")

        assert count == 0

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_get_file_count_with_prefix(self, mock_boto3_client):
        """Test file count with prefix filter."""
        mock_s3_client = Mock()
        mock_paginator = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_paginator.return_value = mock_paginator

        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": f"prefix/file{i}.json"} for i in range(10)]}
        ]

        count = get_file_count("test-bucket", prefix="prefix/")

        assert count == 10
        mock_paginator.paginate.assert_called_once_with(
            Bucket="test-bucket", Prefix="prefix/"
        )

    @patch("newvelles.monitor.fetcher.boto3.client")
    def test_get_file_count_client_error(self, mock_boto3_client):
        """Test handling of S3 client errors."""
        mock_s3_client = Mock()
        mock_paginator = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_paginator.return_value = mock_paginator

        error_response = {"Error": {"Code": "AccessDenied"}}
        mock_paginator.paginate.side_effect = ClientError(error_response, "ListObjects")

        with pytest.raises(ClientError):
            get_file_count("test-bucket")
