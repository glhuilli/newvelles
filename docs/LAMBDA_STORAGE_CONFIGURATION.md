# Lambda Ephemeral Storage Configuration Guide

## 🎯 Overview

This document provides comprehensive guidance on configuring AWS Lambda ephemeral storage for the Newvelles application, specifically addressing the requirements for TensorFlow Hub model downloads.

## 📊 Storage Requirements Analysis

### Current Application Needs

| Component | Size | Purpose | Critical |
|-----------|------|---------|----------|
| **Universal Sentence Encoder** | 504.37MB | TensorFlow Hub model | ✅ Yes |
| **Model extraction overhead** | ~100MB | Temporary files during download | ✅ Yes |
| **Application runtime** | ~50MB | Log files, temp data | ⚠️ Medium |
| **OS overhead** | ~50MB | Lambda system files | ⚠️ Medium |
| **Safety margin** | ~300MB | Buffer for variations | 💡 Recommended |
| **Total Required** | **~1000MB** | **Minimum for stable operation** | ✅ **Critical** |

### Storage Configuration Matrix

| Environment | Memory | Ephemeral Storage | Model Loading | Status |
|-------------|---------|------------------|---------------|---------|
| **Production** | 2048MB | 1024MB | ✅ Working | ✅ Stable |
| **QA** | 2048MB | 1024MB | ✅ Working | ✅ Stable |
| **Testing** | 2048MB | 1024MB | ✅ Working | ✅ Stable |
| **Legacy (3.8)** | 2048MB | 512MB | ❌ Failing | 🚫 Deprecated |

## 🔧 Configuration Commands

### Quick Setup (Recommended)

```bash
# Apply ML-optimized configuration
./bin/lambda-config.sh optimize-ml RunNewvelles-qa

# Manual configuration
aws lambda update-function-configuration \
  --function-name RunNewvelles-qa \
  --memory-size 2048 \
  --timeout 900 \
  --ephemeral-storage Size=1024
```

### Individual Settings

```bash
# Update storage only
./bin/lambda-config.sh update-storage RunNewvelles-qa --storage 1024

# Update memory only  
./bin/lambda-config.sh update-memory RunNewvelles-qa --memory 2048

# Update timeout only
./bin/lambda-config.sh update-timeout RunNewvelles-qa --timeout 900
```

### Check Current Configuration

```bash
# Show current settings
./bin/lambda-config.sh show RunNewvelles-qa

# AWS CLI direct query
aws lambda get-function-configuration \
  --function-name RunNewvelles-qa \
  --query '{Memory:MemorySize,Storage:EphemeralStorage.Size,Timeout:Timeout}'
```

## 📈 Storage Scaling Guidelines

### Conservative Approach (Recommended)
```bash
# Current stable configuration
MEMORY_SIZE=2048      # MB - sufficient for TensorFlow
EPHEMERAL_STORAGE=1024 # MB - 2x model size for safety
TIMEOUT=900           # seconds - 15 minutes for ML processing
```

### Performance Optimization
```bash
# High-performance configuration
MEMORY_SIZE=3008      # MB - maximum performance
EPHEMERAL_STORAGE=2048 # MB - extra buffer for large models
TIMEOUT=900           # seconds - keep same timeout
```

### Cost Optimization
```bash
# Minimum viable configuration
MEMORY_SIZE=2048      # MB - minimum for TensorFlow
EPHEMERAL_STORAGE=1024 # MB - minimum for 504MB model
TIMEOUT=600           # seconds - reduce if processing is fast
```

## 💰 Cost Analysis

### Ephemeral Storage Pricing
- **Rate**: $0.0000000347 per GB-second
- **QA Usage**: 1024MB × 120 seconds = 122.88 GB-seconds per execution
- **Cost per execution**: $0.0000043 (less than half a cent)
- **Monthly cost** (100 executions): $0.43

### Cost Comparison
| Storage Size | Per Execution | Monthly (100x) | Annual |
|--------------|---------------|----------------|---------|
| 512MB (failing) | $0.0000021 | $0.21 | $2.52 |
| 1024MB (working) | $0.0000043 | $0.43 | $5.16 |
| 2048MB (optimized) | $0.0000085 | $0.85 | $10.20 |

**Conclusion**: The storage increase costs **$2.64/year** for a working system vs broken one.

## 🚨 Troubleshooting Storage Issues

### Common Error Patterns

#### 1. "No space left on device"
```
ResourceExhaustedError: /tmp/tfhub_cache/...tmp/variables/variables.data-00000-of-00001; No space left on device
```

**Solution**: Increase ephemeral storage
```bash
./bin/lambda-config.sh update-storage RunNewvelles-qa --storage 1024
```

