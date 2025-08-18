"""Monitoring and performance tests for S3 schema validation."""

import json
import os
import time
import warnings
import pytest
import boto3
from moto import mock_aws
from unittest.mock import patch
from typing import Dict, Any, List

# Suppress deprecation warnings from botocore/AWS SDK (not controllable by us)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="botocore")

from test.test_schema_validation_utils import SchemaValidationUtils
from newvelles.feed.log import log_s3
from newvelles.models.grouping import build_visualization


class TestS3SchemaMonitoring:
    """Tests for monitoring S3 schema validation in production-like scenarios."""
    
    @pytest.fixture
    def s3_monitoring_setup(self):
        """Setup S3 monitoring environment."""
        with mock_aws():
            s3_client = boto3.client("s3", region_name="us-west-2")
            bucket_name = "monitoring-newvelles-bucket"
            public_bucket_name = "monitoring-public-newvelles-bucket"
            
            # Create buckets
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
    
    def test_continuous_upload_validation(self, s3_monitoring_setup):
        """Test multiple consecutive uploads and validate all conform to schema."""
        s3_client = s3_monitoring_setup["client"]
        bucket_name = s3_monitoring_setup["bucket"]
        public_bucket_name = s3_monitoring_setup["public_bucket"]
        
        # Load schemas
        news_schema = SchemaValidationUtils.load_schema("latest_news")
        metadata_schema = SchemaValidationUtils.load_schema("latest_news_metadata")
        
        # Simulate multiple uploads over time
        upload_results = []
        
        with patch('newvelles.feed.log._S3_BUCKET', bucket_name), \
             patch('newvelles.feed.log._S3_PUBLIC_BUCKET', public_bucket_name):
            
            for i in range(5):  # 5 consecutive uploads
                # Generate different data for each upload
                news_data = SchemaValidationUtils.create_nested_news_structure(
                    [f"Category_{i}_{j}" for j in range(3)],
                    [f"SubCat_{k}" for k in range(2)],
                    articles_per_subgroup=2
                )
                
                                # Convert to NewsEntry format for processing (flatten for build_visualization)
                from newvelles.feed import NewsEntry
                processed_data = {}
                for group, group_data in news_data.items():
                    for subgroup, subgroup_data in group_data.items():
                        for article_title, article_data in subgroup_data.items():
                            processed_data[article_title] = NewsEntry(
                                title=article_data["title"],
                                link=article_data["link"],
                                published=article_data["timestamp"],
                                title_detail_base=article_data["source"]
                            )

                # Build visualization and upload
                visualization_data, _ = build_visualization(
                    processed_data, cluster_limit=5
                )
                log_s3(visualization_data)
                
                # Validate uploaded files
                objects = s3_client.list_objects_v2(Bucket=public_bucket_name)
                assert 'Contents' in objects
                
                # Check both files
                for obj in objects['Contents']:
                    key = obj['Key']
                    if key.endswith('.json'):
                        file_obj = s3_client.get_object(Bucket=public_bucket_name, Key=key)
                        data = json.loads(file_obj['Body'].read().decode('utf-8'))
                        
                        if 'metadata' in key:
                            error = SchemaValidationUtils.validate_data_against_schema(
                                data, metadata_schema
                            )
                        else:
                            error = SchemaValidationUtils.validate_data_against_schema(
                                data, news_schema
                            )
                        
                        upload_results.append({
                            "upload_round": i,
                            "file": key,
                            "valid": error is None,
                            "error": error
                        })
                
                # Clear bucket for next iteration (except keep latest files)
                if i < 4:  # Don't clear on last iteration
                    time.sleep(0.1)  # Small delay between uploads
        
        # Verify all uploads were valid
        failed_uploads = [r for r in upload_results if not r["valid"]]
        assert len(failed_uploads) == 0, f"Failed uploads: {failed_uploads}"
        
        # Verify we got results for all uploads
        assert len(upload_results) >= 10  # At least 2 files per upload * 5 uploads
    
    def test_performance_schema_validation(self, s3_monitoring_setup):
        """Test schema validation performance with large datasets.
        
        Note: This test includes ML processing (TensorFlow Universal Sentence Encoder)
        which can take 60-300 seconds depending on the environment.
        Timeout can be customized via environment variables:
        - NEWVELLES_TEST_UPLOAD_TIMEOUT (default: 300s)
        - NEWVELLES_TEST_VALIDATION_TIMEOUT (default: 30s)
        """
        s3_client = s3_monitoring_setup["client"]
        bucket_name = s3_monitoring_setup["bucket"]
        public_bucket_name = s3_monitoring_setup["public_bucket"]
        
        # Create a very large dataset
        large_news_data = SchemaValidationUtils.create_nested_news_structure(
            [f"Category_{i}" for i in range(50)],  # 50 categories
            [f"SubCategory_{j}" for j in range(4)],  # 4 subcategories each
            articles_per_subgroup=5  # 5 articles each
        )
        # Total: 50 * 4 * 5 = 1000 articles
        
        # Convert to NewsEntry format (flatten for build_visualization)
        from newvelles.feed import NewsEntry
        processed_data = {}
        for group, group_data in large_news_data.items():
            for subgroup, subgroup_data in group_data.items():
                for article_title, article_data in subgroup_data.items():
                    processed_data[article_title] = NewsEntry(
                        title=article_data["title"],
                        link=article_data["link"],
                        published=article_data["timestamp"],
                        title_detail_base=article_data["source"]
                    )
        
        # Load schemas
        news_schema = SchemaValidationUtils.load_schema("latest_news")
        metadata_schema = SchemaValidationUtils.load_schema("latest_news_metadata")
        
        with patch('newvelles.feed.log._S3_BUCKET', bucket_name), \
             patch('newvelles.feed.log._S3_PUBLIC_BUCKET', public_bucket_name):
            
            # Time the upload and validation process
            start_time = time.time()
            
            # Build visualization and upload
            visualization_data, _ = build_visualization(
                processed_data, cluster_limit=20
            )
            log_s3(visualization_data)
            
            upload_time = time.time() - start_time
            
            # Time the validation process
            validation_start = time.time()
            
            objects = s3_client.list_objects_v2(Bucket=public_bucket_name)
            assert 'Contents' in objects
            
            validation_results = []
            for obj in objects['Contents']:
                key = obj['Key']
                if key.endswith('.json'):
                    file_obj = s3_client.get_object(Bucket=public_bucket_name, Key=key)
                    data = json.loads(file_obj['Body'].read().decode('utf-8'))
                    
                    if 'metadata' in key:
                        error = SchemaValidationUtils.validate_data_against_schema(
                            data, metadata_schema
                        )
                    else:
                        error = SchemaValidationUtils.validate_data_against_schema(
                            data, news_schema
                        )
                    
                    validation_results.append({
                        "file": key,
                        "valid": error is None,
                        "error": error
                    })
            
            validation_time = time.time() - validation_start
            
            # Performance assertions (adjusted for ML processing time)
            # Note: ML processing with TensorFlow can be slow, especially on first run
            max_upload_time = float(os.environ.get('NEWVELLES_TEST_UPLOAD_TIMEOUT', '300'))  # 5 minutes default
            max_validation_time = float(os.environ.get('NEWVELLES_TEST_VALIDATION_TIMEOUT', '30'))  # 30 seconds default
            
            print(f"\n📊 Performance Metrics:")
            print(f"   • Upload/ML processing time: {upload_time:.2f}s (limit: {max_upload_time}s)")
            print(f"   • Schema validation time: {validation_time:.2f}s (limit: {max_validation_time}s)")
            
            assert upload_time < max_upload_time, f"Upload took too long: {upload_time:.2f}s > {max_upload_time}s"
            assert validation_time < max_validation_time, f"Validation took too long: {validation_time:.2f}s > {max_validation_time}s"
            
            # Validation correctness assertions
            assert len(validation_results) >= 2  # At least news and metadata files
            failed_validations = [r for r in validation_results if not r["valid"]]
            assert len(failed_validations) == 0, f"Failed validations: {failed_validations}"
    
    def test_schema_validation_error_detection(self, s3_monitoring_setup):
        """Test that schema validation properly detects and reports errors."""
        s3_client = s3_monitoring_setup["client"]
        public_bucket_name = s3_monitoring_setup["public_bucket"]
        
        # Load schemas
        news_schema = SchemaValidationUtils.load_schema("latest_news")
        metadata_schema = SchemaValidationUtils.load_schema("latest_news_metadata")
        
        # Upload invalid data directly to S3
        invalid_news = {
            "group": {
                "subgroup": {
                    "article": {
                        "title": 123,  # Should be string
                        "link": "not-a-url",  # Invalid URL
                        # Missing required fields
                    }
                }
            }
        }
        
        invalid_metadata = {
            "datetime": "not-a-datetime",
            "version": "not.a.valid.version.format.too.long"
        }
        
        # Upload invalid files
        s3_client.put_object(
            Bucket=public_bucket_name,
            Key="invalid_news.json",
            Body=json.dumps(invalid_news).encode('utf-8')
        )
        
        s3_client.put_object(
            Bucket=public_bucket_name,
            Key="invalid_metadata.json",
            Body=json.dumps(invalid_metadata).encode('utf-8')
        )
        
        # Validate and ensure errors are detected
        objects = s3_client.list_objects_v2(Bucket=public_bucket_name)
        validation_errors = []
        
        for obj in objects['Contents']:
            key = obj['Key']
            file_obj = s3_client.get_object(Bucket=public_bucket_name, Key=key)
            data = json.loads(file_obj['Body'].read().decode('utf-8'))
            
            if 'metadata' in key:
                error = SchemaValidationUtils.validate_data_against_schema(
                    data, metadata_schema
                )
            else:
                error = SchemaValidationUtils.validate_data_against_schema(
                    data, news_schema
                )
            
            if error:
                validation_errors.append({
                    "file": key,
                    "error": error
                })
        
        # Should have detected 2 errors
        assert len(validation_errors) == 2
        assert any("invalid_news.json" in err["file"] for err in validation_errors)
        assert any("invalid_metadata.json" in err["file"] for err in validation_errors)
    
    def test_schema_validation_monitoring_report(self, s3_monitoring_setup):
        """Test generation of a monitoring report for schema validation."""
        s3_client = s3_monitoring_setup["client"]
        bucket_name = s3_monitoring_setup["bucket"]
        public_bucket_name = s3_monitoring_setup["public_bucket"]
        
        # Upload a mix of valid and invalid files for monitoring
        valid_news = SchemaValidationUtils.create_nested_news_structure(
            ["Politics"], ["Breaking"], 1
        )
        valid_metadata = SchemaValidationUtils.generate_valid_metadata()
        
        invalid_news = {"invalid": "structure"}
        invalid_metadata = {"bad": "metadata"}
        
        # Upload files
        test_files = [
            ("valid_news.json", valid_news),
            ("valid_metadata.json", valid_metadata),
            ("invalid_news.json", invalid_news),
            ("invalid_metadata.json", invalid_metadata)
        ]
        
        for filename, data in test_files:
            s3_client.put_object(
                Bucket=public_bucket_name,
                Key=filename,
                Body=json.dumps(data).encode('utf-8')
            )
        
        # Generate monitoring report
        report = self._generate_validation_report(s3_client, public_bucket_name)
        
        # Verify report structure
        assert "total_files" in report
        assert "valid_files" in report
        assert "invalid_files" in report
        assert "validation_results" in report
        assert "summary" in report
        
        # Verify report content
        assert report["total_files"] == 4
        assert report["valid_files"] == 2
        assert report["invalid_files"] == 2
        assert len(report["validation_results"]) == 4
        
        # Verify each result has required fields
        for result in report["validation_results"]:
            assert "file" in result
            assert "schema_type" in result
            assert "valid" in result
            if not result["valid"]:
                assert "error" in result
    
    def _generate_validation_report(self, s3_client, bucket_name: str) -> Dict[str, Any]:
        """Generate a validation report for all JSON files in the bucket."""
        news_schema = SchemaValidationUtils.load_schema("latest_news")
        metadata_schema = SchemaValidationUtils.load_schema("latest_news_metadata")
        
        validation_results = []
        valid_count = 0
        invalid_count = 0
        
        try:
            objects = s3_client.list_objects_v2(Bucket=bucket_name)
            if 'Contents' not in objects:
                return {
                    "total_files": 0,
                    "valid_files": 0,
                    "invalid_files": 0,
                    "validation_results": [],
                    "summary": "No files found in bucket"
                }
            
            for obj in objects['Contents']:
                key = obj['Key']
                if not key.endswith('.json'):
                    continue
                
                try:
                    file_obj = s3_client.get_object(Bucket=bucket_name, Key=key)
                    data = json.loads(file_obj['Body'].read().decode('utf-8'))
                    
                    # Determine schema based on filename
                    if 'metadata' in key.lower():
                        schema = metadata_schema
                        schema_type = "metadata"
                    else:
                        schema = news_schema
                        schema_type = "news"
                    
                    # Validate
                    error = SchemaValidationUtils.validate_data_against_schema(data, schema)
                    
                    result = {
                        "file": key,
                        "schema_type": schema_type,
                        "valid": error is None
                    }
                    
                    if error:
                        result["error"] = error
                        invalid_count += 1
                    else:
                        valid_count += 1
                    
                    validation_results.append(result)
                
                except Exception as e:
                    validation_results.append({
                        "file": key,
                        "schema_type": "unknown",
                        "valid": False,
                        "error": f"Failed to process file: {str(e)}"
                    })
                    invalid_count += 1
        
        except Exception as e:
            return {
                "total_files": 0,
                "valid_files": 0,
                "invalid_files": 0,
                "validation_results": [],
                "summary": f"Failed to access bucket: {str(e)}"
            }
        
        total_files = valid_count + invalid_count
        summary = f"Processed {total_files} files: {valid_count} valid, {invalid_count} invalid"
        
        return {
            "total_files": total_files,
            "valid_files": valid_count,
            "invalid_files": invalid_count,
            "validation_results": validation_results,
            "summary": summary
        }


