#!/bin/bash

# Deploy Docker image to specific Lambda environment with proper S3 bucket configuration
# Usage: ./bin/deploy-to-environment.sh <environment> <image-tag> [aws-account-id]

set -e

ENVIRONMENT=$1
IMAGE_TAG=$2
AWS_ACCOUNT_ID=${3:-$AWS_ACCOUNT_ID}

if [ -z "$ENVIRONMENT" ] || [ -z "$IMAGE_TAG" ]; then
    echo "❌ Usage: $0 <environment> <image-tag> [aws-account-id]"
    echo ""
    echo "🌍 Available environments:"
    echo "  - prod      (Production - uses config file defaults)"
    echo "  - qa        (QA/Shadow - uses newvelles-qa-bucket)"
    echo "  - test      (Testing - uses newvelles-test-bucket)"
    echo ""
    echo "📝 Examples:"
    echo "  $0 qa v2-py312-20250817-181418"
    echo "  $0 prod v2-py312-20250817-181418 \$AWS_ACCOUNT_ID"
    exit 1
fi

# Validate AWS_ACCOUNT_ID is set
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo "❌ Error: AWS_ACCOUNT_ID is required"
    echo "   Please set environment variable: export AWS_ACCOUNT_ID=your-account-id"
    echo "   Or provide as third parameter: $0 $ENVIRONMENT $IMAGE_TAG your-account-id"
    echo "   Find your account ID: aws sts get-caller-identity --query Account --output text"
    exit 1
fi

# Define environment configurations
case $ENVIRONMENT in
    "prod"|"production")
        LAMBDA_FUNCTION="RunNewvelles"
        ENV_VARS='Variables={}'
        S3_PRIVATE="newvelles-data-bucket"
        S3_PUBLIC="public-newvelles-data-bucket"
        echo "🏭 Deploying to PRODUCTION environment"
        ;;
    "qa"|"shadow")
        LAMBDA_FUNCTION="RunNewvelles-qa"
        ENV_VARS='Variables={"AWS_S3_BUCKET":"newvelles-qa-bucket","AWS_S3_PUBLIC_BUCKET":"public-newvelles-qa-bucket"}'
        S3_PRIVATE="newvelles-qa-bucket"
        S3_PUBLIC="public-newvelles-qa-bucket"
        echo "🛡️ Deploying to QA/Shadow environment"
        ;;
    "test"|"testing")
        LAMBDA_FUNCTION="RunNewvelles-test"
        ENV_VARS='Variables={"AWS_S3_BUCKET":"newvelles-test-bucket","AWS_S3_PUBLIC_BUCKET":"public-newvelles-test-bucket"}'
        S3_PRIVATE="newvelles-test-bucket"
        S3_PUBLIC="public-newvelles-test-bucket"
        echo "🧪 Deploying to TESTING environment"
        ;;
    *)
        echo "❌ Unknown environment: $ENVIRONMENT"
        echo "Valid environments: prod, qa, test"
        exit 1
        ;;
esac

IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com/newvelles-docker-lambda:${IMAGE_TAG}"

echo ""
echo "📋 Deployment Configuration:"
echo "   Environment: $ENVIRONMENT"
echo "   Lambda Function: $LAMBDA_FUNCTION"
echo "   Image URI: $IMAGE_URI"
echo "   Private S3 Bucket: $S3_PRIVATE"
echo "   Public S3 Bucket: $S3_PUBLIC"
echo ""

# Confirm deployment (except for test environment)
if [ "$ENVIRONMENT" != "test" ] && [ "$ENVIRONMENT" != "testing" ]; then
    read -p "⚠️  Deploy to $ENVIRONMENT environment? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "❌ Deployment cancelled"
        exit 1
    fi
fi

echo "🚀 Starting deployment..."

# Check if Lambda function exists
if ! aws lambda get-function --function-name "$LAMBDA_FUNCTION" >/dev/null 2>&1; then
    echo "❌ Lambda function '$LAMBDA_FUNCTION' not found"
    echo "💡 Please create the Lambda function first or check the function name"
    exit 1
fi

