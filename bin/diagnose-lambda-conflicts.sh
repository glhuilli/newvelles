#!/bin/bash
# Lambda Conflict Diagnostic Script
# Diagnoses and resolves ResourceConflictException issues

set -e

FUNCTION_NAME="${1:-RunNewvelles}"

echo "🔍 Lambda Conflict Diagnostics"
echo "=============================="
echo "Function: $FUNCTION_NAME"
echo ""

# Check Lambda function state
echo "📊 Lambda Function State:"
LAMBDA_STATE=$(aws lambda get-function --function-name "$FUNCTION_NAME" --query 'Configuration.State' --output text 2>/dev/null || echo "FUNCTION_NOT_FOUND")

if [ "$LAMBDA_STATE" = "FUNCTION_NOT_FOUND" ]; then
    echo "❌ Lambda function '$FUNCTION_NAME' not found"
    exit 1
fi

echo "   State: $LAMBDA_STATE"

LAST_UPDATE_STATUS=$(aws lambda get-function --function-name "$FUNCTION_NAME" --query 'Configuration.LastUpdateStatus' --output text)
echo "   Last Update Status: $LAST_UPDATE_STATUS"

LAST_UPDATE_REASON=$(aws lambda get-function --function-name "$FUNCTION_NAME" --query 'Configuration.LastUpdateStatusReason' --output text 2>/dev/null || echo "N/A")
echo "   Last Update Reason: $LAST_UPDATE_REASON"

echo ""

# Check for ongoing operations
echo "🔄 Checking for ongoing operations..."

if [ "$LAMBDA_STATE" = "Pending" ] || [ "$LAST_UPDATE_STATUS" = "InProgress" ]; then
    echo "⚠️ Lambda function is currently being updated"
    echo "   This explains the ResourceConflictException"
    echo ""
    echo "💡 Solutions:"
    echo "   1. Wait for current update to complete (recommended)"
    echo "   2. Use 'make prod-deploy' which has retry logic"
    echo "   3. Monitor progress: aws lambda get-function --function-name $FUNCTION_NAME"
    echo ""
    
    # Wait and monitor
    echo "⏳ Monitoring update progress..."
    echo "   Press Ctrl+C to stop monitoring"
    echo ""
    
    while true; do
        CURRENT_STATE=$(aws lambda get-function --function-name "$FUNCTION_NAME" --query 'Configuration.State' --output text)
        CURRENT_STATUS=$(aws lambda get-function --function-name "$FUNCTION_NAME" --query 'Configuration.LastUpdateStatus' --output text)
        
        echo "   $(date '+%H:%M:%S') - State: $CURRENT_STATE, Status: $CURRENT_STATUS"
        
        if [ "$CURRENT_STATE" = "Active" ] && [ "$CURRENT_STATUS" = "Successful" ]; then
            echo ""
            echo "✅ Lambda function update completed successfully!"
            echo "   You can now run 'make prod-deploy' safely"
            break
        elif [ "$CURRENT_STATUS" = "Failed" ]; then
            echo ""
            echo "❌ Lambda function update failed"
            FAILURE_REASON=$(aws lambda get-function --function-name "$FUNCTION_NAME" --query 'Configuration.LastUpdateStatusReason' --output text)
            echo "   Reason: $FAILURE_REASON"
            break
        fi
        
        sleep 10
    done
    
elif [ "$LAMBDA_STATE" = "Active" ] && [ "$LAST_UPDATE_STATUS" = "Successful" ]; then
    echo "✅ Lambda function is in good state (Active/Successful)"
    echo "   No ongoing operations detected"
    echo ""
    
    # Check for recent invocations (macOS compatible)
    echo "📈 Checking recent invocations..."
    START_TIME=$(python3 -c "import time; print(int((time.time() - 300) * 1000))" 2>/dev/null || echo $(( ($(date +%s) - 300) * 1000 )))
    RECENT_INVOCATIONS=$(aws logs filter-log-events \
        --log-group-name "/aws/lambda/$FUNCTION_NAME" \
        --start-time "$START_TIME" \
        --query 'events[0].message' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$RECENT_INVOCATIONS" ] && [ "$RECENT_INVOCATIONS" != "None" ]; then
        echo "⚠️ Recent invocations detected (last 5 minutes)"
        echo "   This might cause conflicts if EventBridge is triggering executions"
        echo ""
        echo "💡 To prevent conflicts:"
        echo "   1. Pause EventBridge: make pause-eventbridge"
        echo "   2. Wait for running executions to complete"
        echo "   3. Run deployment: make prod-deploy"
    else
        echo "✅ No recent invocations detected"
        echo "   Function should be safe to update"
    fi
    
elif [ "$LAMBDA_STATE" = "Failed" ]; then
    echo "❌ Lambda function is in Failed state"
    echo "   Reason: $LAST_UPDATE_REASON"
    echo ""
    echo "💡 Solutions:"
    echo "   1. Check CloudWatch logs for errors"
    echo "   2. Try deploying with a known-good image"
    echo "   3. Contact AWS support if issue persists"
    
else
    echo "⚠️ Lambda function in unexpected state: $LAMBDA_STATE"
    echo "   Last update status: $LAST_UPDATE_STATUS"
fi

echo ""

# Check EventBridge status
echo "⏰ EventBridge Status:"
EB_STATE=$(aws events describe-rule --name newvelles-event --query 'State' --output text 2>/dev/null || echo "RULE_NOT_FOUND")

if [ "$EB_STATE" = "RULE_NOT_FOUND" ]; then
    echo "   EventBridge rule not found (no automatic executions)"
elif [ "$EB_STATE" = "ENABLED" ]; then
    echo "⚠️ EventBridge is ENABLED - may trigger conflicting executions"
    echo "   Schedule: $(aws events describe-rule --name newvelles-event --query 'ScheduleExpression' --output text)"
    echo ""
    echo "💡 To prevent conflicts:"
    echo "   make pause-eventbridge"
else
    echo "✅ EventBridge is DISABLED - no automatic executions"
fi

echo ""

# Summary and recommendations
echo "📋 Summary & Recommendations"
echo "============================"

if [ "$LAMBDA_STATE" = "Pending" ] || [ "$LAST_UPDATE_STATUS" = "InProgress" ]; then
    echo "🚨 WAIT: Lambda function is currently updating"
    echo "   Action: Wait for update to complete, then retry"
    
elif [ "$EB_STATE" = "ENABLED" ] && [ "$LAMBDA_STATE" = "Active" ]; then
    echo "⚠️ CAUTION: EventBridge enabled with active function"
    echo "   Action: Pause EventBridge before deployment"
    echo "   Command: make pause-eventbridge && make prod-deploy"
    
elif [ "$LAMBDA_STATE" = "Active" ] && [ "$LAST_UPDATE_STATUS" = "Successful" ]; then
    echo "✅ READY: Safe to deploy"
    echo "   Action: Run deployment with retry logic"
    echo "   Command: make prod-deploy"
    
else
    echo "❓ INVESTIGATE: Unexpected state"
    echo "   Action: Check AWS Console or contact support"
fi

echo ""
echo "🔧 Available Commands:"
echo "   make check-eventbridge     # Check EventBridge status"
echo "   make pause-eventbridge     # Stop automatic executions"
echo "   make prod-deploy           # Deploy with retry logic"
echo "   make resume-eventbridge    # Resume automatic executions"

echo ""
echo "✅ Diagnostic complete!"
