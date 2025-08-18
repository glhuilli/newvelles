"""Utility functions and comprehensive tests for schema validation."""

import json
import os
from typing import Dict, Any, List, Optional
import jsonschema
import pytest


class SchemaValidationUtils:
    """Utility class for schema validation operations."""
    
    @staticmethod
    def load_schema(schema_name: str) -> Dict[str, Any]:
        """Load a JSON schema from the schemas directory."""
        schema_path = os.path.join("schemas", f"{schema_name}_schema.json")
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        with open(schema_path, "r") as f:
            return json.load(f)
    
    @staticmethod
    def validate_data_against_schema(data: Dict[str, Any], 
                                   schema: Dict[str, Any]) -> Optional[str]:
        """
        Validate data against schema and return error message if invalid.
        
        Args:
            data: The data to validate
            schema: The JSON schema to validate against
            
        Returns:
            None if valid, error message string if invalid
        """
        try:
            jsonschema.validate(data, schema)
            return None
        except jsonschema.ValidationError as e:
            return str(e)
    
    @staticmethod
    def generate_valid_news_entry(title: str = "Test News", 
                                link: str = "https://example.com/news",
                                timestamp: str = "2024-01-15T10:00:00Z",
                                source: str = "https://example.com/rss") -> Dict[str, Any]:
        """Generate a valid news entry for testing."""
        return {
            "title": title,
            "link": link,
            "timestamp": timestamp,
            "source": source
        }
    
    @staticmethod
    def generate_valid_metadata(datetime_str: str = "2024-01-15T10:30:45",
                              version: str = "1.0.0") -> Dict[str, Any]:
        """Generate valid metadata for testing."""
        return {
            "datetime": datetime_str,
            "version": version
        }
    
    @staticmethod
    def create_nested_news_structure(groups: List[str], 
                                   subgroups: List[str],
                                   articles_per_subgroup: int = 1) -> Dict[str, Any]:
        """Create a nested news structure for testing."""
        news_data = {}
        
        for group in groups:
            news_data[group] = {}
            for subgroup in subgroups:
                news_data[group][subgroup] = {}
                for i in range(articles_per_subgroup):
                    article_title = f"Article {i+1} in {group} - {subgroup}"
                    news_data[group][subgroup][article_title] = SchemaValidationUtils.generate_valid_news_entry(
                        title=article_title,
                        link=f"https://example.com/article-{group}-{subgroup}-{i}",
                        source=f"https://example.com/rss/{group.lower()}"
                    )
        
        return news_data