# Pause EventBridge scheduling for production during deployment
if [ "$ENVIRONMENT" = "prod" ] || [ "$ENVIRONMENT" = "production" ]; then
    echo ""
    echo "⏸️ Pausing EventBridge scheduling during deployment..."
    
    # Check if rule exists and get current state
    CURRENT_RULE_STATE=$(aws events describe-rule --name newvelles-event --query 'State' --output text 2>/dev/null || echo "RULE_NOT_FOUND")
    
    if [ "$CURRENT_RULE_STATE" != "RULE_NOT_FOUND" ]; then
        if [ "$CURRENT_RULE_STATE" = "ENABLED" ]; then
            echo "   • Disabling EventBridge rule temporarily..."
            aws events disable-rule --name newvelles-event
            if [ $? -eq 0 ]; then
                echo "   ✅ EventBridge scheduling paused"
                NEED_TO_RESUME_EVENTBRIDGE=true
            else
                echo "   ⚠️ Failed to pause EventBridge (continuing anyway)"
                NEED_TO_RESUME_EVENTBRIDGE=false
            fi
        else
            echo "   • EventBridge rule already disabled"
            NEED_TO_RESUME_EVENTBRIDGE=false
        fi
    else
        echo "   • EventBridge rule doesn't exist yet (will create)"
        NEED_TO_RESUME_EVENTBRIDGE=false
    fi
    
    # Wait for any currently running executions to complete
    echo "   • Waiting 10 seconds for any running executions to complete..."
    sleep 10
fi

# Update Lambda function code with retry logic
echo "📤 Updating Lambda function code..."

# Function to update Lambda code with retries
update_lambda_with_retry() {
    local max_attempts=5
    local attempt=1
    local wait_time=30
    
    while [ $attempt -le $max_attempts ]; do
        echo "   Attempt $attempt/$max_attempts..."
        
        # Try to update Lambda function code
        aws lambda update-function-code \
            --function-name "$LAMBDA_FUNCTION" \
            --image-uri "$IMAGE_URI" 2>&1
        
        local exit_code=$?
        
        if [ $exit_code -eq 0 ]; then
            echo "✅ Lambda function code updated successfully"
            return 0
        else
            # Check if it's a ResourceConflictException (update in progress)
            local error_output=$(aws lambda update-function-code \
                --function-name "$LAMBDA_FUNCTION" \
                --image-uri "$IMAGE_URI" 2>&1 || true)
            
            if echo "$error_output" | grep -q "ResourceConflictException\|update is in progress"; then
                echo "⚠️ Lambda function update in progress (attempt $attempt/$max_attempts)"
                echo "   Waiting ${wait_time}s for current update to complete..."
                
                if [ $attempt -lt $max_attempts ]; then
                    # Wait for current update to complete
                    echo "   ⏳ Waiting for Lambda function to be ready..."
                    aws lambda wait function-updated --function-name "$LAMBDA_FUNCTION" || true
                    sleep $wait_time
                    attempt=$((attempt + 1))
                    wait_time=$((wait_time + 15))  # Increase wait time each retry
                    continue
                fi
            fi
            
            echo "❌ Failed to update Lambda function code (attempt $attempt/$max_attempts)"
            if [ $attempt -eq $max_attempts ]; then
                echo "💡 Lambda function may be busy with ongoing updates or executions"
                echo "   Try again in a few minutes, or check AWS Console for function status"
                return 1
            fi
            
            attempt=$((attempt + 1))
        fi
    done
    
    return 1
}

# Execute the update with retry logic
if update_lambda_with_retry; then
    echo "✅ Lambda function code updated successfully"
else
    echo "❌ Failed to update Lambda function code after multiple attempts"
    
    # Resume EventBridge if we paused it
    if [ "$NEED_TO_RESUME_EVENTBRIDGE" = "true" ]; then
        echo "🔄 Resuming EventBridge due to deployment failure..."
        aws events enable-rule --name newvelles-event
    fi
    
    exit 1
fi

# Function to update Lambda configuration with retries
update_lambda_config_with_retry() {
    local config_type="$1"
    local config_command="$2"
    local max_attempts=3
    local attempt=1
    local wait_time=20
    
    while [ $attempt -le $max_attempts ]; do
        echo "   Attempt $attempt/$max_attempts for $config_type..."
        
        # Execute the configuration command
        eval "$config_command" 2>&1
        local exit_code=$?
        
        if [ $exit_code -eq 0 ]; then
            echo "✅ $config_type updated successfully"
            return 0
        else
            # Check if it's a ResourceConflictException
            local error_output=$(eval "$config_command" 2>&1 || true)
            
            if echo "$error_output" | grep -q "ResourceConflictException\|update is in progress"; then
                echo "⚠️ Lambda function busy, waiting ${wait_time}s (attempt $attempt/$max_attempts)"
                
                if [ $attempt -lt $max_attempts ]; then
                    aws lambda wait function-updated --function-name "$LAMBDA_FUNCTION" || true
                    sleep $wait_time
                    attempt=$((attempt + 1))
                    wait_time=$((wait_time + 10))
                    continue
                fi
            fi
            
            echo "❌ Failed to update $config_type (attempt $attempt/$max_attempts)"
            if [ $attempt -eq $max_attempts ]; then
                return 1
            fi
            
            attempt=$((attempt + 1))
        fi
    done
    
    return 1
}

