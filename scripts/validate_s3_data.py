#!/usr/bin/env python3
"""
Utility script to validate S3 data against JSON schemas.

This script can be used to validate:
1. Local JSON files against schemas
2. S3 bucket contents against schemas
3. Example data files against schemas
"""

import argparse
import json
import os
import sys
from typing import Dict, Any

import boto3
import jsonschema
from botocore.exceptions import ClientError, NoCredentialsError


def load_schema(schema_name: str) -> Dict[str, Any]:
    """Load a JSON schema from the schemas directory."""
    schema_path = os.path.join("schemas", f"{schema_name}_schema.json")
    
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(schema_path, "r") as f:
        return json.load(f)


def validate_local_file(file_path: str, schema_name: str) -> bool:
    """Validate a local JSON file against a schema."""
    try:
        schema = load_schema(schema_name)
        
        with open(file_path, "r") as f:
            data = json.load(f)
        
        jsonschema.validate(data, schema)
        print(f"✅ {file_path} is valid according to {schema_name} schema")
        return True
        
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {file_path}: {e}")
        return False
    except jsonschema.ValidationError as e:
        print(f"❌ Schema validation failed for {file_path}:")
        print(f"   {e.message}")
        if e.absolute_path:
            print(f"   Path: {' -> '.join(str(p) for p in e.absolute_path)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error validating {file_path}: {e}")
        return False


def validate_s3_bucket(bucket_name: str, region: str = "us-west-2") -> bool:
    """Validate JSON files in an S3 bucket against schemas."""
    try:
        s3_client = boto3.client("s3", region_name=region)
        
        # List objects in bucket
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        
        if 'Contents' not in response:
            print(f"⚠️  No objects found in bucket: {bucket_name}")
            return True
        
        success = True
        for obj in response['Contents']:
            key = obj['Key']
            
            # Determine schema based on filename
            if key == "latest_news.json":
                schema_name = "latest_news"
            elif key == "latest_news_metadata.json":
                schema_name = "latest_news_metadata"
            else:
                print(f"⏭️  Skipping {key} (no matching schema)")
                continue
            
            try:
                # Download and validate
                obj_response = s3_client.get_object(Bucket=bucket_name, Key=key)
                data = json.loads(obj_response['Body'].read().decode('utf-8'))
                
                schema = load_schema(schema_name)
                jsonschema.validate(data, schema)
                print(f"✅ s3://{bucket_name}/{key} is valid according to {schema_name} schema")
                
            except jsonschema.ValidationError as e:
                print(f"❌ Schema validation failed for s3://{bucket_name}/{key}:")
                print(f"   {e.message}")
                success = False
            except Exception as e:
                print(f"❌ Error validating s3://{bucket_name}/{key}: {e}")
                success = False
        
        return success
        
    except NoCredentialsError:
        print("❌ AWS credentials not found. Please configure your credentials.")
        return False
    except ClientError as e:
        print(f"❌ AWS error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error validating S3 bucket: {e}")
        return False


def validate_examples() -> bool:
    """Validate example data files against schemas."""
    examples = [
        ("data/latest_news_metadata_example.json", "latest_news_metadata"),
        # Note: latest_news_example.json is too large to validate directly
        # but we can validate a sample in the integration tests
    ]
    
    success = True
    for file_path, schema_name in examples:
        if os.path.exists(file_path):
            if not validate_local_file(file_path, schema_name):
                success = False
        else:
            print(f"⚠️  Example file not found: {file_path}")
    
    return success


def main():
    parser = argparse.ArgumentParser(description="Validate JSON data against Newvelles schemas")
    parser.add_argument(
        "command", 
        choices=["file", "s3", "examples"],
        help="Validation target: local file, S3 bucket, or example files"
    )
    parser.add_argument(
        "--file", 
        help="Local JSON file to validate (required for 'file' command)"
    )
    parser.add_argument(
        "--schema", 
        choices=["latest_news", "latest_news_metadata"],
        help="Schema to validate against (required for 'file' command)"
    )
    parser.add_argument(
        "--bucket", 
        help="S3 bucket name to validate (required for 's3' command)"
    )
    parser.add_argument(
        "--region", 
        default="us-west-2",
        help="AWS region (default: us-west-2)"
    )
    
    args = parser.parse_args()
    
    if args.command == "file":
        if not args.file or not args.schema:
            print("❌ --file and --schema are required for 'file' command")
            sys.exit(1)
        
        success = validate_local_file(args.file, args.schema)
        
    elif args.command == "s3":
        if not args.bucket:
            print("❌ --bucket is required for 's3' command")
            sys.exit(1)
        
        success = validate_s3_bucket(args.bucket, args.region)
        
    elif args.command == "examples":
        success = validate_examples()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
