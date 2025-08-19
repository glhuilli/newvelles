#!/bin/bash

# Create IAM role specifically for QA Lambda function
# This role will have access to QA S3 buckets only

set -e

ROLE_NAME="RunNewvelles-qa-execution-role"
POLICY_NAME="RunNewvelles-qa-s3-policy"

echo "🔧 Creating IAM role for QA Lambda function..."

# 1. Create trust policy (allows Lambda to assume this role)
cat > /tmp/trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# 2. Create the IAM role
echo "Creating IAM role: $ROLE_NAME"
aws iam create-role \
  --role-name $ROLE_NAME \
  --assume-role-policy-document file:///tmp/trust-policy.json \
  --description "Execution role for RunNewvelles QA Lambda function"

# 3. Attach basic Lambda execution policy (for CloudWatch logs)
echo "Attaching basic execution policy..."
aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# 4. Create custom S3 policy for QA buckets only
cat > /tmp/s3-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::newvelles-qa-bucket/*",
        "arn:aws:s3:::public-newvelles-qa-bucket/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::newvelles-qa-bucket",
        "arn:aws:s3:::public-newvelles-qa-bucket"
      ]
    }
  ]
}
EOF

# 5. Create and attach the S3 policy
echo "Creating S3 policy for QA buckets..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws iam create-policy \
  --policy-name $POLICY_NAME \
  --policy-document file:///tmp/s3-policy.json \
  --description "S3 access policy for RunNewvelles QA buckets"

echo "Attaching S3 policy to role..."
aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/$POLICY_NAME

# 6. Wait for role to be ready
echo "Waiting for IAM role to be ready..."
sleep 10

# 7. Output the role ARN
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/$ROLE_NAME"
echo ""
echo "✅ IAM role created successfully!"
echo "Role ARN: $ROLE_ARN"
echo ""
echo "🚀 Now you can create the QA Lambda function with:"
echo "aws lambda create-function \\"
echo "  --function-name RunNewvelles-qa \\"
echo "  --package-type Image \\"
echo "  --code ImageUri=\$AWS_ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/newvelles-docker-lambda:v2-py312-20250817-181418 \\"
echo "  --role $ROLE_ARN \\"
echo "  --timeout 900 \\"
echo "  --memory-size 512 \\"
echo "  --environment Variables='{\"AWS_S3_BUCKET\":\"newvelles-qa-bucket\",\"AWS_S3_PUBLIC_BUCKET\":\"public-newvelles-qa-bucket\"}'"

# Cleanup temp files
rm -f /tmp/trust-policy.json /tmp/s3-policy.json

echo ""
echo "🛡️ Security Note: This role only has access to QA buckets, not production!"