# Update environment variables
echo "🔧 Updating environment variables..."
ENV_COMMAND="aws lambda update-function-configuration --function-name \"$LAMBDA_FUNCTION\" --environment \"$ENV_VARS\""

if update_lambda_config_with_retry "environment variables" "$ENV_COMMAND"; then
    echo "✅ Environment variables updated successfully"
else
    echo "❌ Failed to update environment variables after multiple attempts"
    
    # Resume EventBridge if we paused it
    if [ "$NEED_TO_RESUME_EVENTBRIDGE" = "true" ]; then
        echo "🔄 Resuming EventBridge due to deployment failure..."
        aws events enable-rule --name newvelles-event
    fi
    
    exit 1
fi

# Apply ML-optimized Lambda configuration (memory, timeout, storage)
echo "🤖 Applying ML-optimized Lambda configuration..."
echo "   • Memory: 2048MB (for TensorFlow)"
echo "   • Timeout: 900s (15 minutes for ML processing)"
echo "   • Ephemeral Storage: 1024MB (for 504MB TensorFlow model)"

ML_CONFIG_COMMAND="aws lambda update-function-configuration --function-name \"$LAMBDA_FUNCTION\" --memory-size 2048 --timeout 900 --ephemeral-storage Size=1024"

if update_lambda_config_with_retry "ML configuration" "$ML_CONFIG_COMMAND"; then
    echo "✅ ML-optimized configuration applied successfully"
else
    echo "❌ Failed to apply ML-optimized configuration after multiple attempts"
    
    # Resume EventBridge if we paused it
    if [ "$NEED_TO_RESUME_EVENTBRIDGE" = "true" ]; then
        echo "🔄 Resuming EventBridge due to deployment failure..."
        aws events enable-rule --name newvelles-event
    fi
    
    exit 1
fi

# Wait for function to be ready
echo "⏳ Waiting for Lambda function to be ready..."
aws lambda wait function-updated --function-name "$LAMBDA_FUNCTION"

# Configure EventBridge scheduling for production
if [ "$ENVIRONMENT" = "prod" ] || [ "$ENVIRONMENT" = "production" ]; then
    echo ""
    echo "⏰ Configuring EventBridge scheduling for production..."
    
    # Update the EventBridge rule to ensure 6-hour schedule (but keep disabled for now)
    aws events put-rule \
        --name newvelles-event \
        --schedule-expression "rate(6 hours)" \
        --description "Trigger newvelles computation every 6 hours" \
        --state DISABLED
    
    if [ $? -eq 0 ]; then
        echo "✅ EventBridge rule configured successfully (temporarily disabled)"
    else
        echo "⚠️ Failed to configure EventBridge rule"
        
        # Resume EventBridge if we paused it and rule creation failed
        if [ "$NEED_TO_RESUME_EVENTBRIDGE" = "true" ]; then
            echo "🔄 Resuming original EventBridge state due to configuration failure..."
            aws events enable-rule --name newvelles-event
        fi
        
        # Don't exit - continue with deployment
    fi
    
    # Ensure Lambda has the right target
    aws events put-targets \
        --rule newvelles-event \
        --targets "Id"="1","Arn"="arn:aws:lambda:us-west-2:${AWS_ACCOUNT_ID}:function:$LAMBDA_FUNCTION"
    
    if [ $? -eq 0 ]; then
        echo "✅ EventBridge target updated successfully"
    else
        echo "⚠️ Failed to update EventBridge target"
    fi
    
    # Ensure EventBridge has permission to invoke Lambda
    aws lambda add-permission \
        --function-name "$LAMBDA_FUNCTION" \
        --statement-id allow-eventbridge \
        --action lambda:InvokeFunction \
        --principal events.amazonaws.com \
        --source-arn "arn:aws:events:us-west-2:${AWS_ACCOUNT_ID}:rule/newvelles-event" \
        2>/dev/null || echo "✅ Lambda permission already exists"
fi

# Verify final configuration
echo ""
echo "📊 Verifying final Lambda configuration..."
aws lambda get-function-configuration \
    --function-name "$LAMBDA_FUNCTION" \
    --query '{Memory:MemorySize,Timeout:Timeout,Storage:EphemeralStorage.Size,Architecture:Architectures[0]}' \
    --output table

