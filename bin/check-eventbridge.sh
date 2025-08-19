#!/bin/bash
# EventBridge Configuration Checker
# Verifies EventBridge scheduling configuration for production

set -e

echo "🔍 EventBridge Configuration Checker"
echo "====================================="
echo ""

# Check if EventBridge rule exists
echo "📋 Checking EventBridge rule..."
RULE_INFO=$(aws events describe-rule --name newvelles-event 2>/dev/null || echo "")

if [ -z "$RULE_INFO" ]; then
    echo "❌ EventBridge rule 'newvelles-event' not found"
    echo ""
    echo "💡 To create the rule, run:"
    echo "   make prod-deploy"
    echo "   or manually:"
    echo "   aws events put-rule --name newvelles-event --schedule-expression 'rate(6 hours)' --state ENABLED"
    exit 1
else
    echo "✅ EventBridge rule found"
    echo "$RULE_INFO" | jq '{Name: .Name, Schedule: .ScheduleExpression, State: .State, Description: .Description}'
fi

echo ""

# Check targets
echo "🎯 Checking EventBridge targets..."
TARGETS=$(aws events list-targets-by-rule --rule newvelles-event 2>/dev/null || echo "")

if [ -z "$TARGETS" ] || [ "$(echo "$TARGETS" | jq '.Targets | length')" -eq 0 ]; then
    echo "❌ No targets configured for EventBridge rule"
    echo ""
    echo "💡 To add target, run:"
    echo "   aws events put-targets --rule newvelles-event --targets 'Id=1,Arn=arn:aws:lambda:us-west-2:\$AWS_ACCOUNT_ID:function:RunNewvelles'"
else
    echo "✅ EventBridge targets found"
    echo "$TARGETS" | jq '.Targets[] | {Id: .Id, Function: .Arn | split(":") | last}'
fi

echo ""

# Check Lambda permissions
echo "🔐 Checking Lambda permissions..."
POLICY=$(aws lambda get-policy --function-name RunNewvelles 2>/dev/null || echo "")

if [ -z "$POLICY" ]; then
    echo "❌ No Lambda policy found"
else
    EVENTBRIDGE_PERMISSION=$(echo "$POLICY" | jq -r '.Policy' | jq -r 'fromjson | .Statement[] | select(.Principal.Service? == "events.amazonaws.com") | .Sid' 2>/dev/null || echo "")
    
    if [ -z "$EVENTBRIDGE_PERMISSION" ] || [ "$EVENTBRIDGE_PERMISSION" = "null" ]; then
        echo "❌ EventBridge permission not found in Lambda policy"
        echo ""
        echo "💡 To add permission, run:"
        echo "   aws lambda add-permission --function-name RunNewvelles --statement-id allow-eventbridge --action lambda:InvokeFunction --principal events.amazonaws.com --source-arn 'arn:aws:events:us-west-2:\$AWS_ACCOUNT_ID:rule/newvelles-event'"
    else
        echo "✅ EventBridge has permission to invoke Lambda (Statement: $EVENTBRIDGE_PERMISSION)"
    fi
fi

echo ""

# Check Lambda function configuration
echo "⚙️ Checking Lambda function configuration..."
LAMBDA_CONFIG=$(aws lambda get-function-configuration --function-name RunNewvelles 2>/dev/null || echo "")

if [ -z "$LAMBDA_CONFIG" ]; then
    echo "❌ Lambda function 'RunNewvelles' not found"
else
    echo "✅ Lambda function found"
    echo "$LAMBDA_CONFIG" | jq '{Memory: .MemorySize, Timeout: .Timeout, Storage: .EphemeralStorage.Size, Runtime: .PackageType}'
fi

echo ""

# Summary
echo "📊 Configuration Summary"
echo "========================"

RULE_STATE=$(echo "$RULE_INFO" | jq -r '.State // "UNKNOWN"')
SCHEDULE=$(echo "$RULE_INFO" | jq -r '.ScheduleExpression // "UNKNOWN"')
TARGET_COUNT=$(echo "$TARGETS" | jq '.Targets | length // 0')

echo "• EventBridge Rule: $RULE_STATE"
echo "• Schedule: $SCHEDULE"
echo "• Targets: $TARGET_COUNT"

if [ "$RULE_STATE" = "ENABLED" ] && [ "$TARGET_COUNT" -gt 0 ] && [ -n "$EVENTBRIDGE_PERMISSION" ] && [ "$EVENTBRIDGE_PERMISSION" != "null" ]; then
    echo ""
    echo "🎉 EventBridge configuration is complete and working!"
    echo ""
    echo "📅 Next execution times (approximate):"
    node -e "
        const now = new Date();
        const interval = 6 * 60 * 60 * 1000; // 6 hours in ms
        for (let i = 1; i <= 4; i++) {
            const next = new Date(Math.ceil(now.getTime() / interval) * interval + (i - 1) * interval);
            console.log(\`   \${i}. \${next.toISOString().replace('T', ' ').substr(0, 19)} UTC\`);
        }
    " 2>/dev/null || echo "   (Install Node.js to see next execution times)"
else
    echo ""
    echo "⚠️ EventBridge configuration incomplete"
    echo "   Run 'make prod-deploy' to fix all issues"
fi

echo ""
echo "✅ Configuration check complete!"