#### 2. "Read-only file system: '/var/data'"
```
OSError: [Errno 30] Read-only file system: '/var/data'
```

**Solution**: Use `/tmp` directory or S3 direct uploads
```python
# Wrong - trying to write to /var/data
os.makedirs("/var/data/logs", exist_ok=True)

# Correct - use /tmp or skip local files
os.makedirs("/tmp/logs", exist_ok=True)  # or upload directly to S3
```

#### 3. Model download timeouts
```
INIT_REPORT Init Duration: 10007.67 ms Phase: init Status: timeout
```

**Solution**: Increase timeout or pre-download models
```bash
./bin/lambda-config.sh update-timeout RunNewvelles-qa --timeout 900
```

### Diagnostic Commands

```bash
# Check storage usage during execution
aws logs filter-log-events \
  --log-group-name '/aws/lambda/RunNewvelles-qa' \
  --filter-pattern 'size|space|memory' \
  --start-time $(date -d '1 hour ago' +%s)000

# Monitor function performance
aws logs filter-log-events \
  --log-group-name '/aws/lambda/RunNewvelles-qa' \
  --filter-pattern 'REPORT' \
  --start-time $(date -d '1 hour ago' +%s)000
```

## 🏗️ Infrastructure as Code

### Terraform Configuration
```hcl
resource "aws_lambda_function" "newvelles_qa" {
  function_name = "RunNewvelles-qa"
  package_type  = "Image"
  image_uri     = "$AWS_ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/newvelles-docker-lambda:py312-latest"
  
  # ML-optimized configuration
  memory_size = 2048
  timeout     = 900
  
  ephemeral_storage {
    size = 1024  # MB - Required for TensorFlow Hub models
  }
  
  environment {
    variables = {
      AWS_S3_BUCKET        = "newvelles-qa-bucket"
      AWS_S3_PUBLIC_BUCKET = "public-newvelles-qa-bucket"
    }
  }
}
```

### CloudFormation Template
```yaml
NewvellesQAFunction:
  Type: AWS::Lambda::Function
  Properties:
    FunctionName: RunNewvelles-qa
    PackageType: Image
    Code:
      ImageUri: $AWS_ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/newvelles-docker-lambda:py312-latest
    MemorySize: 2048
    Timeout: 900
    EphemeralStorage:
      Size: 1024  # Required for TensorFlow Hub models
    Environment:
      Variables:
        AWS_S3_BUCKET: newvelles-qa-bucket
        AWS_S3_PUBLIC_BUCKET: public-newvelles-qa-bucket
```

## 📋 Monitoring and Maintenance

### Key Metrics to Monitor

```bash
# Storage utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=RunNewvelles-qa \
  --start-time $(date -d '24 hours ago' -u +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Average,Maximum

# Memory utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name MemoryUtilization \
  --dimensions Name=FunctionName,Value=RunNewvelles-qa \
  --start-time $(date -d '24 hours ago' -u +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Average,Maximum
```

### Automated Monitoring Script

```bash
#!/bin/bash
# Monitor Lambda storage health
FUNCTION_NAME="RunNewvelles-qa"

# Check recent errors
ERRORS=$(aws logs filter-log-events \
  --log-group-name "/aws/lambda/${FUNCTION_NAME}" \
  --filter-pattern "No space left on device" \
  --start-time $(($(date +%s) - 3600))000 \
  --query 'length(events)')

if [ "$ERRORS" -gt 0 ]; then
  echo "⚠️ Storage errors detected in ${FUNCTION_NAME}"
  echo "Consider increasing ephemeral storage"
  # Send alert to monitoring system
fi
```

## 🔄 Migration Procedures

### Upgrading Storage

```bash
# 1. Check current configuration
./bin/lambda-config.sh show RunNewvelles-qa

# 2. Test in QA first
./bin/lambda-config.sh update-storage RunNewvelles-qa --storage 2048

# 3. Verify functionality
make qa-invoke

# 4. Apply to production if successful
./bin/lambda-config.sh update-storage RunNewvelles --storage 2048
```

### Rollback Plan

```bash
# If issues occur, rollback to previous working configuration
aws lambda update-function-configuration \
  --function-name RunNewvelles-qa \
  --memory-size 2048 \
  --timeout 900 \
  --ephemeral-storage Size=1024
```

## 📚 References

- [AWS Lambda Ephemeral Storage Documentation](https://docs.aws.amazon.com/lambda/latest/dg/configuration-ephemeral-storage.html)
- [TensorFlow Hub Caching Guide](https://www.tensorflow.org/hub/caching)
- [Lambda Pricing Calculator](https://aws.amazon.com/lambda/pricing/)

---

**Last Updated**: August 18, 2025  
**Version**: 1.0  
**Status**: ✅ Production Ready
