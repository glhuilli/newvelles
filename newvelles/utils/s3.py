import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def upload_to_s3(bucket_name: str, file_name: str, string_byte, public_read: bool = False) -> None:
    """
    Upload data to S3 bucket with optional public read access.

    Args:
        bucket_name: Name of the S3 bucket
        file_name: Name of the file in S3
        string_byte: Data to upload (as bytes)
        public_read: Whether to make the object publicly readable

    Note:
        If public_read is True but ACLs are not supported by the bucket,
        the upload will still succeed but the object won't be public.
        Consider using bucket policies for public access instead of ACLs.
    """
    s3_resource = boto3.resource("s3")
    s3_object = s3_resource.Object(bucket_name, file_name)

    # Upload the object
    s3_object.put(Body=string_byte)

    # Try to set public read ACL if requested
    if public_read:
        try:
            s3_object.Acl().put(ACL="public-read")
            logger.info(f"Successfully set public-read ACL for {file_name}")
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "AccessControlListNotSupported":
                logger.warning(
                    f"Cannot set ACL for {file_name}: Bucket does not support ACLs. "
                    f"Consider using bucket policies for public access."
                )
            else:
                logger.error(f"Failed to set ACL for {file_name}: {e}")
                # Re-raise if it's not an ACL-related error
                raise

    logger.info(f"Successfully uploaded {file_name} to {bucket_name}")
