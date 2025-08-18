#!/bin/bash

# Local Docker Testing Script with Environment Variables
# This script builds and runs the lambda container with test S3 buckets

set -e  # Exit on any error

# Generate timestamp for unique container names
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
IMAGE_NAME="docker-lambda-newvelles"
IMAGE_TAG="test-${TIMESTAMP}"
CONTAINER_NAME="newvelles-lambda-test-${TIMESTAMP}"

echo "🔧 Building lambda container for local testing..."
echo "🏷️  Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "📦 Container: ${CONTAINER_NAME}"
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo "🔍 Checking for .env.local file..."
if [ -f ".env.local" ]; then
    echo "✅ Found .env.local file, using local environment variables"
    ENV_FILE=".env.local"
else
    echo "⚠️  No .env.local file found. Using default test values."
    echo "   Create .env.local from env.local.example for custom configuration"
    ENV_FILE="/dev/null"
fi

echo "🚀 Starting lambda container with test environment..."

# Run container with environment variables from .env.local if it exists
if [ -f ".env.local" ]; then
    docker run --env-file .env.local \
        -d -p 8080:8080 \
        --name ${CONTAINER_NAME} \
        ${IMAGE_NAME}:${IMAGE_TAG}
else
    # Fallback with test bucket names as environment variables
    docker run \
        -e AWS_S3_BUCKET=newvelles-test-bucket \
        -e AWS_S3_PUBLIC_BUCKET=public-newvelles-test-bucket \
        -e AWS_ACCESS_KEY_ID \
        -e AWS_SECRET_ACCESS_KEY \
        -e AWS_DEFAULT_REGION \
        -d -p 8080:8080 \
        --name ${CONTAINER_NAME} \
        ${IMAGE_NAME}:${IMAGE_TAG}
fi

echo "⏳ Waiting for container to start..."
sleep 3

echo "🧪 Testing lambda endpoint..."
curl -XPOST "http://localhost:8080/2015-03-31/functions/function/invocations" \
    -d '{"test": "local_test", "environment": "testing"}' \
    -H "Content-Type: application/json" | jq '.' || echo "Response received (jq not available)"

echo ""
echo "📋 Container is running. You can:"
echo "   - Test more requests: curl -XPOST \"http://localhost:8080/2015-03-31/functions/function/invocations\" -d '{\"test\":\"data\"}'"
echo "   - View logs: docker logs ${CONTAINER_NAME}"
echo "   - Stop container: docker stop ${CONTAINER_NAME}"
echo "   - Remove container: docker rm ${CONTAINER_NAME}"
echo ""
echo "🏷️  Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "📦 Container: ${CONTAINER_NAME}"
echo "⏰ Timestamp: ${TIMESTAMP}"
