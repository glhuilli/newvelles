#!/bin/bash
# EventBridge Management Script
# Pause, resume, or check EventBridge scheduling for production

set -e

COMMAND="$1"

if [ -z "$COMMAND" ]; then
    echo "EventBridge Management Script"
    echo "============================="
    echo ""
    echo "Usage: $0 [pause|resume|status|restart]"
    echo ""
    echo "Commands:"
    echo "  pause    - Disable EventBridge scheduling"
    echo "  resume   - Enable EventBridge scheduling"  
    echo "  status   - Show current EventBridge status"
    echo "  restart  - Pause for 30s then resume (safe restart)"
    echo ""
    echo "Examples:"
    echo "  $0 pause     # Stop automatic executions"
    echo "  $0 resume    # Start automatic executions"
    echo "  $0 status    # Check current state"
    echo "  $0 restart   # Safe restart with pause"
    exit 1
fi

echo "🔧 EventBridge Management"
echo "========================="
echo ""

case "$COMMAND" in
    "pause"|"stop"|"disable")
        echo "⏸️ Pausing EventBridge scheduling..."
        
        # Check current state
        CURRENT_STATE=$(aws events describe-rule --name newvelles-event --query 'State' --output text 2>/dev/null || echo "RULE_NOT_FOUND")
        
        if [ "$CURRENT_STATE" = "RULE_NOT_FOUND" ]; then
            echo "❌ EventBridge rule 'newvelles-event' not found"
            exit 1
        elif [ "$CURRENT_STATE" = "DISABLED" ]; then
            echo "ℹ️ EventBridge is already disabled"
        else
            aws events disable-rule --name newvelles-event
            if [ $? -eq 0 ]; then
                echo "✅ EventBridge scheduling paused"
                echo "   Automatic executions stopped"
            else
                echo "❌ Failed to pause EventBridge"
                exit 1
            fi
        fi
        ;;
        
    "resume"|"start"|"enable")
        echo "▶️ Resuming EventBridge scheduling..."
        
        # Check current state
        CURRENT_STATE=$(aws events describe-rule --name newvelles-event --query 'State' --output text 2>/dev/null || echo "RULE_NOT_FOUND")
        
        if [ "$CURRENT_STATE" = "RULE_NOT_FOUND" ]; then
            echo "❌ EventBridge rule 'newvelles-event' not found"
            echo "💡 Run 'make prod-deploy' to create the rule"
            exit 1
        elif [ "$CURRENT_STATE" = "ENABLED" ]; then
            echo "ℹ️ EventBridge is already enabled"
        else
            aws events enable-rule --name newvelles-event
            if [ $? -eq 0 ]; then
                echo "✅ EventBridge scheduling resumed"
                echo "   Automatic executions will continue"
            else
                echo "❌ Failed to resume EventBridge"
                exit 1
            fi
        fi
        ;;
        
    "status"|"check"|"info")
        echo "📊 EventBridge Status"
        echo "===================="
        
        # Get rule information
        RULE_INFO=$(aws events describe-rule --name newvelles-event 2>/dev/null || echo "")
        
        if [ -z "$RULE_INFO" ]; then
            echo "❌ EventBridge rule 'newvelles-event' not found"
            echo ""
            echo "💡 To create the rule, run: make prod-deploy"
            exit 1
        fi
        
        echo "$RULE_INFO" | jq '{Name: .Name, Schedule: .ScheduleExpression, State: .State, Description: .Description}'
        
        echo ""
        echo "🎯 Targets:"
        aws events list-targets-by-rule --rule newvelles-event | jq '.Targets[] | {Id: .Id, Function: .Arn | split(":") | last}'
        
        # Show next execution times if enabled
        STATE=$(echo "$RULE_INFO" | jq -r '.State')
        if [ "$STATE" = "ENABLED" ]; then
            echo ""
            echo "📅 Next execution times (approximate):"
            node -e "
                const now = new Date();
                const interval = 6 * 60 * 60 * 1000; // 6 hours in ms
                for (let i = 1; i <= 3; i++) {
                    const next = new Date(Math.ceil(now.getTime() / interval) * interval + (i - 1) * interval);
                    console.log(\`   \${i}. \${next.toISOString().replace('T', ' ').substr(0, 19)} UTC\`);
                }
            " 2>/dev/null || echo "   (Install Node.js to see execution times)"
        else
            echo ""
            echo "⏸️ EventBridge is DISABLED - no automatic executions"
        fi
        ;;
        
    "restart"|"safe-restart")
        echo "🔄 Safe EventBridge Restart"
        echo "==========================="
        
        # Check if rule exists
        CURRENT_STATE=$(aws events describe-rule --name newvelles-event --query 'State' --output text 2>/dev/null || echo "RULE_NOT_FOUND")
        
        if [ "$CURRENT_STATE" = "RULE_NOT_FOUND" ]; then
            echo "❌ EventBridge rule 'newvelles-event' not found"
            exit 1
        fi
        
        # Pause if currently enabled
        if [ "$CURRENT_STATE" = "ENABLED" ]; then
            echo "⏸️ Pausing EventBridge..."
            aws events disable-rule --name newvelles-event
            echo "✅ EventBridge paused"
        else
            echo "ℹ️ EventBridge already paused"
        fi
        
        # Wait for any running executions
        echo "⏳ Waiting 30 seconds for any running executions to complete..."
        sleep 30
        
        # Resume
        echo "▶️ Resuming EventBridge..."
        aws events enable-rule --name newvelles-event
        
        if [ $? -eq 0 ]; then
            echo "✅ EventBridge restart completed"
            echo "   Scheduling resumed with 6-hour interval"
        else
            echo "❌ Failed to resume EventBridge"
            exit 1
        fi
        ;;
        
    *)
        echo "❌ Unknown command: $COMMAND"
        echo ""
        echo "Valid commands: pause, resume, status, restart"
        echo "Run '$0' without arguments for help"
        exit 1
        ;;
esac

echo ""
echo "✅ Operation completed!"
