#!/bin/bash

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
    
    # Also tag as 'latest' for convenience
    docker tag ${FULL_IMAGE_NAME} ${IMAGE_NAME}:latest
    echo "🏷️  Tagged as: ${IMAGE_NAME}:latest"
    
    # test new build
    echo "🧪 Testing the new build..."
    CONTAINER_ID=$(docker run -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION -d -p 8080:8080 ${FULL_IMAGE_NAME})
    echo "🚀 Container started: ${CONTAINER_ID}"
    echo "📡 Test endpoint: http://localhost:8080/2015-03-31/functions/function/invocations"
    
    # add tag for ECR if account ID provided
    if [ ! -z "$1" ]; then
        ECR_REPO="$1.dkr.ecr.us-west-2.amazonaws.com/newvelles-docker-lambda"
        docker tag ${FULL_IMAGE_NAME} ${ECR_REPO}:${IMAGE_TAG}
        docker tag ${FULL_IMAGE_NAME} ${ECR_REPO}:latest
        echo "🏷️  Tagged for ECR: ${ECR_REPO}:${IMAGE_TAG}"
        echo "🏷️  Tagged for ECR: ${ECR_REPO}:latest"
        
        # login to ECR 
        echo "🔐 Logging into ECR..."
        sh bin/ecr.sh
        
        # push to ECR
        echo "📤 Pushing to ECR..."
        docker push ${ECR_REPO}:${IMAGE_TAG}
        echo "✅ Pushed to ECR: ${ECR_REPO}:${IMAGE_TAG}"
        
        # Ask before pushing 'latest' to avoid production impact
        echo ""
        echo "⚠️  Push 'latest' tag? This will update production if using 'latest'"
        read -p "Push latest tag? (y/N): " push_latest
        if [ "$push_latest" = "y" ] || [ "$push_latest" = "Y" ]; then
            docker push ${ECR_REPO}:latest
            echo "✅ Pushed to ECR: ${ECR_REPO}:latest"
        else
            echo "⏭️  Skipped pushing 'latest' tag"
        fi
    else
        echo "⚠️  No AWS account ID provided - skipping ECR push"
        echo "💡 Usage: $0 <aws-account-id>"
    fi
    
    echo ""
    echo "📋 Image Summary:"
    echo "   Local Image: ${FULL_IMAGE_NAME}"
    echo "   Local Latest: ${IMAGE_NAME}:latest"
    echo "   Container ID: ${CONTAINER_ID}"
    echo "   Timestamp: ${TIMESTAMP}"
    
else
    echo "❌ Build failed"
    exit 1
fi


