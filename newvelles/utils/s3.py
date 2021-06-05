import boto3


def upload_to_s3(bucket_name, file_name, string_byte):
    s3_resource = boto3.resource('s3')
    s3_object = s3_resource.Object(bucket_name, file_name)
    s3_object.put(Body=string_byte)
    s3_object.Acl().put(ACL='public-read')
