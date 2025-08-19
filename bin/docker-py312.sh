#!/bin/bash
# Python 3.12 Optimized Docker Build Script
# Builds Docker images specifically optimized for Python 3.12 + TensorFlow

set -e

# Configuration - requires environment variable
DEFAULT_REGION="us-west-2"
REPO_NAME="newvelles-docker-lambda"

show_usage() {
    echo "Python 3.12 Docker Build Script"
    echo "==============================="
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --tag SUFFIX        Custom tag suffix (default: auto-generated timestamp)"
    echo "  --account ID        AWS account ID (required if \$AWS_ACCOUNT_ID not set)"
    echo "  --region REGION     AWS region (default: ${DEFAULT_REGION})" 
    echo "  --push              Push to ECR after build"
    echo "  --no-cache          Build without using Docker cache"
    echo "  --latest            Also tag as 'latest' (use with caution in production)"
    echo ""
    echo "Examples:"
    echo "  $0                           # Build with timestamp tag"
    echo "  $0 --tag qa-test --push      # Build, tag as 'qa-test', and push to ECR"
    echo "  $0 --no-cache --push         # Clean build and push"
    echo "  $0 --latest --push           # Build and update 'latest' tag (production use)"
}

# Parse arguments
CUSTOM_TAG=""
ACCOUNT_ID="$AWS_ACCOUNT_ID"
REGION=$DEFAULT_REGION
PUSH_TO_ECR=false
NO_CACHE=false
TAG_LATEST=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --tag)
            CUSTOM_TAG="$2"
            shift 2
            ;;
        --account)
            ACCOUNT_ID="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --push)
            PUSH_TO_ECR=true
            shift
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        --latest)
            TAG_LATEST=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate AWS_ACCOUNT_ID is set
if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ Error: AWS_ACCOUNT_ID environment variable is required"
    echo "   Please set it with: export AWS_ACCOUNT_ID=your-account-id"
    echo "   Or provide it with: $0 --account your-account-id"
    echo "   Find your account ID: aws sts get-caller-identity --query Account --output text"
    exit 1
fi

# Generate tag
if [ -n "$CUSTOM_TAG" ]; then
    IMAGE_TAG="py312-${CUSTOM_TAG}"
else
    TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
    IMAGE_TAG="py312-${TIMESTAMP}"
fi

LOCAL_IMAGE="docker-lambda-newvelles:${IMAGE_TAG}"
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}"
ECR_IMAGE="${ECR_REPO}:${IMAGE_TAG}"

echo "🐳 Python 3.12 Docker Build"
echo "============================"
echo ""
echo "📋 Build Configuration:"
echo "   • Local Image: ${LOCAL_IMAGE}"
echo "   • ECR Repository: ${ECR_REPO}"
echo "   • Tag: ${IMAGE_TAG}"
echo "   • No Cache: ${NO_CACHE}"
echo "   • Push to ECR: ${PUSH_TO_ECR}"
echo "   • Tag Latest: ${TAG_LATEST}"
echo ""

# Prepare build command
BUILD_ARGS=(
    "buildx" "build"
    "--platform" "linux/amd64"
    "--provenance=false"
    "--load"
    "-t" "${LOCAL_IMAGE}"
)

if [ "$NO_CACHE" = true ]; then
    BUILD_ARGS+=("--no-cache")
    echo "🧹 Building without cache..."
else
    echo "🏗️ Building with cache..."
fi

BUILD_ARGS+=(".")

# Execute build
echo "Building: ${LOCAL_IMAGE}"
docker "${BUILD_ARGS[@]}"

if [ $? -eq 0 ]; then
    echo "✅ Docker build successful"
else
    echo "❌ Docker build failed"
    exit 1
fi

# Tag for ECR if pushing
if [ "$PUSH_TO_ECR" = true ]; then
    echo ""
    echo "🏷️ Tagging for ECR..."
    docker tag "${LOCAL_IMAGE}" "${ECR_IMAGE}"
    echo "Tagged: ${ECR_IMAGE}"
    
    # Tag as latest if requested
    if [ "$TAG_LATEST" = true ]; then
        docker tag "${LOCAL_IMAGE}" "${ECR_REPO}:latest"
        echo "Tagged: ${ECR_REPO}:latest"
        echo "⚠️  WARNING: 'latest' tag updated - this may affect production!"
    fi
    
    # ECR login
    echo ""
    echo "🔐 Logging into ECR..."
    aws ecr get-login-password --region ${REGION} | \
        docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
    
    if [ $? -ne 0 ]; then
        echo "❌ ECR login failed"
        exit 1
    fi
    
    # Push images
    echo ""
    echo "📤 Pushing to ECR..."
    DOCKER_CONTENT_TRUST=0 docker push "${ECR_IMAGE}"
    
    if [ $? -eq 0 ]; then
        echo "✅ Pushed: ${ECR_IMAGE}"
    else
        echo "❌ Push failed"
        exit 1
    fi
    
    # Push latest if tagged
    if [ "$TAG_LATEST" = true ]; then
        echo ""
        echo "📤 Pushing 'latest' tag..."
        echo "⚠️  This will update production if using 'latest'"
        read -p "Continue with 'latest' push? (y/N): " confirm
        
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            DOCKER_CONTENT_TRUST=0 docker push "${ECR_REPO}:latest"
            echo "✅ Pushed: ${ECR_REPO}:latest"
        else
            echo "⏭️  Skipped 'latest' push"
        fi
    fi
fi

# Save build info
echo "${IMAGE_TAG}" > .last-docker-build.txt

echo ""
echo "🎉 Build Complete!"
echo "=================="
echo ""
echo "📋 Summary:"
echo "   • Local Image: ${LOCAL_IMAGE}"
if [ "$PUSH_TO_ECR" = true ]; then
    echo "   • ECR Image: ${ECR_IMAGE}"
fi
echo "   • Build Info: Saved to .last-docker-build.txt"
echo ""
echo "🚀 Next Steps:"
echo "   • Test locally: docker run --rm ${LOCAL_IMAGE}"
if [ "$PUSH_TO_ECR" = false ]; then
    echo "   • Push to ECR: $0 --tag $(echo ${IMAGE_TAG} | sed 's/py312-//') --push"
fi
echo "   • Deploy to Lambda: make qa-deploy"
echo ""
echo "✅ Python 3.12 image ready!"
