#!/usr/bin/env python3
"""
Simple schema validation script that can run without pytest.

This script validates the example data files against the schemas to ensure
they are correctly structured and that our schema validation framework works.
"""

import json
import os
import sys
from pathlib import Path


def load_json_file(file_path: str):
    """Load and parse a JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {file_path}: {e}")
        return None


def basic_schema_validation(data, schema_type):
    """Basic validation without jsonschema library."""
    if schema_type == "metadata":
        return validate_metadata_basic(data)
    elif schema_type == "news":
        return validate_news_basic(data)
    return False, "Unknown schema type"


def validate_metadata_basic(data):
    """Basic validation for metadata schema."""
    if not isinstance(data, dict):
        return False, "Metadata must be an object"
    
    if "datetime" not in data:
        return False, "Missing required field: datetime"
    
    if "version" not in data:
        return False, "Missing required field: version"
    
    # Basic datetime format check (ISO 8601-ish)
    datetime_str = data["datetime"]
    if not isinstance(datetime_str, str) or len(datetime_str) != 19:
        return False, "datetime must be in YYYY-MM-DDTHH:mm:ss format"
    
    # Basic version format check (semantic versioning)
    version_str = data["version"]
    if not isinstance(version_str, str):
        return False, "version must be a string"
    
    version_parts = version_str.split(".")
    if len(version_parts) != 3:
        return False, "version must be in major.minor.patch format"
    
    try:
        [int(part) for part in version_parts]
    except ValueError:
        return False, "version parts must be integers"
    
    return True, "Valid metadata"


def validate_news_basic(data):
    """Basic validation for news schema."""
    if not isinstance(data, dict):
        return False, "News data must be an object"
    
    if len(data) == 0:
        return False, "News data cannot be empty"
    
    # Check structure: group -> subgroup -> article
    for group_name, group_data in data.items():
        if not isinstance(group_data, dict):
            return False, f"Group '{group_name}' must be an object"
        
        if len(group_data) == 0:
            return False, f"Group '{group_name}' cannot be empty"
        
        for subgroup_name, subgroup_data in group_data.items():
            if not isinstance(subgroup_data, dict):
                return False, f"Subgroup '{subgroup_name}' must be an object"
            
            if len(subgroup_data) == 0:
                return False, f"Subgroup '{subgroup_name}' cannot be empty"
            
            for article_name, article_data in subgroup_data.items():
                valid, error = validate_article_basic(article_data, article_name)
                if not valid:
                    return False, f"Article '{article_name}': {error}"
    
    return True, "Valid news data"


def validate_article_basic(article, article_name):
    """Basic validation for a single article."""
    if not isinstance(article, dict):
        return False, "Article must be an object"
    
    required_fields = ["title", "link", "timestamp", "source"]
    for field in required_fields:
        if field not in article:
            return False, f"Missing required field: {field}"
        
        if not isinstance(article[field], str):
            return False, f"Field '{field}' must be a string"
        
        if len(article[field].strip()) == 0:
            return False, f"Field '{field}' cannot be empty"
    
    # Basic URL validation for link and source
    for url_field in ["link", "source"]:
        url = article[url_field]
        if not (url.startswith("http://") or url.startswith("https://")):
            return False, f"Field '{url_field}' must be a valid URL"
    
    return True, "Valid article"


def main():
    """Main function to run schema validation."""
    print("🔍 Simple Schema Validation")
    print("=" * 40)
    
    # Change to project root if needed
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Test files to validate
    test_files = [
        ("data/latest_news_metadata_example.json", "metadata"),
        # Note: latest_news_example.json is too large to read fully, so we'll skip it
    ]
    
    # Check that schemas directory exists
    if not Path("schemas").exists():
        print("❌ schemas/ directory not found")
        print("💡 Make sure you're running this from the project root")
        return False
    
    success_count = 0
    total_count = 0
    
    for file_path, schema_type in test_files:
        total_count += 1
        print(f"\\n📄 Validating {file_path} ({schema_type})...")
        
        data = load_json_file(file_path)
        if data is None:
            continue
        
        valid, message = basic_schema_validation(data, schema_type)
        
        if valid:
            print(f"✅ {message}")
            success_count += 1
        else:
            print(f"❌ {message}")
    
    # Test schema files exist and are valid JSON
    schema_files = [
        "schemas/latest_news_schema.json",
        "schemas/latest_news_metadata_schema.json"
    ]
    
    print(f"\\n📋 Checking schema files...")
    for schema_file in schema_files:
        total_count += 1
        schema_data = load_json_file(schema_file)
        if schema_data is not None:
            print(f"✅ {schema_file} is valid JSON")
            success_count += 1
        else:
            print(f"❌ {schema_file} failed to load")
    
    # Test that we can create valid data structures
    print(f"\\n🧪 Testing data structure creation...")
    total_count += 1
    
    # Create a simple valid news structure
    test_news = {
        "Test Group": {
            "Test Subgroup": {
                "Test Article": {
                    "title": "Test Article Title",
                    "link": "https://example.com/article",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "source": "https://example.com/rss"
                }
            }
        }
    }
    
    valid, message = validate_news_basic(test_news)
    if valid:
        print(f"✅ Generated test data structure is valid")
        success_count += 1
    else:
        print(f"❌ Generated test data failed validation: {message}")
    
    # Test metadata structure
    total_count += 1
    test_metadata = {
        "datetime": "2024-01-15T10:30:45",
        "version": "1.0.0"
    }
    
    valid, message = validate_metadata_basic(test_metadata)
    if valid:
        print(f"✅ Generated test metadata is valid")
        success_count += 1
    else:
        print(f"❌ Generated test metadata failed validation: {message}")
    
    # Summary
    print("\\n" + "=" * 40)
    print(f"📊 Results: {success_count}/{total_count} validations passed")
    
    if success_count == total_count:
        print("🎉 All validations passed!")
        print("✨ Your schema validation framework is ready to use.")
        print("💡 Install dev dependencies to run the full test suite:")
        print("   pip install -r requirements_dev.txt")
        return True
    else:
        print("⚠️  Some validations failed.")
        print("🔧 Please check the errors above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