class TestSchemaValidationUtils:
    """Tests for the schema validation utility functions."""
    
    def test_load_schema_success(self):
        """Test successful schema loading."""
        schema = SchemaValidationUtils.load_schema("latest_news")
        assert isinstance(schema, dict)
        assert "$schema" in schema
        assert "type" in schema
        
        metadata_schema = SchemaValidationUtils.load_schema("latest_news_metadata")
        assert isinstance(metadata_schema, dict)
        assert "$schema" in metadata_schema
    
    def test_load_schema_file_not_found(self):
        """Test schema loading with non-existent file."""
        with pytest.raises(FileNotFoundError):
            SchemaValidationUtils.load_schema("nonexistent_schema")
    
    def test_validate_data_against_schema_success(self):
        """Test successful data validation."""
        schema = SchemaValidationUtils.load_schema("latest_news_metadata")
        valid_data = SchemaValidationUtils.generate_valid_metadata()
        
        error = SchemaValidationUtils.validate_data_against_schema(valid_data, schema)
        assert error is None
    
    def test_validate_data_against_schema_failure(self):
        """Test data validation failure."""
        schema = SchemaValidationUtils.load_schema("latest_news_metadata")
        invalid_data = {"invalid": "data"}
        
        error = SchemaValidationUtils.validate_data_against_schema(invalid_data, schema)
        assert error is not None
        assert isinstance(error, str)
    
    def test_generate_valid_news_entry(self):
        """Test generation of valid news entries."""
        entry = SchemaValidationUtils.generate_valid_news_entry()
        
        assert "title" in entry
        assert "link" in entry
        assert "timestamp" in entry
        assert "source" in entry
        
        # Test with custom values
        custom_entry = SchemaValidationUtils.generate_valid_news_entry(
            title="Custom Title",
            link="https://custom.com",
            timestamp="2025-01-01T00:00:00Z",
            source="https://custom.com/rss"
        )
        
        assert custom_entry["title"] == "Custom Title"
        assert custom_entry["link"] == "https://custom.com"
    
    def test_generate_valid_metadata(self):
        """Test generation of valid metadata."""
        metadata = SchemaValidationUtils.generate_valid_metadata()
        
        assert "datetime" in metadata
        assert "version" in metadata
        
        # Validate against schema
        schema = SchemaValidationUtils.load_schema("latest_news_metadata")
        error = SchemaValidationUtils.validate_data_against_schema(metadata, schema)
        assert error is None
    
    def test_create_nested_news_structure(self):
        """Test creation of nested news structures."""
        groups = ["Politics", "Technology"]
        subgroups = ["Breaking", "Analysis"]
        
        news_data = SchemaValidationUtils.create_nested_news_structure(
            groups, subgroups, articles_per_subgroup=2
        )
        
        assert len(news_data) == 2
        assert "Politics" in news_data
        assert "Technology" in news_data
        
        for group in groups:
            assert len(news_data[group]) == 2
            for subgroup in subgroups:
                assert subgroup in news_data[group]
                assert len(news_data[group][subgroup]) == 2
        
        # Validate against schema
        schema = SchemaValidationUtils.load_schema("latest_news")
        error = SchemaValidationUtils.validate_data_against_schema(news_data, schema)
        assert error is None


