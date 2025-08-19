# Production Rollback Guide

## 🎯 Overview

This guide explains how to safely roll back the production Lambda function to a previous Docker image version when issues arise with new deployments.

## 🚨 When to Use Rollback

### **Immediate Rollback Scenarios:**
- **Algorithm Performance Issues**: New ML model performs worse than previous version
- **Critical Bugs**: Function errors, crashes, or incorrect outputs
- **Data Quality Problems**: RSS parsing failures, missing data, or corrupted outputs
- **Performance Degradation**: Significant increase in execution time or memory usage
- **S3 Upload Failures**: Issues with file generation or bucket uploads

### **Consider Rollback When:**
- Production file sizes suddenly change unexpectedly
- CloudWatch logs show new error patterns
- EventBridge scheduling becomes unreliable
- Manual invocations fail consistently

## 🔄 Rollback Methods

### **Method 1: Interactive Rollback (Recommended)**
```bash
make rollback-prod
```

**Features:**
- ✅ Shows current production image
- ✅ Lists available images with timestamps and sizes
- ✅ Interactive selection with numbered options
- ✅ Safety confirmations at each step
- ✅ Automatic EventBridge pause/resume
- ✅ Test invocation after rollback
- ✅ Complete safety checks

### **Method 2: List Available Images**
```bash
make list-prod-images
```

**Use this to:**
- See available rollback options
- Check image timestamps and sizes
- Plan rollback strategy before executing

## 📋 Step-by-Step Rollback Process

### **1. Assess the Situation**
```bash
# Check current production status
aws lambda get-function --function-name RunNewvelles --query 'Code.ImageUri'

# Check recent logs for errors
aws logs tail /aws/lambda/RunNewvelles --since 1h

# Check S3 output
aws s3 ls s3://public-newvelles-data-bucket/ --human-readable
```

### **2. Identify Target Version**
```bash
# List available versions
make list-prod-images

# Common rollback targets:
# - py312-nocache-20250817-233736 (last known stable before latest changes)
# - py312-s3only-20250817-233534 (S3-only deployment)
# - py312-1024mb-20250817-232154 (1GB memory optimization)
```

### **3. Execute Rollback**
```bash
make rollback-prod
```

**Follow the prompts:**
1. **Review current image**: Confirm what's currently deployed
2. **Select target image**: Choose from numbered list (1-25)
3. **Confirm selection**: Verify the image tag and timestamp
4. **Final confirmation**: Type `yes` to proceed

### **4. Verify Rollback Success**
```bash
# Check Lambda configuration
aws lambda get-function --function-name RunNewvelles

# Monitor logs
aws logs tail /aws/lambda/RunNewvelles --follow

# Verify S3 output after next execution
aws s3 ls s3://public-newvelles-data-bucket/ --human-readable
```

## 🔒 Safety Features

### **Automatic Safety Measures:**
- **EventBridge Pause**: Stops automatic executions during rollback
- **Wait Period**: 15-second grace period for running executions
- **Test Invocation**: Validates rollback with test run
- **Error Recovery**: Auto-resumes EventBridge if rollback fails
- **Confirmation Gates**: Multiple confirmation prompts

### **Rollback Process Flow:**
```
1. Show current production image
2. List available rollback targets
3. User selects target image
4. Pause EventBridge scheduling
5. Wait for running executions
6. Update Lambda function code
7. Wait for function to be ready
8. Test rollback with invocation
9. Resume EventBridge scheduling
10. Show success summary
```

## 📊 Understanding Image Tags

### **Tag Naming Convention:**
- `py312-qa-YYYYMMDD-HHMMSS`: QA builds with Python 3.12
- `py312-nocache-YYYYMMDD-HHMMSS`: No TensorFlow cache optimization
- `py312-s3only-YYYYMMDD-HHMMSS`: S3-only deployment version
- `py312-1024mb-YYYYMMDD-HHMMSS`: 1GB ephemeral storage
- `v7`, `v6`, etc.: Legacy versions (Python 3.8)

### **Image Size Guide:**
- **~1983 MB**: Python 3.12 with full ML stack (current)
- **~681 MB**: Python 3.8 legacy versions
- **~630 MB**: Very old versions

### **Recommended Rollback Targets:**

#### **For Algorithm Issues:**
- `py312-nocache-20250817-233736`: Last stable before recent changes
- `py312-s3only-20250817-233534`: Proven S3-only deployment

#### **For Performance Issues:**
- `py312-1024mb-20250817-232154`: Optimized memory configuration
- `py312-final-20250817-204444`: Stable final build

#### **For Critical Issues:**
- `v7`: Last known Python 3.8 stable (fallback option)

## ⚠️ Important Considerations

### **Before Rolling Back:**
1. **Document the issue**: Save logs, error messages, and symptoms
2. **Check EventBridge status**: Ensure it's running normally
3. **Verify S3 bucket health**: Confirm buckets are accessible
4. **Consider impact**: Understand what functionality will change

### **After Rolling Back:**
1. **Monitor closely**: Watch logs for the next few executions
2. **Verify S3 outputs**: Confirm files are being generated correctly
3. **Check file sizes**: Ensure output matches expected patterns
4. **Plan forward fix**: Identify root cause and plan proper fix

### **Rollback Limitations:**
- **No data recovery**: Rollback doesn't restore previous S3 data
- **Configuration**: Lambda memory/timeout settings remain current
- **EventBridge**: Schedule remains at 6-hour intervals
- **Environment**: Still uses current environment variables

## 🚨 Emergency Procedures

### **If Rollback Fails:**
```bash
# Manual Lambda update
aws lambda update-function-code \
  --function-name RunNewvelles \
  --image-uri $AWS_ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/newvelles-docker-lambda:py312-nocache-20250817-233736

# Manual EventBridge resume
aws events enable-rule --name newvelles-event

# Check status
make check-eventbridge
```

### **If Production is Completely Broken:**
```bash
# Pause EventBridge immediately
make pause-eventbridge

# Roll back to last known good version
make rollback-prod
# Select a proven stable image like py312-nocache-20250817-233736

# If interactive rollback fails, use manual commands above
```

### **Communication:**
- Document rollback in deployment logs
- Notify team of rollback and reasons
- Plan follow-up investigation and fixes

## 📈 Best Practices

### **Rollback Strategy:**
1. **Test in QA first**: Always test fixes in QA before production
2. **Keep recent builds**: Don't delete recent ECR images
3. **Document changes**: Tag images with meaningful descriptions
4. **Monitor actively**: Watch production for first few hours after deployment
5. **Have rollback plan**: Know which version to roll back to before deploying

### **Image Management:**
- Keep at least 5 recent stable images
- Document known good versions
- Test rollback procedure in QA environment
- Regular cleanup of very old images (>30 days)

### **Monitoring:**
- Set up CloudWatch alarms for Lambda errors
- Monitor S3 bucket file sizes and upload frequency
- Track EventBridge execution success rates
- Set up alerts for unusual RSS processing patterns

---

**Last Updated**: August 18, 2025  
**Version**: 1.0  
**Status**: ✅ Production Ready
