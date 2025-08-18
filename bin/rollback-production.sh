#!/bin/bash
# Production Rollback Script
# Allows rolling back to a previous Docker image version

set -e

# AWS Configuration - requires environment variable
ACCOUNT_ID="$AWS_ACCOUNT_ID"
REGION="us-west-2"
REPOSITORY="newvelles-docker-lambda"
LAMBDA_FUNCTION="RunNewvelles"

# Validate AWS_ACCOUNT_ID is set
if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ Error: AWS_ACCOUNT_ID environment variable is required"
    echo "   Please set it with: export AWS_ACCOUNT_ID=your-account-id"
    echo "   Find your account ID: aws sts get-caller-identity --query Account --output text"
    exit 1
fi

echo "🔄 Production Rollback System"
echo "============================="
echo ""

# Get current production image
echo "📊 Current Production Configuration:"
CURRENT_IMAGE=$(aws lambda get-function --function-name "$LAMBDA_FUNCTION" --query 'Code.ImageUri' --output text)
CURRENT_TAG=$(echo "$CURRENT_IMAGE" | cut -d':' -f2)
echo "   Current Image: $CURRENT_TAG"
echo ""

# Get available images with better formatting
echo "📦 Available Docker Images for Rollback:"
echo ""

# Get images and format them nicely
IMAGES_JSON=$(aws ecr describe-images \
    --repository-name "$REPOSITORY" \
    --query 'sort_by(imageDetails[?imageTags], &imagePushedAt) | reverse(@)' \
    --output json)

# Parse and display images
echo "$IMAGES_JSON" | jq -r '
.[] | 
select(.imageTags != null) | 
{
    tag: .imageTags[0],
    pushed: .imagePushedAt,
    size: .imageSizeInBytes
} | 
[
    .tag,
    (.pushed | strftime("%Y-%m-%d %H:%M UTC")),
    ((.size / 1024 / 1024) | floor | tostring + " MB")
] | 
@tsv' | nl -w3 -s'. ' | while read line; do
    echo "   $line"
done

echo ""

# Let user select image
echo "🎯 Select Image to Rollback To:"
echo ""

# Create array of image tags
TAGS=($(echo "$IMAGES_JSON" | jq -r '.[] | select(.imageTags != null) | .imageTags[0]'))

if [ ${#TAGS[@]} -eq 0 ]; then
    echo "❌ No tagged images found for rollback"
    exit 1
fi

# Get user selection
while true; do
    read -p "Enter image number (1-${#TAGS[@]}) or 'q' to quit: " selection
    
    if [ "$selection" = "q" ] || [ "$selection" = "quit" ]; then
        echo "❌ Rollback cancelled"
        exit 0
    fi
    
    if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le ${#TAGS[@]} ]; then
        SELECTED_INDEX=$((selection - 1))
        SELECTED_TAG=${TAGS[$SELECTED_INDEX]}
        break
    else
        echo "❌ Invalid selection. Please enter a number between 1 and ${#TAGS[@]}"
    fi
done

echo ""
echo "🔍 Selected Image: $SELECTED_TAG"

# Check if it's the same as current
if [ "$SELECTED_TAG" = "$CURRENT_TAG" ]; then
    echo "ℹ️ Selected image is the same as current production image"
    read -p "Continue anyway? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "❌ Rollback cancelled"
        exit 0
    fi
fi

# Show rollback summary
echo ""
echo "📋 Rollback Summary:"
echo "   From: $CURRENT_TAG"
echo "   To:   $SELECTED_TAG"
echo "   Function: $LAMBDA_FUNCTION"
echo ""

# Final confirmation
echo "⚠️  PRODUCTION ROLLBACK CONFIRMATION"
echo "===================================="
echo "This will roll back the production Lambda function to a previous version."
echo "The EventBridge schedule will be paused during rollback for safety."
echo ""

read -p "Are you absolutely sure you want to proceed? (yes/no): " final_confirm

if [ "$final_confirm" != "yes" ]; then
    echo "❌ Rollback cancelled"
    exit 0
fi

echo ""
echo "🚀 Starting Production Rollback..."
echo "================================="

# Pause EventBridge
echo "⏸️ Pausing EventBridge scheduling..."
aws events disable-rule --name newvelles-event
echo "✅ EventBridge paused"

# Wait for any running executions
echo "⏳ Waiting 15 seconds for any running executions to complete..."
sleep 15

# Perform rollback
echo "🔄 Rolling back Lambda function..."
ROLLBACK_IMAGE_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPOSITORY}:${SELECTED_TAG}"

echo "   Image URI: $ROLLBACK_IMAGE_URI"

aws lambda update-function-code \
    --function-name "$LAMBDA_FUNCTION" \
    --image-uri "$ROLLBACK_IMAGE_URI"

if [ $? -ne 0 ]; then
    echo "❌ Rollback failed!"
    echo "🔄 Re-enabling EventBridge..."
    aws events enable-rule --name newvelles-event
    exit 1
fi

echo "✅ Lambda function rolled back successfully"

# Wait for function to be ready
echo "⏳ Waiting for Lambda function to be ready..."
aws lambda wait function-updated --function-name "$LAMBDA_FUNCTION"

# Test the rollback
echo ""
echo "🧪 Testing Rollback..."
echo "====================="

# Quick test invocation
echo "🚀 Performing test invocation..."
RESPONSE_FILE="/tmp/rollback-test-$(date +%Y%m%d-%H%M%S).json"

aws lambda invoke \
    --function-name "$LAMBDA_FUNCTION" \
    --payload '{}' \
    "$RESPONSE_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Test invocation successful"
    echo "📋 Response:"
    cat "$RESPONSE_FILE"
    echo ""
    rm -f "$RESPONSE_FILE"
else
    echo "❌ Test invocation failed!"
    echo "⚠️ Production may be in a broken state"
    echo "🔄 Re-enabling EventBridge anyway..."
    aws events enable-rule --name newvelles-event
    exit 1
fi

# Resume EventBridge
echo "▶️ Resuming EventBridge scheduling..."
aws events enable-rule --name newvelles-event

if [ $? -eq 0 ]; then
    echo "✅ EventBridge scheduling resumed"
else
    echo "⚠️ Failed to resume EventBridge - please enable manually:"
    echo "   aws events enable-rule --name newvelles-event"
fi

# Show final status
echo ""
echo "🎉 Rollback Completed Successfully!"
echo "=================================="
echo ""
echo "📊 New Production Status:"
echo "   Lambda Function: $LAMBDA_FUNCTION"
echo "   Image Tag: $SELECTED_TAG"
echo "   EventBridge: ENABLED (6-hour schedule)"
echo ""
echo "📋 Next Steps:"
echo "1. Monitor CloudWatch logs:"
echo "   aws logs tail /aws/lambda/$LAMBDA_FUNCTION --follow"
echo ""
echo "2. Check S3 bucket updates after next execution:"
echo "   aws s3 ls s3://public-newvelles-data-bucket/ --human-readable"
echo ""
echo "3. If issues persist, you can roll back again:"
echo "   make rollback-prod"
echo ""
echo "✅ Production rollback complete!"
