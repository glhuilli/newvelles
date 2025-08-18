#!/bin/bash

# Simple Lambda invocation script compatible with AWS CLI v1
# Usage: ./bin/invoke-lambda-simple.sh <function-name>

set -e

FUNCTION_NAME=$1

if [ -z "$FUNCTION_NAME" ]; then
    echo "❌ Usage: $0 <function-name>"
    echo ""
    echo "🎯 Examples:"
    echo "  $0 RunNewvelles-qa       # Invoke QA function"
    echo "  $0 RunNewvelles          # Invoke production function"
    echo ""
    exit 1
fi

# Create response file with timestamp
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
RESPONSE_FILE="/tmp/lambda-response-${FUNCTION_NAME}-${TIMESTAMP}.json"

echo "🚀 Invoking Lambda Function: $FUNCTION_NAME"
echo "============================================="
echo ""

# Get recent logs before invocation
echo "📊 Recent logs (before invocation):"
echo "-----------------------------------"
aws logs describe-log-streams \
    --log-group-name "/aws/lambda/$FUNCTION_NAME" \
    --order-by LastEventTime \
    --descending \
    --max-items 1 \
    --query 'logStreams[0].logStreamName' \
    --output text 2>/dev/null | while read stream; do
        if [ ! -z "$stream" ] && [ "$stream" != "None" ]; then
            aws logs get-log-events \
                --log-group-name "/aws/lambda/$FUNCTION_NAME" \
                --log-stream-name "$stream" \
                --query 'events[-5:].[timestamp,message]' \
                --output text 2>/dev/null | tail -5
        fi
    done

echo ""
echo "🚀 Invoking Lambda function..."
echo "Function: $FUNCTION_NAME"
echo "Payload: {} (empty)"

# Record start time for filtering logs
INVOKE_START=$(date +%s)

# Invoke the function
aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --cli-read-timeout 900 \
    --cli-connect-timeout 60 \
    "$RESPONSE_FILE"

echo ""
echo "📋 Lambda Response:"
echo "=================="
cat "$RESPONSE_FILE"
echo ""

echo ""
echo "⏳ Waiting 10 seconds for logs to appear..."
sleep 10

echo ""
echo "📊 Recent logs (after invocation):"
echo "----------------------------------"

# Get logs after invocation
aws logs describe-log-streams \
    --log-group-name "/aws/lambda/$FUNCTION_NAME" \
    --order-by LastEventTime \
    --descending \
    --max-items 3 \
    --query 'logStreams[*].logStreamName' \
    --output text 2>/dev/null | tr '\t' '\n' | while read stream; do
        if [ ! -z "$stream" ] && [ "$stream" != "None" ]; then
            echo ""
            echo "📝 Stream: $stream"
            aws logs get-log-events \
                --log-group-name "/aws/lambda/$FUNCTION_NAME" \
                --log-stream-name "$stream" \
                --start-time ${INVOKE_START}000 \
                --query 'events[*].[timestamp,message]' \
                --output text 2>/dev/null | while IFS=$'\t' read timestamp message; do
                    if [ ! -z "$timestamp" ] && [ "$timestamp" != "None" ]; then
                        # Convert timestamp to readable format
                        readable_time=$(date -r $((timestamp/1000)) '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "$timestamp")
                        echo "[$readable_time] $message"
                    fi
                done
        fi
    done

echo ""
echo "📄 Response saved to: $RESPONSE_FILE"
echo ""
echo "📋 Manual log commands for continued monitoring:"
echo "=============================================="
echo "# View recent logs:"
echo "aws logs filter-log-events --log-group-name '/aws/lambda/$FUNCTION_NAME' --start-time ${INVOKE_START}000"
echo ""
echo "# Or view specific log stream:"
echo "aws logs describe-log-streams --log-group-name '/aws/lambda/$FUNCTION_NAME' --order-by LastEventTime --descending --max-items 1"
echo ""
echo "✅ Invocation complete!"
