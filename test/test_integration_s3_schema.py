"""Integration tests for S3 upload schema validation."""

import json
import os
import tempfile
import time
from unittest.mock import Mock, patch
from typing import Dict, Any, List

import boto3
import pytest
import jsonschema
from moto import mock_aws

from newvelles.feed.log import log_s3
from newvelles.models.grouping import build_visualization
from newvelles.feed.load import build_data_from_rss_feeds_list


class TestS3SchemaValidation:
    """Integration tests for S3 upload and schema validation."""

    @pytest.fixture
    def schema_loader(self):
        """Load JSON schemas from files."""
        def _load_schema(schema_name: str) -> Dict[str, Any]:
            schema_path = os.path.join("schemas", f"{schema_name}_schema.json")
            with open(schema_path, "r") as f:
                return json.load(f)
        return _load_schema

    @pytest.fixture
    def s3_mock_setup(self):
        """Setup mock S3 environment for testing."""
        with mock_aws():
            s3_client = boto3.client("s3", region_name="us-west-2")
            bucket_name = "test-newvelles-bucket"
            public_bucket_name = "test-public-newvelles-bucket"
            
            # Create test buckets
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': 'us-west-2'}
            )
            s3_client.create_bucket(
                Bucket=public_bucket_name,
                CreateBucketConfiguration={'LocationConstraint': 'us-west-2'}
            )
            
            yield {
                "client": s3_client,
                "bucket": bucket_name,
                "public_bucket": public_bucket_name
            }

    @pytest.fixture
    def mock_rss_data(self):
        """Create mock RSS data for testing."""
        from newvelles.feed import NewsEntry
        
        return {
            "Sample News Title 1": NewsEntry(
                title="Sample News Title 1",
                link="https://example.com/news1",
                published="2024-01-15T10:00:00Z",
                title_detail_base="https://example.com"
            ),
            "Sample News Title 2": NewsEntry(
                title="Sample News Title 2", 
                link="https://example.com/news2",
                published="2024-01-15T11:00:00Z",
                title_detail_base="https://example.com"
            ),
            "Different Topic News": NewsEntry(
                title="Different Topic News",
                link="https://example.com/news3", 
                published="2024-01-15T12:00:00Z",
                title_detail_base="https://example.com"
            )
        }

    def test_s3_upload_schema_validation(self, schema_loader, mock_rss_data, s3_mock_setup):
        """Test that S3 uploads conform to the JSON schema."""
        s3_client = s3_mock_setup["client"]
        bucket_name = s3_mock_setup["bucket"]
        public_bucket_name = s3_mock_setup["public_bucket"]

        # Mock the S3 bucket configuration in the log module
        with patch('newvelles.feed.log._S3_BUCKET', bucket_name), \
             patch('newvelles.feed.log._S3_PUBLIC_BUCKET', public_bucket_name):
            # Generate visualization data
            visualization_data, _ = build_visualization(mock_rss_data, cluster_limit=1)
            
            # Upload to S3
            log_s3(visualization_data)
            
            # Verify files were uploaded
            objects = s3_client.list_objects_v2(Bucket=public_bucket_name)
            assert 'Contents' in objects
            
            uploaded_files = {obj['Key'] for obj in objects['Contents']}
            assert 'latest_news.json' in uploaded_files
            assert 'latest_news_metadata.json' in uploaded_files
            
            # Download and validate latest_news.json
            news_obj = s3_client.get_object(Bucket=public_bucket_name, Key='latest_news.json')
            news_data = json.loads(news_obj['Body'].read().decode('utf-8'))
            
            # Validate against schema
            news_schema = schema_loader("latest_news")
            jsonschema.validate(news_data, news_schema)
            
            # Download and validate latest_news_metadata.json  
            metadata_obj = s3_client.get_object(Bucket=public_bucket_name, Key='latest_news_metadata.json')
            metadata_data = json.loads(metadata_obj['Body'].read().decode('utf-8'))
            
            # Validate against schema
            metadata_schema = schema_loader("latest_news_metadata")
            jsonschema.validate(metadata_data, metadata_schema)
            
            # Additional content validation
            assert isinstance(news_data, dict)
            assert len(news_data) > 0
            
            # Check metadata structure
            assert 'datetime' in metadata_data
            assert 'version' in metadata_data
            assert len(metadata_data['datetime']) > 0
            assert len(metadata_data['version']) > 0

    def test_schema_validation_with_real_example(self, schema_loader):
        """Test schema validation against real example data."""
        # Test with the actual example files
        with open("data/latest_news_metadata_example.json", "r") as f:
            metadata_example = json.load(f)
        
        # Validate metadata example
        metadata_schema = schema_loader("latest_news_metadata")
        jsonschema.validate(metadata_example, metadata_schema)
        
        # Test a small portion of the news data (since the full file is too large)
        news_sample = {
            "sample_group": {
                "sample_subgroup": {
                    "Sample Article": {
                        "title": "Sample Article",
                        "link": "https://example.com/article",
                        "timestamp": "Mon, 25 Nov 2024 08:03:10 +0000",
                        "source": "https://example.com/rss"
                    }
                }
            }
        }
        
        # Validate news sample
        news_schema = schema_loader("latest_news")
        jsonschema.validate(news_sample, news_schema)

    def test_schema_validation_failures(self, schema_loader):
        """Test that invalid data correctly fails schema validation."""
        news_schema = schema_loader("latest_news")
        metadata_schema = schema_loader("latest_news_metadata")
        
        # Test invalid news data - missing required fields
        invalid_news_data = {
            "group": {
                "subgroup": {
                    "article": {
                        "title": "Valid Title",
                        "link": "not-a-valid-url",  # Invalid URL
                        # Missing required timestamp and source
                    }
                }
            }
        }
        
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_news_data, news_schema)
        
        # Test invalid news data - wrong data types
        invalid_news_type = {
            "group": {
                "subgroup": {
                    "article": {
                        "title": 123,  # Should be string
                        "link": "https://example.com",
                        "timestamp": "2024-01-15T10:00:00Z",
                        "source": "https://example.com/rss"
                    }
                }
            }
        }
        
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_news_type, news_schema)
        
        # Test invalid metadata - wrong date format
        invalid_metadata = {
            "datetime": "invalid-date-format",  # Invalid format
            "version": "not.semantic.version.format.too.many.parts"  # Invalid version
        }
        
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_metadata, metadata_schema)
        
        # Test invalid metadata - missing required fields
        incomplete_metadata = {
            "datetime": "2024-01-15T10:30:45"
            # Missing version field
        }
        
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(incomplete_metadata, metadata_schema)
        
        # Test invalid metadata - additional properties
        metadata_with_extra = {
            "datetime": "2024-01-15T10:30:45",
            "version": "1.0.0",
            "extra_field": "not allowed"  # Additional properties not allowed
        }
        
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(metadata_with_extra, metadata_schema)

    @patch('handler.build_visualization')
    def test_end_to_end_lambda_s3_validation(self, mock_build_viz, schema_loader, s3_mock_setup):
        """End-to-end test: Lambda execution -> S3 upload -> Schema validation."""
        s3_client = s3_mock_setup["client"]
        bucket_name = s3_mock_setup["bucket"]
        public_bucket_name = s3_mock_setup["public_bucket"]
        
        # Mock the build_visualization function to return valid test data
        mock_visualization_data = {
            "Politics": {
                "Elections": {
                    "Breaking political developments reshape election campaign strategies": {
                        "title": "Breaking political developments reshape election campaign strategies",
                        "link": "https://news.com/breaking",
                        "timestamp": "2024-01-15T14:30:00Z",
                        "source": "https://news.com"
                    }
                }
            },
            "Technology": {
                "AI": {
                    "Revolutionary artificial intelligence transforms healthcare industry applications": {
                        "title": "Revolutionary artificial intelligence transforms healthcare industry applications",
                        "link": "https://tech.com/update",
                        "timestamp": "2024-01-15T15:00:00Z",
                        "source": "https://tech.com"
                    }
                }
            }
        }
        mock_group_sentences = {0: ["politics", "election"], 1: ["technology", "ai"]}
        mock_build_viz.return_value = (mock_visualization_data, mock_group_sentences)
        
        # Mock the S3 bucket configuration in the log module  
        with patch('newvelles.feed.log._S3_BUCKET', bucket_name), \
             patch('newvelles.feed.log._S3_PUBLIC_BUCKET', public_bucket_name):
            # Import and run the handler's run function
            from handler import run
            
            result = run()
            assert result is True
            
            # Verify S3 uploads and validate schemas
            objects = s3_client.list_objects_v2(Bucket=public_bucket_name)
            assert 'Contents' in objects
            
            # Download and validate both files
            for key in ['latest_news.json', 'latest_news_metadata.json']:
                obj = s3_client.get_object(Bucket=public_bucket_name, Key=key)
                data = json.loads(obj['Body'].read().decode('utf-8'))
                
                if key == 'latest_news.json':
                    schema = schema_loader("latest_news")
                else:
                    schema = schema_loader("latest_news_metadata")
                
                # This should not raise any validation errors
                jsonschema.validate(data, schema)


    def test_s3_upload_large_data_validation(self, schema_loader, s3_mock_setup):
        """Test schema validation with large datasets to ensure performance."""
        s3_client = s3_mock_setup["client"]
        bucket_name = s3_mock_setup["bucket"]
        public_bucket_name = s3_mock_setup["public_bucket"]
        
        # Create a large mock dataset
        from newvelles.feed import NewsEntry
        large_mock_data = {}
        
        # Generate 100 news entries across 10 groups
        for group_idx in range(10):
            group_name = f"Group {group_idx}"
            large_mock_data[group_name] = {}
            
            for subgroup_idx in range(2):
                subgroup_name = f"SubGroup {subgroup_idx}"
                large_mock_data[group_name][subgroup_name] = {}
                
                for article_idx in range(5):
                    article_title = f"Article {article_idx} in {group_name} {subgroup_name}"
                    large_mock_data[group_name][subgroup_name][article_title] = NewsEntry(
                        title=article_title,
                        link=f"https://example.com/article-{group_idx}-{subgroup_idx}-{article_idx}",
                        published=f"2024-01-{15 + (article_idx % 10):02d}T{10 + article_idx}:00:00Z",
                        title_detail_base="https://example.com/rss"
                    )
        
        # Mock the S3 bucket configuration
        with patch('newvelles.feed.log._S3_BUCKET', bucket_name), \
             patch('newvelles.feed.log._S3_PUBLIC_BUCKET', public_bucket_name):
            
            # Flatten the nested structure for build_visualization
            flat_data = {}
            for group_name, group_data in large_mock_data.items():
                for subgroup_name, subgroup_data in group_data.items():
                    for article_title, article_entry in subgroup_data.items():
                        flat_data[article_title] = article_entry
            
            # Generate visualization data and upload
            visualization_data, _ = build_visualization(flat_data, cluster_limit=10)
            log_s3(visualization_data)
            
            # Verify files were uploaded
            objects = s3_client.list_objects_v2(Bucket=public_bucket_name)
            assert 'Contents' in objects
            
            # Download and validate the files
            for key in ['latest_news.json', 'latest_news_metadata.json']:
                obj = s3_client.get_object(Bucket=public_bucket_name, Key=key)
                data = json.loads(obj['Body'].read().decode('utf-8'))
                
                if key == 'latest_news.json':
                    schema = schema_loader("latest_news")
                    # Validate the large dataset
                    jsonschema.validate(data, schema)
                    # Ensure we have the expected amount of data
                    assert len(data) > 0
                    
                    # Verify structure - check at least one complete article
                    for group_key, group_data in data.items():
                        assert isinstance(group_data, dict)
                        for subgroup_key, subgroup_data in group_data.items():
                            assert isinstance(subgroup_data, dict)
                            for article_key, article_data in subgroup_data.items():
                                assert "title" in article_data
                                assert "link" in article_data
                                assert "timestamp" in article_data
                                assert "source" in article_data
                                break  # Only check one article per subgroup
                            break  # Only check one subgroup per group
                        break  # Only check one group
                else:
                    schema = schema_loader("latest_news_metadata")
                    jsonschema.validate(data, schema)

    def test_schema_edge_cases(self, schema_loader):
        """Test schema validation with edge cases and boundary conditions."""
        news_schema = schema_loader("latest_news")
        metadata_schema = schema_loader("latest_news_metadata")
        
        # Test with minimal valid data
        minimal_news = {
            "a": {
                "b": {
                    "c": {
                        "title": "a",  # Minimal length title
                        "link": "https://a.com",
                        "timestamp": "Mon, 01 Jan 2024 00:00:00 +0000",
                        "source": "https://a.com/rss"
                    }
                }
            }
        }
        jsonschema.validate(minimal_news, news_schema)
        
        # Test with very long but valid data
        long_title = "Very " + "long " * 100 + "title"
        long_url = "https://example.com/" + "very/" * 50 + "long/path"
        
        long_news = {
            "Group with very long name that exceeds normal expectations": {
                "Subgroup with equally long name for testing purposes": {
                    long_title: {
                        "title": long_title,
                        "link": long_url,
                        "timestamp": "Fri, 15 Aug 2025 14:30:00 +0000",
                        "source": long_url
                    }
                }
            }
        }
        jsonschema.validate(long_news, news_schema)
        
        # Test metadata with different valid timestamp formats
        valid_timestamps = [
            "2024-01-01T00:00:00",
            "2024-12-31T23:59:59",
            "1999-01-01T00:00:00",  # Y2K edge case
            "2099-12-31T23:59:59"   # Far future
        ]
        
        for timestamp in valid_timestamps:
            metadata = {
                "datetime": timestamp,
                "version": "1.0.0"
            }
            jsonschema.validate(metadata, metadata_schema)


