#!/bin/bash

# Invoke Lambda function and monitor logs in real-time
# Usage: ./bin/invoke-and-monitor.sh <function-name> [payload-file]

set -e

FUNCTION_NAME=$1
PAYLOAD_FILE=${2:-"{}"}

if [ -z "$FUNCTION_NAME" ]; then
    echo "❌ Usage: $0 <function-name> [payload-file]"
    echo ""
    echo "🎯 Examples:"
    echo "  $0 RunNewvelles-qa                    # Invoke QA function"
    echo "  $0 RunNewvelles                       # Invoke production function"
    echo "  $0 RunNewvelles-qa payload.json       # Invoke with custom payload"
    echo ""
    echo "🚀 Available functions:"
    echo "  - RunNewvelles (Production)"
    echo "  - RunNewvelles-qa (QA)"
    echo "  - RunNewvelles-test (Testing)"
    exit 1
fi

# Create response file with timestamp
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
RESPONSE_FILE="/tmp/lambda-response-${FUNCTION_NAME}-${TIMESTAMP}.json"

echo "🚀 Invoking Lambda Function: $FUNCTION_NAME"
echo "============================================="
echo ""

# Start log monitoring in background
echo "📊 Starting log monitoring..."
LOG_PID=""

# Function to start log tailing (compatible with AWS CLI v1)
start_log_tail() {
    echo "🔍 Monitoring logs for $FUNCTION_NAME..."
    
    # Check if AWS CLI v2 'tail' command exists
    if aws logs tail --help >/dev/null 2>&1; then
        echo "Using AWS CLI v2 logs tail command..."
        aws logs tail /aws/lambda/$FUNCTION_NAME --follow &
        LOG_PID=$!
    else
        echo "Using AWS CLI v1 compatible log monitoring..."
        # For AWS CLI v1, we'll check logs periodically
        while true; do
            echo "📊 $(date): Checking recent logs..."
            # Get logs from last 5 minutes
            START_TIME=$(date -u -v-5M +"%Y-%m-%dT%H:%M:%S.000Z" 2>/dev/null || date -u -d '5 minutes ago' +"%Y-%m-%dT%H:%M:%S.000Z" 2>/dev/null || echo "")
            if [ ! -z "$START_TIME" ]; then
                aws logs filter-log-events \
                    --log-group-name "/aws/lambda/$FUNCTION_NAME" \
                    --start-time $(date -d "$START_TIME" +%s)000 \
                    --query 'events[*].[timestamp,message]' \
                    --output text 2>/dev/null | tail -20
            else
                # Fallback: get recent log streams
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
                                --query 'events[-10:].[timestamp,message]' \
                                --output text 2>/dev/null
                        fi
                    done
            fi
            sleep 10
        done &
        LOG_PID=$!
    fi
    echo "Log monitor PID: $LOG_PID"
}

# Function to stop log tailing
stop_log_tail() {
    if [ ! -z "$LOG_PID" ]; then
        echo ""
        echo "🛑 Stopping log monitor..."
        kill $LOG_PID 2>/dev/null || true
        wait $LOG_PID 2>/dev/null || true
    fi
}

# Trap to cleanup log monitoring on exit
trap stop_log_tail EXIT INT TERM

# Start log monitoring
start_log_tail

echo ""
echo "⏳ Waiting 3 seconds for log stream to initialize..."
sleep 3

echo ""
echo "🚀 Invoking Lambda function..."
echo "Function: $FUNCTION_NAME"
if [ "$PAYLOAD_FILE" != "{}" ]; then
    echo "Payload: $PAYLOAD_FILE"
    aws lambda invoke \
        --function-name "$FUNCTION_NAME" \
        --payload fileb://"$PAYLOAD_FILE" \
        --cli-read-timeout 900 \
        --cli-connect-timeout 60 \
        "$RESPONSE_FILE"
else
    echo "Payload: {} (empty)"
    aws lambda invoke \
        --function-name "$FUNCTION_NAME" \
        --cli-read-timeout 900 \
        --cli-connect-timeout 60 \
        "$RESPONSE_FILE"
fi

echo ""
echo "📋 Lambda Response:"
echo "=================="
cat "$RESPONSE_FILE"
echo ""

echo ""
echo "⏳ Waiting 10 seconds for additional logs..."
sleep 10

echo ""
echo "📄 Response saved to: $RESPONSE_FILE"
echo ""
echo "🔍 Log monitoring will continue until you press Ctrl+C"
echo "   Or wait 60 seconds for automatic timeout..."

# Continue monitoring for a bit longer
sleep 60

echo ""
echo "✅ Monitoring complete!"