class TestS3SchemaAlerts:
    """Tests for alerting mechanisms when schema validation fails."""
    
    def test_schema_validation_alert_trigger(self):
        """Test that schema validation failures can trigger alerts."""
        # This test would integrate with actual alerting systems in production
        # For now, we'll test the detection mechanism
        
        invalid_data = {"completely": "invalid", "structure": True}
        schema = SchemaValidationUtils.load_schema("latest_news")
        
        error = SchemaValidationUtils.validate_data_against_schema(invalid_data, schema)
        
        # In production, this would trigger an alert
        assert error is not None
        assert isinstance(error, str)
        assert len(error) > 0
        
        # Simulate alert conditions
        alert_conditions = [
            "required" in error.lower(),
            "additional properties" in error.lower(),
            "not of type" in error.lower()
        ]
        
        # At least one alert condition should be met
        assert any(alert_conditions), f"No alert conditions met for error: {error}"
    
    def test_schema_validation_metrics_collection(self):
        """Test collection of metrics for schema validation monitoring."""
        # Simulate multiple validation attempts
        test_cases = [
            (SchemaValidationUtils.generate_valid_metadata(), "latest_news_metadata", True),
            ({"invalid": "metadata"}, "latest_news_metadata", False),
            (SchemaValidationUtils.create_nested_news_structure(["Test"], ["Test"], 1), "latest_news", True),
            ({"invalid": "news"}, "latest_news", False)
        ]
        
        metrics = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "error_types": {}
        }
        
        for data, schema_name, expected_valid in test_cases:
            schema = SchemaValidationUtils.load_schema(schema_name)
            error = SchemaValidationUtils.validate_data_against_schema(data, schema)
            
            metrics["total_validations"] += 1
            
            if error is None:
                metrics["successful_validations"] += 1
                assert expected_valid, "Expected validation to fail but it succeeded"
            else:
                metrics["failed_validations"] += 1
                assert not expected_valid, "Expected validation to succeed but it failed"
                
                # Categorize error type
                if "required" in error.lower():
                    error_type = "missing_required_field"
                elif "additional properties" in error.lower():
                    error_type = "additional_properties"
                elif "not of type" in error.lower():
                    error_type = "wrong_type"
                else:
                    error_type = "other"
                
                metrics["error_types"][error_type] = metrics["error_types"].get(error_type, 0) + 1
        
        # Verify metrics collection
        assert metrics["total_validations"] == 4
        assert metrics["successful_validations"] == 2
        assert metrics["failed_validations"] == 2
        assert len(metrics["error_types"]) > 0
        
        # In production, these metrics would be sent to monitoring systems
        # (CloudWatch, Datadog, etc.)
        success_rate = metrics["successful_validations"] / metrics["total_validations"]
        assert 0 <= success_rate <= 1