class TestSchemaEvolution:
    """Tests for handling schema evolution and versioning."""
    
    def test_schema_version_compatibility(self):
        """Test that schemas are compatible with different data versions."""
        # Load schema directly in the test
        def load_schema(schema_name: str) -> Dict[str, Any]:
            schema_path = os.path.join("schemas", f"{schema_name}_schema.json")
            with open(schema_path, "r") as f:
                return json.load(f)
                
        # This test can be expanded as schemas evolve
        metadata_schema = load_schema("latest_news_metadata")
        
        # Test current version format
        current_metadata = {
            "datetime": "2024-01-15T10:30:45",
            "version": "0.2.1"
        }
        
        jsonschema.validate(current_metadata, metadata_schema)
        
        # Test with different valid version formats
        for version in ["1.0.0", "10.25.3", "0.0.1"]:
            test_metadata = current_metadata.copy()
            test_metadata["version"] = version
            jsonschema.validate(test_metadata, metadata_schema)

    def test_schema_backwards_compatibility(self):
        """Test that current schemas work with older data formats."""
        def load_schema(schema_name: str) -> Dict[str, Any]:
            schema_path = os.path.join("schemas", f"{schema_name}_schema.json")
            with open(schema_path, "r") as f:
                return json.load(f)
        
        news_schema = load_schema("latest_news")
        
        # Test with various RSS timestamp formats that might appear in real data
        timestamp_formats = [
            "Mon, 25 Nov 2024 08:03:10 +0000",  # RFC 2822
            "2024-01-15T14:30:00Z",              # ISO 8601 with Z
            "Sat, 16 Aug 2025 18:51:12 +0000",   # Standard RSS format
            "Fri, 15 Aug 2025 19:51:03 GMT"      # GMT timezone
        ]
        
        for timestamp in timestamp_formats:
            news_data = {
                "test_group": {
                    "test_subgroup": {
                        "Test Article": {
                            "title": "Test Article",
                            "link": "https://example.com/article",
                            "timestamp": timestamp,
                            "source": "https://example.com/rss"
                        }
                    }
                }
            }
            jsonschema.validate(news_data, news_schema)