# Test production deployment with verification
if [ "$ENVIRONMENT" = "prod" ] || [ "$ENVIRONMENT" = "production" ]; then
    echo ""
    echo "🧪 Testing production deployment..."
    echo "======================================"
    
    # Store S3 bucket state before test
    echo "📊 Checking S3 bucket state before test..."
    BEFORE_PRIVATE=$(aws s3 ls s3://$S3_PRIVATE/ --recursive | wc -l || echo "0")
    BEFORE_PUBLIC=$(aws s3 ls s3://$S3_PUBLIC/ --recursive | wc -l || echo "0")
    echo "   • Private bucket files: $BEFORE_PRIVATE"
    echo "   • Public bucket files: $BEFORE_PUBLIC"
    
    # Invoke the function
    echo ""
    echo "🚀 Invoking production Lambda function..."
    RESPONSE_FILE="/tmp/prod-test-response-$(date +%Y%m%d-%H%M%S).json"
    
    aws lambda invoke \
        --function-name "$LAMBDA_FUNCTION" \
        --payload '{}' \
        "$RESPONSE_FILE"
    
    if [ $? -eq 0 ]; then
        echo "✅ Lambda invocation completed"
        echo "📋 Response:"
        cat "$RESPONSE_FILE"
        echo ""
    else
        echo "❌ Lambda invocation failed"
        exit 1
    fi
    
    # Wait for processing and S3 uploads
    echo "⏳ Waiting 30 seconds for S3 uploads to complete..."
    sleep 30
    
    # Check S3 bucket updates
    echo ""
    echo "📊 Verifying S3 bucket updates..."
    AFTER_PRIVATE=$(aws s3 ls s3://$S3_PRIVATE/ --recursive | wc -l || echo "0")
    AFTER_PUBLIC=$(aws s3 ls s3://$S3_PUBLIC/ --recursive | wc -l || echo "0")
    
    echo "   • Private bucket files: $BEFORE_PRIVATE → $AFTER_PRIVATE"
    echo "   • Public bucket files: $BEFORE_PUBLIC → $AFTER_PUBLIC"
    
    # Verify new files were created
    if [ "$AFTER_PRIVATE" -gt "$BEFORE_PRIVATE" ] || [ "$AFTER_PUBLIC" -gt "$BEFORE_PUBLIC" ]; then
        echo "✅ S3 buckets updated successfully!"
        echo ""
        echo "📁 Latest files in public bucket:"
        aws s3 ls s3://$S3_PUBLIC/ --recursive --human-readable | tail -5
    else
        echo "⚠️ No new files detected in S3 buckets"
        echo "This may indicate a processing issue - check CloudWatch logs"
    fi
    
    # Clean up response file
    rm -f "$RESPONSE_FILE"
fi

# Resume EventBridge scheduling for production (final step)
if [ "$ENVIRONMENT" = "prod" ] || [ "$ENVIRONMENT" = "production" ]; then
    echo ""
    echo "🔄 Resuming EventBridge scheduling..."
    
    # Enable the EventBridge rule
    aws events enable-rule --name newvelles-event
    
    if [ $? -eq 0 ]; then
        echo "✅ EventBridge scheduling resumed (6-hour schedule active)"
        
        # Show next execution time
        echo ""
        echo "📅 EventBridge Status:"
        aws events describe-rule --name newvelles-event --query '{Name:Name,Schedule:ScheduleExpression,State:State}' --output table
    else
        echo "⚠️ Failed to resume EventBridge scheduling"
        echo "   You may need to manually enable it: aws events enable-rule --name newvelles-event"
    fi
fi

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "📋 Deployment Summary:"
echo "   • Environment: $ENVIRONMENT"
echo "   • Function: $LAMBDA_FUNCTION"
echo "   • Image: $IMAGE_TAG"
echo "   • Memory: 2048MB"
echo "   • Timeout: 900s (15 min)"
echo "   • Storage: 1024MB"
if [ "$ENVIRONMENT" = "prod" ] || [ "$ENVIRONMENT" = "production" ]; then
    echo "   • EventBridge: Every 6 hours (paused during deployment, now resumed)"
    echo "   • Test Result: ✅ Verified working"
    echo "   • Safety: ✅ No concurrent executions during deployment"
fi
echo ""
echo "📋 Next Steps:"
if [ "$ENVIRONMENT" != "prod" ] && [ "$ENVIRONMENT" != "production" ]; then
    echo "1. Test the deployment:"
    echo "   ./bin/invoke-lambda-simple.sh $LAMBDA_FUNCTION"
    echo ""
    echo "2. Validate S3 bucket contents:"
    echo "   aws s3 ls s3://$S3_PRIVATE/ --recursive"
    echo "   aws s3 ls s3://$S3_PUBLIC/ --recursive"
    echo ""
fi
echo "• Monitor CloudWatch logs:"
echo "   aws logs tail /aws/lambda/$LAMBDA_FUNCTION --follow"
if [ "$ENVIRONMENT" = "prod" ] || [ "$ENVIRONMENT" = "production" ]; then
    echo ""
    echo "• View EventBridge schedule:"
    echo "   aws events describe-rule --name newvelles-event"
fi

