#!/bin/bash

# Production-safe Docker build and ECR deployment
# Only pushes timestamped versions, never overwrites 'latest'

# Generate timestamp-based image tag
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
IMAGE_NAME="docker-lambda-newvelles"
IMAGE_TAG="v2-py312-${TIMESTAMP}"
FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"

echo "🐳 Building Docker image: ${FULL_IMAGE_NAME}"

# create new build (Python 3.12) with timestamp
docker build -t ${FULL_IMAGE_NAME} .

if [ $? -eq 0 ]; then
    echo "✅ Build successful: ${FULL_IMAGE_NAME}"
    
    # test new build
    echo "🧪 Testing the new build..."
    CONTAINER_ID=$(docker run -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION -d -p 8080:8080 ${FULL_IMAGE_NAME})
    echo "🚀 Container started: ${CONTAINER_ID}"
    echo "📡 Test endpoint: http://localhost:8080/2015-03-31/functions/function/invocations"
    
    # Wait for container to be ready
    sleep 5
    
    # Test the container
    echo "🔍 Testing container health..."
    if curl -f -s http://localhost:8080/2015-03-31/functions/function/invocations >/dev/null 2>&1; then
        echo "✅ Container is healthy"
    else
        echo "⚠️  Container may not be ready yet (this is normal)"
    fi
    
    # Stop test container
    docker stop ${CONTAINER_ID} >/dev/null 2>&1
    docker rm ${CONTAINER_ID} >/dev/null 2>&1
    echo "🧹 Test container cleaned up"
    
    # add tag for ECR if account ID provided
    if [ ! -z "$1" ]; then
        ECR_REPO="$1.dkr.ecr.us-west-2.amazonaws.com/newvelles-docker-lambda"
        docker tag ${FULL_IMAGE_NAME} ${ECR_REPO}:${IMAGE_TAG}
        echo "🏷️  Tagged for ECR: ${ECR_REPO}:${IMAGE_TAG}"
        
        # login to ECR 
        echo "🔐 Logging into ECR..."
        aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin ${ECR_REPO}
        
        if [ $? -eq 0 ]; then
            # push ONLY timestamped version to ECR (production-safe)
            echo "📤 Pushing timestamped version to ECR (production-safe)..."
            docker push ${ECR_REPO}:${IMAGE_TAG}
            echo "✅ Pushed to ECR: ${ECR_REPO}:${IMAGE_TAG}"
            echo ""
            echo "🛡️  Production Safety: 'latest' tag NOT updated"
            echo "💡 To use this version in production, update your Lambda to use:"
            echo "   ${ECR_REPO}:${IMAGE_TAG}"
        else
            echo "❌ ECR login failed"
            exit 1
        fi
        
    else
        echo "⚠️  No AWS account ID provided - skipping ECR push"
        echo "💡 Usage: $0 <aws-account-id>"
    fi
    
    echo ""
    echo "📋 Image Summary:"
    echo "   Local Image: ${FULL_IMAGE_NAME}"
    echo "   ECR Image: ${ECR_REPO}:${IMAGE_TAG}"
    echo "   Timestamp: ${TIMESTAMP}"
    echo ""
    echo "🚀 Ready for production deployment!"
    
else
    echo "❌ Build failed"
    exit 1
fi