class TestSchemaValidationHelpers:
    """Helper functions and utilities for schema validation testing."""
    
    @staticmethod
    def validate_s3_files_against_schemas(s3_client, bucket_name: str, 
                                          schema_loader) -> List[Dict[str, Any]]:
        """Helper function to validate all JSON files in S3 bucket against schemas."""
        validation_results = []
        
        try:
            objects = s3_client.list_objects_v2(Bucket=bucket_name)
            if 'Contents' not in objects:
                return validation_results
                
            for obj in objects['Contents']:
                key = obj['Key']
                if not key.endswith('.json'):
                    continue
                    
                # Download file
                file_obj = s3_client.get_object(Bucket=bucket_name, Key=key)
                data = json.loads(file_obj['Body'].read().decode('utf-8'))
                
                # Determine schema based on filename
                if 'metadata' in key:
                    schema = schema_loader("latest_news_metadata")
                    schema_name = "latest_news_metadata"
                else:
                    schema = schema_loader("latest_news")
                    schema_name = "latest_news"
                
                # Validate
                try:
                    jsonschema.validate(data, schema)
                    validation_results.append({
                        "file": key,
                        "schema": schema_name,
                        "valid": True,
                        "error": None
                    })
                except jsonschema.ValidationError as e:
                    validation_results.append({
                        "file": key,
                        "schema": schema_name,
                        "valid": False,
                        "error": str(e)
                    })
                    
        except Exception as e:
            validation_results.append({
                "file": "bucket_error",
                "schema": "unknown",
                "valid": False,
                "error": f"Failed to access bucket: {str(e)}"
            })
            
        return validation_results

