#!/usr/bin/env python3
"""
Simple script to check S3 bucket contents and investigate the missing metadata file.
"""

import boto3
import json
from botocore.exceptions import ClientError, NoCredentialsError
import os


def list_bucket_contents(bucket_name, prefix=""):
    """List all objects in an S3 bucket."""
    try:
        s3_client = boto3.client('s3')
        
        print(f"\n📋 Listing contents of bucket: {bucket_name}")
        print("-" * 50)
        
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix
        )
        
        if 'Contents' in response:
            objects = response['Contents']
            print(f"Found {len(objects)} objects:")
            
            for obj in objects:
                key = obj['Key']
                size = obj['Size']
                modified = obj['LastModified']
                print(f"  📄 {key}")
                print(f"     Size: {size} bytes")
                print(f"     Modified: {modified}")
                
                # If it's a JSON file, show a preview
                if key.endswith('.json'):
                    try:
                        obj_response = s3_client.get_object(Bucket=bucket_name, Key=key)
                        content = obj_response['Body'].read().decode('utf-8')
                        data = json.loads(content)
                        
                        if key.endswith('metadata.json'):
                            print(f"     📊 Metadata content: {data}")
                        else:
                            # For news data, just show the structure
                            if isinstance(data, dict):
                                print(f"     📊 Structure: {len(data)} top-level groups")
                                if data:
                                    first_key = list(data.keys())[0]
                                    first_group = data[first_key]
                                    if isinstance(first_group, dict):
                                        print(f"     📊 Sample group '{first_key}': {len(first_group)} items")
                    except Exception as e:
                        print(f"     ⚠️  Could not preview content: {e}")
                
                print()
        else:
            print("  📭 Bucket is empty or no objects found")
            
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchBucket':
            print(f"  ❌ Bucket '{bucket_name}' does not exist")
        elif error_code == 'AccessDenied':
            print(f"  ❌ Access denied to bucket '{bucket_name}'")
        else:
            print(f"  ❌ Error accessing bucket '{bucket_name}': {e}")
    except NoCredentialsError:
        print(f"  ❌ No AWS credentials found")
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")


def main():
    """Main function to check both buckets."""
    print("🔍 S3 Bucket Contents Checker")
    print("=" * 40)
    
    # Check environment variables for bucket names
    private_bucket = os.getenv('AWS_S3_BUCKET', 'newvelles-test-bucket')
    public_bucket = os.getenv('AWS_S3_PUBLIC_BUCKET', 'public-newvelles-test-bucket')
    
    print(f"Private bucket: {private_bucket}")
    print(f"Public bucket: {public_bucket}")
    
    # List contents of both buckets
    list_bucket_contents(private_bucket)
    list_bucket_contents(public_bucket)
    
    # Specifically look for metadata files
    print("\n🔍 Specifically searching for metadata files...")
    print("-" * 50)
    
    metadata_variations = [
        "latest_news_metadata.json",
        "latest_news_metadata",
        "metadata.json",
        "newvelles_metadata.json"
    ]
    
    for bucket_name in [private_bucket, public_bucket]:
        print(f"\nSearching in {bucket_name}:")
        try:
            s3_client = boto3.client('s3')
            
            for metadata_name in metadata_variations:
                try:
                    response = s3_client.head_object(Bucket=bucket_name, Key=metadata_name)
                    print(f"  ✅ Found: {metadata_name}")
                    print(f"     Size: {response['ContentLength']} bytes")
                    print(f"     Modified: {response['LastModified']}")
                except ClientError as e:
                    if e.response['Error']['Code'] == 'NoSuchKey':
                        print(f"  ❌ Not found: {metadata_name}")
                    else:
                        print(f"  ⚠️  Error checking {metadata_name}: {e}")
                        
        except Exception as e:
            print(f"  ❌ Error accessing {bucket_name}: {e}")


if __name__ == "__main__":
    main()
