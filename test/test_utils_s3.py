"""Tests for newvelles.utils.s3 module."""

from unittest.mock import Mock, patch

import pytest

from newvelles.utils.s3 import upload_to_s3


class TestUploadToS3:
    """Test upload_to_s3 function."""

    @patch("newvelles.utils.s3.boto3.resource")
    def test_upload_to_s3_basic(self, mock_boto3_resource):
        """Test basic functionality of upload_to_s3."""
        # Mock AWS S3 resource
        mock_s3_resource = Mock()
        mock_s3_object = Mock()
        mock_boto3_resource.return_value = mock_s3_resource
        mock_s3_resource.Object.return_value = mock_s3_object

        bucket_name = "test-bucket"
        file_name = "test-file.json"
        string_byte = b'{"test": "data"}'

        upload_to_s3(bucket_name, file_name, string_byte, public_read=False)

        # Verify boto3 resource was called correctly
        mock_boto3_resource.assert_called_once_with("s3")
        mock_s3_resource.Object.assert_called_once_with(bucket_name, file_name)
        mock_s3_object.put.assert_called_once_with(Body=string_byte)

        # ACL should not be set when public_read=False
        mock_s3_object.Acl.assert_not_called()

    @patch("newvelles.utils.s3.boto3.resource")
    def test_upload_to_s3_public_read(self, mock_boto3_resource):
        """Test upload_to_s3 with public_read=True."""
        # Mock AWS S3 resource
        mock_s3_resource = Mock()
        mock_s3_object = Mock()
        mock_acl = Mock()
        mock_boto3_resource.return_value = mock_s3_resource
        mock_s3_resource.Object.return_value = mock_s3_object
        mock_s3_object.Acl.return_value = mock_acl

        bucket_name = "test-bucket"
        file_name = "test-file.json"
        string_byte = b'{"test": "data"}'

        upload_to_s3(bucket_name, file_name, string_byte, public_read=True)

        # Verify boto3 resource was called correctly
        mock_boto3_resource.assert_called_once_with("s3")
        mock_s3_resource.Object.assert_called_once_with(bucket_name, file_name)
        mock_s3_object.put.assert_called_once_with(Body=string_byte)

        # ACL should be set to public-read when public_read=True
        mock_s3_object.Acl.assert_called_once()
        mock_acl.put.assert_called_once_with(ACL="public-read")

    @patch("newvelles.utils.s3.boto3.resource")
    def test_upload_to_s3_string_data(self, mock_boto3_resource):
        """Test upload_to_s3 with string data."""
        # Mock AWS S3 resource
        mock_s3_resource = Mock()
        mock_s3_object = Mock()
        mock_boto3_resource.return_value = mock_s3_resource
        mock_s3_resource.Object.return_value = mock_s3_object

        bucket_name = "test-bucket"
        file_name = "test-file.txt"
        string_data = "This is test data"

        upload_to_s3(bucket_name, file_name, string_data, public_read=False)

        # Verify the string data was passed correctly
        mock_s3_object.put.assert_called_once_with(Body=string_data)

    @patch("newvelles.utils.s3.boto3.resource")
    def test_upload_to_s3_with_special_characters(self, mock_boto3_resource):
        """Test upload_to_s3 with special characters in file name."""
        # Mock AWS S3 resource
        mock_s3_resource = Mock()
        mock_s3_object = Mock()
        mock_boto3_resource.return_value = mock_s3_resource
        mock_s3_resource.Object.return_value = mock_s3_object

        bucket_name = "test-bucket"
        file_name = "path/to/test file with spaces.json"
        string_byte = b'{"test": "data"}'

        upload_to_s3(bucket_name, file_name, string_byte)

        # Should handle special characters in file name
        mock_s3_resource.Object.assert_called_once_with(bucket_name, file_name)
        mock_s3_object.put.assert_called_once_with(Body=string_byte)

    @patch("newvelles.utils.s3.boto3.resource")
    def test_upload_to_s3_empty_data(self, mock_boto3_resource):
        """Test upload_to_s3 with empty data."""
        # Mock AWS S3 resource
        mock_s3_resource = Mock()
        mock_s3_object = Mock()
        mock_boto3_resource.return_value = mock_s3_resource
        mock_s3_resource.Object.return_value = mock_s3_object

        bucket_name = "test-bucket"
        file_name = "empty-file.txt"
        string_byte = b""

        upload_to_s3(bucket_name, file_name, string_byte)

        # Should handle empty data
        mock_s3_object.put.assert_called_once_with(Body=string_byte)

    @patch("newvelles.utils.s3.boto3.resource")
    def test_upload_to_s3_large_file_name(self, mock_boto3_resource):
        """Test upload_to_s3 with long file name."""
        # Mock AWS S3 resource
        mock_s3_resource = Mock()
        mock_s3_object = Mock()
        mock_boto3_resource.return_value = mock_s3_resource
        mock_s3_resource.Object.return_value = mock_s3_object

        bucket_name = "test-bucket"
        file_name = "a" * 1000 + ".json"  # Very long file name
        string_byte = b'{"test": "data"}'

        upload_to_s3(bucket_name, file_name, string_byte)

        # Should handle long file names
        mock_s3_resource.Object.assert_called_once_with(bucket_name, file_name)
        mock_s3_object.put.assert_called_once_with(Body=string_byte)
