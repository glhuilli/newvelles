# EventBridge Scheduling Configuration

## 🎯 Overview

This document describes the EventBridge (CloudWatch Events) configuration for automatic Newvelles execution in the production environment.

## ⏰ Current Configuration

### **Production Schedule**
- **Rule Name**: `newvelles-event`
- **Schedule**: Every 6 hours (`rate(6 hours)`)
- **Target**: `RunNewvelles` Lambda function
- **State**: ENABLED
- **Environment**: Production only (QA uses manual invocation)

### **Execution Times**
With a 6-hour schedule, the function runs approximately:
- 00:00 UTC (4:00 PM PST / 5:00 PM PDT)
- 06:00 UTC (10:00 PM PST / 11:00 PM PDT)  
- 12:00 UTC (4:00 AM PST / 5:00 AM PDT)
- 18:00 UTC (10:00 AM PST / 11:00 AM PDT)

## 🔧 Automatic Configuration

### **During Production Deployment**

The `make prod-deploy` command automatically:

1. **Creates/Updates EventBridge Rule**:
   ```bash
   aws events put-rule \
       --name newvelles-event \
       --schedule-expression "rate(6 hours)" \
       --description "Trigger newvelles computation every 6 hours" \
       --state ENABLED
   ```

2. **Sets Lambda Target**:
   ```bash
   aws events put-targets \
       --rule newvelles-event \
       --targets "Id"="1","Arn"="arn:aws:lambda:us-west-2:617641631577:function:RunNewvelles"
   ```

3. **Grants EventBridge Permission**:
   ```bash
   aws lambda add-permission \
       --function-name RunNewvelles \
       --statement-id allow-eventbridge \
       --action lambda:InvokeFunction \
       --principal events.amazonaws.com \
       --source-arn "arn:aws:events:us-west-2:617641631577:rule/newvelles-event"
   ```

## 📊 Monitoring & Management

### **Quick Management Commands**
```bash
# Check status and next execution times
make check-eventbridge

# Emergency pause (stops all automatic executions)
make pause-eventbridge

# Resume scheduling
make resume-eventbridge

# Get detailed status with management options
./bin/manage-eventbridge.sh status
./bin/manage-eventbridge.sh restart  # Safe restart with 30s pause
```

### **Check Current Configuration**
```bash
# View the EventBridge rule
aws events describe-rule --name newvelles-event

# List targets
aws events list-targets-by-rule --rule newvelles-event

# Check Lambda permissions
aws lambda get-policy --function-name RunNewvelles
```

### **Modify Schedule**
```bash
# Change to 4-hour execution
aws events put-rule \
    --name newvelles-event \
    --schedule-expression "rate(4 hours)" \
    --description "Trigger newvelles computation every 4 hours" \
    --state ENABLED

# Change to daily at 6 AM UTC
aws events put-rule \
    --name newvelles-event \
    --schedule-expression "cron(0 6 * * ? *)" \
    --description "Trigger newvelles computation daily at 6 AM UTC" \
    --state ENABLED
```

### **Enable/Disable Scheduling**
```bash
# Disable automatic execution
aws events disable-rule --name newvelles-event

# Re-enable automatic execution  
aws events enable-rule --name newvelles-event

# Check rule state
aws events describe-rule --name newvelles-event --query 'State'
```

## 🚨 Troubleshooting

### **Common Issues**

1. **EventBridge Not Triggering**:
   ```bash
   # Check if rule is enabled
   aws events describe-rule --name newvelles-event --query 'State'
   
   # Verify Lambda permissions
   aws lambda get-policy --function-name RunNewvelles | grep events.amazonaws.com
   ```

2. **Lambda Function Not Found**:
   ```bash
   # Verify Lambda function exists
   aws lambda get-function --function-name RunNewvelles
   
   # Update target if function name changed
   aws events put-targets \
       --rule newvelles-event \
       --targets "Id"="1","Arn"="arn:aws:lambda:us-west-2:617641631577:function:RunNewvelles"
   ```

3. **Permission Denied**:
   ```bash
   # Re-add EventBridge permission
   aws lambda add-permission \
       --function-name RunNewvelles \
       --statement-id allow-eventbridge \
       --action lambda:InvokeFunction \
       --principal events.amazonaws.com \
       --source-arn "arn:aws:events:us-west-2:617641631577:rule/newvelles-event"
   ```

### **Manual Testing**
```bash
# Test EventBridge rule manually
aws events put-events \
    --entries Source=test,DetailType="Manual Test",Detail="{}"

# Check CloudWatch logs for execution
aws logs tail /aws/lambda/RunNewvelles --follow
```

## 📈 CloudWatch Metrics

### **Key Metrics to Monitor**
- **Rule Executions**: `AWS/Events` → `InvocationsCount`
- **Lambda Duration**: `AWS/Lambda` → `Duration`  
- **Lambda Errors**: `AWS/Lambda` → `Errors`
- **Lambda Success Rate**: `AWS/Lambda` → `Invocations` vs `Errors`

### **CloudWatch Dashboard Query**
```json
{
    "metrics": [
        [ "AWS/Events", "InvocationsCount", "RuleName", "newvelles-event" ],
        [ "AWS/Lambda", "Duration", "FunctionName", "RunNewvelles" ],
        [ "AWS/Lambda", "Errors", "FunctionName", "RunNewvelles" ]
    ],
    "period": 3600,
    "stat": "Sum",
    "region": "us-west-2",
    "title": "Newvelles Execution Metrics"
}
```

## 💰 Cost Optimization

### **Current Costs** (Approximate)
- **EventBridge Rule**: $1/month per million events (~$0.004/month for 4 daily executions)
- **Lambda Execution**: Based on duration and memory (main cost)
- **Total EventBridge Cost**: <$0.01/month

### **Cost Reduction Options**
1. **Reduce Frequency**: Change from 6 hours to 8 or 12 hours
2. **Off-Peak Execution**: Use cron expression for specific times
3. **Conditional Execution**: Add logic to skip execution during low-traffic periods

## 🔄 Migration & Backup

### **Backup Current Configuration**
```bash
# Export rule configuration
aws events describe-rule --name newvelles-event > newvelles-event-backup.json

# Export targets
aws events list-targets-by-rule --rule newvelles-event > newvelles-targets-backup.json
```

### **Restore Configuration**
```bash
# Restore from backup (adjust as needed)
aws events put-rule \
    --name newvelles-event \
    --schedule-expression "rate(6 hours)" \
    --description "Trigger newvelles computation every 6 hours" \
    --state ENABLED
```

---

**Last Updated**: August 18, 2025  
**Version**: 1.0  
**Status**: ✅ Production Active
