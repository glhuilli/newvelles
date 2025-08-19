#!/bin/bash
# QA Environment Deployment Script
# Builds and deploys Python 3.12 Docker image to QA Lambda function

set -e

# Configuration - requires environment variable
AWS_REGION="us-west-2"
FUNCTION_NAME="RunNewvelles-qa"

# Validate AWS_ACCOUNT_ID is set
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo "❌ Error: AWS_ACCOUNT_ID environment variable is required"
    echo "   Please set it with: export AWS_ACCOUNT_ID=your-account-id"
    echo "   Find your account ID: aws sts get-caller-identity --query Account --output text"
    exit 1
fi

ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/newvelles-docker-lambda"

# Generate timestamp-based tag
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
IMAGE_TAG="py312-qa-${TIMESTAMP}"
LOCAL_IMAGE="docker-lambda-newvelles:${IMAGE_TAG}"
ECR_IMAGE="${ECR_REPO}:${IMAGE_TAG}"

echo "🚀 QA Deployment Pipeline Starting..."
echo "====================================="
echo ""
echo "📋 Configuration:"
echo "   • Function: ${FUNCTION_NAME}"
echo "   • Image Tag: ${IMAGE_TAG}"
echo "   • Account: ${AWS_ACCOUNT_ID}"
echo "   • Region: ${AWS_REGION}"
echo ""

# Step 1: Build Docker image
echo "🏗️ Step 1: Building Docker image..."
echo "Building: ${LOCAL_IMAGE}"
docker buildx build \
    --platform linux/amd64 \
    --provenance=false \
    --load \
    -t "${LOCAL_IMAGE}" \
    .

if [ $? -eq 0 ]; then
    echo "✅ Docker build successful"
else
    echo "❌ Docker build failed"
    exit 1
fi

# Step 2: Tag for ECR
echo ""
echo "🏷️ Step 2: Tagging for ECR..."
docker tag "${LOCAL_IMAGE}" "${ECR_IMAGE}"
echo "Tagged: ${ECR_IMAGE}"

# Step 3: Login to ECR
echo ""
echo "🔐 Step 3: ECR Authentication..."
aws ecr get-login-password --region ${AWS_REGION} | \
    docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

if [ $? -eq 0 ]; then
    echo "✅ ECR login successful"
else
    echo "❌ ECR login failed"
    exit 1
fi

# Step 4: Push to ECR
echo ""
echo "📤 Step 4: Pushing to ECR..."
DOCKER_CONTENT_TRUST=0 docker push "${ECR_IMAGE}"

if [ $? -eq 0 ]; then
    echo "✅ ECR push successful"
else
    echo "❌ ECR push failed"
    exit 1
fi

# Step 5: Update Lambda function
echo ""
echo "🔄 Step 5: Updating Lambda function..."
aws lambda update-function-code \
    --function-name "${FUNCTION_NAME}" \
    --image-uri "${ECR_IMAGE}" \
    --region ${AWS_REGION}

if [ $? -eq 0 ]; then
    echo "✅ Lambda function updated successfully"
else
    echo "❌ Lambda function update failed"
    exit 1
fi

# Step 6: Save build info
echo "${IMAGE_TAG}" > .last-qa-build.txt

echo ""
echo "🎉 QA Deployment Complete!"
echo "=========================="
echo ""
echo "📋 Summary:"
echo "   • Function: ${FUNCTION_NAME}"
echo "   • Image: ${ECR_IMAGE}"
echo "   • Build Info: Saved to .last-qa-build.txt"
echo ""
echo "🧪 Next steps:"
echo "   • Test: make qa-invoke"
echo "   • Verify: make qa-check-s3"
echo "   • Full test: make qa-full-test"
echo ""
echo "✅ Ready for QA testing!"