class TestSchemaValidationStressTests:
    """Stress tests for schema validation with various data scenarios."""
    
    def test_large_dataset_validation(self):
        """Test schema validation with large datasets."""
        # Create a large dataset
        groups = [f"Group_{i}" for i in range(20)]
        subgroups = [f"SubGroup_{i}" for i in range(5)]
        
        large_data = SchemaValidationUtils.create_nested_news_structure(
            groups, subgroups, articles_per_subgroup=10
        )
        
        # Should have 20 * 5 * 10 = 1000 articles
        total_articles = sum(
            len(subgroup_data) 
            for group_data in large_data.values() 
            for subgroup_data in group_data.values()
        )
        assert total_articles == 1000
        
        # Validate against schema
        schema = SchemaValidationUtils.load_schema("latest_news")
        error = SchemaValidationUtils.validate_data_against_schema(large_data, schema)
        assert error is None
    
    def test_edge_case_data_validation(self):
        """Test schema validation with edge case data."""
        schema = SchemaValidationUtils.load_schema("latest_news")
        
        # Test with minimal valid structure
        minimal_data = {
            "a": {
                "b": {
                    "c": SchemaValidationUtils.generate_valid_news_entry(
                        title="a",  # Minimal title
                        link="https://a.com",
                        timestamp="Mon, 01 Jan 2024 00:00:00 +0000",
                        source="https://a.com/rss"
                    )
                }
            }
        }
        
        error = SchemaValidationUtils.validate_data_against_schema(minimal_data, schema)
        assert error is None
        
        # Test with very long but valid data
        long_title = "Very " + "long " * 100 + "title"
        long_url = "https://example.com/" + "very/" * 50 + "long/path"
        
        long_data = {
            "Group with very long name": {
                "Subgroup with long name": {
                    long_title: SchemaValidationUtils.generate_valid_news_entry(
                        title=long_title,
                        link=long_url,
                        source=long_url
                    )
                }
            }
        }
        
        error = SchemaValidationUtils.validate_data_against_schema(long_data, schema)
        assert error is None
    
    def test_various_timestamp_formats(self):
        """Test schema validation with various RSS timestamp formats."""
        schema = SchemaValidationUtils.load_schema("latest_news")
        
        # Common RSS timestamp formats
        timestamp_formats = [
            "Mon, 25 Nov 2024 08:03:10 +0000",  # RFC 2822
            "2024-01-15T14:30:00Z",              # ISO 8601 with Z
            "Sat, 16 Aug 2025 18:51:12 +0000",   # Standard RSS format
            "Fri, 15 Aug 2025 19:51:03 GMT",     # GMT timezone
            "Thu, 14 Aug 2025 20:49:01 EST",     # EST timezone
            "Wed, 13 Aug 2025 17:45:00 PST"      # PST timezone
        ]
        
        for i, timestamp in enumerate(timestamp_formats):
            test_data = {
                f"Group_{i}": {
                    "SubGroup": {
                        f"Article_{i}": SchemaValidationUtils.generate_valid_news_entry(
                            title=f"Test Article {i}",
                            timestamp=timestamp
                        )
                    }
                }
            }
            
            error = SchemaValidationUtils.validate_data_against_schema(test_data, schema)
            assert error is None, f"Failed for timestamp format: {timestamp}"
    
    def test_metadata_version_formats(self):
        """Test metadata schema with various version formats."""
        schema = SchemaValidationUtils.load_schema("latest_news_metadata")
        
        # Valid semantic versions
        valid_versions = [
            "0.0.1",
            "1.0.0", 
            "10.25.3",
            "999.999.999"
        ]
        
        for version in valid_versions:
            metadata = SchemaValidationUtils.generate_valid_metadata(version=version)
            error = SchemaValidationUtils.validate_data_against_schema(metadata, schema)
            assert error is None, f"Failed for version: {version}"
        
        # Invalid versions should fail
        invalid_versions = [
            "1.0",           # Missing patch version
            "1.0.0.0",       # Too many parts
            "v1.0.0",        # With 'v' prefix
            "1.0.0-beta",    # With suffix
            "1.0.0a",        # With letter
        ]
        
        for version in invalid_versions:
            metadata = SchemaValidationUtils.generate_valid_metadata(version=version)
            error = SchemaValidationUtils.validate_data_against_schema(metadata, schema)
            assert error is not None, f"Should have failed for version: {version}"


class TestSchemaValidationIntegration:
    """Integration tests combining schema validation with S3 operations."""
    
    def test_end_to_end_schema_validation_workflow(self):
        """Test complete workflow from data generation to schema validation."""
        # 1. Generate test data
        news_data = SchemaValidationUtils.create_nested_news_structure(
            ["Politics", "Technology", "Sports"],
            ["Breaking", "Analysis", "Opinion"],
            articles_per_subgroup=3
        )
        
        metadata = SchemaValidationUtils.generate_valid_metadata(
            datetime_str="2024-08-16T12:00:00",
            version="1.2.3"
        )
        
        # 2. Load schemas
        news_schema = SchemaValidationUtils.load_schema("latest_news")
        metadata_schema = SchemaValidationUtils.load_schema("latest_news_metadata")
        
        # 3. Validate data
        news_error = SchemaValidationUtils.validate_data_against_schema(
            news_data, news_schema
        )
        metadata_error = SchemaValidationUtils.validate_data_against_schema(
            metadata, metadata_schema
        )
        
        # 4. Assert validation success
        assert news_error is None
        assert metadata_error is None
        
        # 5. Verify data structure integrity
        assert len(news_data) == 3  # 3 groups
        total_articles = sum(
            len(subgroup_data) 
            for group_data in news_data.values() 
            for subgroup_data in group_data.values()
        )
        assert total_articles == 27  # 3 groups * 3 subgroups * 3 articles
        
        # 6. Verify metadata content
        assert "datetime" in metadata
        assert "version" in metadata
        assert metadata["version"] == "1.2.3"
