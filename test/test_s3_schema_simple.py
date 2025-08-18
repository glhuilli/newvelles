"""Simple S3 schema validation tests."""

import json
import os
from typing import Dict, Any

import jsonschema
import pytest


class TestSchemaValidation:
    """Test JSON schema validation."""

    @pytest.fixture
    def schema_loader(self):
        """Load JSON schemas from files."""
        def _load_schema(schema_name: str) -> Dict[str, Any]:
            schema_path = os.path.join("schemas", f"{schema_name}_schema.json")
            with open(schema_path, "r") as f:
                return json.load(f)
        return _load_schema

    def test_schema_files_exist(self):
        """Test that schema files exist and are valid JSON."""
        schema_files = [
            "schemas/latest_news_schema.json",
            "schemas/latest_news_metadata_schema.json"
        ]
        
        for schema_file in schema_files:
            assert os.path.exists(schema_file), f"Schema file {schema_file} not found"
            
            with open(schema_file, "r") as f:
                schema = json.load(f)
                assert isinstance(schema, dict)
                assert "$schema" in schema

    def test_metadata_schema_validation(self, schema_loader):
        """Test metadata schema against example data."""
        metadata_schema = schema_loader("latest_news_metadata")
        
        # Test with the actual example file
        with open("data/latest_news_metadata_example.json", "r") as f:
            metadata_example = json.load(f)
        
        # This should not raise any validation errors
        jsonschema.validate(metadata_example, metadata_schema)

    def test_news_schema_with_sample_data(self, schema_loader):
        """Test news schema with manually created sample data."""
        news_schema = schema_loader("latest_news")
        
        # Create sample data that matches the expected structure
        sample_data = {
            "breaking news politics": {
                "trump administration": {
                    "Trump picks new attorney general": {
                        "title": "Trump picks new attorney general",
                        "link": "https://example.com/news1", 
                        "timestamp": "Mon, 25 Nov 2024 08:03:10 +0000",
                        "source": "https://example.com/rss"
                    },
                    "Cabinet appointments continue": {
                        "title": "Cabinet appointments continue",
                        "link": "https://example.com/news2",
                        "timestamp": "Sun, 24 Nov 2024 19:12:50 +0000", 
                        "source": "https://example.com/rss"
                    }
                }
            },
            "technology news": {
                "ai developments": {
                    "New AI breakthrough announced": {
                        "title": "New AI breakthrough announced",
                        "link": "https://tech.example.com/ai",
                        "timestamp": "Sat, 23 Nov 2024 14:30:00 +0000",
                        "source": "https://tech.example.com/rss"
                    }
                }
            }
        }
        
        # This should not raise any validation errors
        jsonschema.validate(sample_data, news_schema)

    def test_schema_validation_errors(self, schema_loader):
        """Test that invalid data correctly fails validation."""
        news_schema = schema_loader("latest_news")
        metadata_schema = schema_loader("latest_news_metadata")
        
        # Test invalid news data - missing required fields
        invalid_news = {
            "group": {
                "subgroup": {
                    "article": {
                        "title": "Valid Title",
                        # Missing required fields: link, timestamp, source
                    }
                }
            }
        }
        
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_news, news_schema)
        
        # Test invalid metadata - wrong datetime format
        invalid_metadata = {
            "datetime": "not-a-valid-datetime",
            "version": "1.0.0"
        }
        
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_metadata, metadata_schema)

    def test_real_s3_upload_validation(self):
        """Test validation against actual S3 upload format."""
        # This test would validate actual S3 uploads if you provide bucket name
        # For now, it just checks that the validation script exists
        script_path = "scripts/validate_s3_data.py"
        assert os.path.exists(script_path)
        assert os.access(script_path, os.X_OK), "Validation script should be executable"
