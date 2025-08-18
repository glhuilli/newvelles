# 🏗️ Multi-Environment S3 Bucket Strategy

## 📋 **How S3 Bucket Selection Works**

Your Lambda function determines which S3 buckets to use through this **priority hierarchy**:

### **🔍 Bucket Selection Logic:**
```python
# From newvelles/feed/log.py lines 20-26
_S3_BUCKET = os.getenv(
    "AWS_S3_BUCKET", 
    CONFIG.get("S3", "bucket", fallback="newvelles-data-bucket")
)
_S3_PUBLIC_BUCKET = os.getenv(
    "AWS_S3_PUBLIC_BUCKET",
    CONFIG.get("S3", "public_bucket", fallback="public-newvelles-data-bucket"),
)
```

**Priority Order:**
1. **Environment Variables** (highest priority)
2. **Config file** (`newvelles/config/newvelles.ini`)
3. **Hardcoded fallbacks** (lowest priority)

---

## 🌍 **Recommended 3-Environment Setup**

### **1. 🏭 Production Environment**
- **Purpose:** Live production data
- **Configuration:** Uses config file defaults (no env vars set)
- **Buckets:** 
  - `newvelles-data-bucket` (private)
  - `public-newvelles-data-bucket` (public)

### **2. 🧪 Testing Environment** 
- **Purpose:** Integration testing (current setup)
- **Configuration:** Environment variables override
- **Buckets:**
  - `newvelles-test-bucket` (private)
  - `public-newvelles-test-bucket` (public)

### **3. 🛡️ QA/Shadow Environment**
- **Purpose:** Production-like validation before release
- **Configuration:** Environment variables override
- **Buckets:**
  - `newvelles-qa-bucket` (private)
  - `public-newvelles-qa-bucket` (public)

---

## 🚀 **Implementation Strategy**

### **Step 1: Create QA Buckets**
```bash
# Create QA S3 buckets
aws s3 mb s3://newvelles-qa-bucket --region us-west-2
aws s3 mb s3://public-newvelles-qa-bucket --region us-west-2

# Configure public bucket for web access (if needed)
aws s3api put-bucket-policy --bucket public-newvelles-qa-bucket --policy '{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadGetObject",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::public-newvelles-qa-bucket/*"
  }]
}'
```

### **Step 2: Configure Lambda Environment Variables**

#### **For Testing Lambda:**
```bash
# Environment variables for testing
AWS_S3_BUCKET=newvelles-test-bucket
AWS_S3_PUBLIC_BUCKET=public-newvelles-test-bucket
```

#### **For QA Lambda:**
```bash
# Environment variables for QA
AWS_S3_BUCKET=newvelles-qa-bucket
AWS_S3_PUBLIC_BUCKET=public-newvelles-qa-bucket
```

#### **For Production Lambda:**
```bash
# No environment variables needed - uses config file defaults
# newvelles-data-bucket
# public-newvelles-data-bucket
```

---

## 🐳 **Docker Image Deployment Strategy**

### **Same Image, Different Environments**

Your **single Docker image** can be deployed to different environments by setting different environment variables:

```bash
# QA Environment Deployment
aws lambda update-function-configuration \
  --function-name RunNewvelles-qa \
  --environment Variables='{
    "AWS_S3_BUCKET":"newvelles-qa-bucket",
    "AWS_S3_PUBLIC_BUCKET":"public-newvelles-qa-bucket"
  }' \
  --image-uri 617641631577.dkr.ecr.us-west-2.amazonaws.com/newvelles-docker-lambda:v2-py312-20250817-181418

# Production Environment Deployment  
aws lambda update-function-configuration \
  --function-name RunNewvelles \
  --environment Variables='{}' \
  --image-uri 617641631577.dkr.ecr.us-west-2.amazonaws.com/newvelles-docker-lambda:v2-py312-20250817-181418
```

---

## 📋 **Environment Configuration Matrix**

| Environment | Lambda Function | Private Bucket | Public Bucket | Python Version | Storage | Image URI | Env Vars |
|-------------|----------------|----------------|---------------|----------------|---------|-----------|----------|
| **Production** | `RunNewvelles` | `newvelles-data-bucket` | `public-newvelles-data-bucket` | 3.12.11 | 1024MB | `617641631577.dkr.ecr.us-west-2.amazonaws.com/newvelles-docker-lambda:py312-nocache-20250817-233736` | None (uses config)<br/>**84 RSS sources** |
| **QA/Shadow** | `RunNewvelles-qa` | `newvelles-qa-bucket` | `public-newvelles-qa-bucket` | 3.12.11 | 1024MB | Same image | `AWS_S3_BUCKET=newvelles-qa-bucket`<br/>`AWS_S3_PUBLIC_BUCKET=public-newvelles-qa-bucket`<br/>**13 RSS sources** |
| **Testing** | `RunNewvelles-test` | `newvelles-test-bucket` | `public-newvelles-test-bucket` | 3.12.11 | 1024MB | Same image | `AWS_S3_BUCKET=newvelles-test-bucket`<br/>`AWS_S3_PUBLIC_BUCKET=public-newvelles-test-bucket`<br/>**13 RSS sources** |

---

## 🔄 **Recommended Deployment Workflow**

### **1. Development & Testing**
```bash
# Local testing with test buckets
make test-local-complete
```

### **2. Deploy to QA Environment**
```bash
# Use improved QA workflow (builds + deploys + tests)
make qa-full-test

# Or manual QA deployment
./bin/deploy-to-environment.sh qa py312-final-20250817-204444 617641631577
```

### **3. Validate QA Results**
```bash
# Check QA bucket contents
make validate-s3 BUCKET=newvelles-qa-bucket
make validate-s3 BUCKET=public-newvelles-qa-bucket

# Compare QA vs current production data
aws s3 sync s3://public-newvelles-qa-bucket s3://qa-validation-bucket --dryrun
```

### **4. Deploy to Production** (after QA validation)
```bash
# ✅ IMPROVED: Production deployment with ML-optimized configuration
make prod-deploy

# Or manual production deployment (applies same config as QA)
./bin/deploy-to-environment.sh prod py312-final-20250817-204444 617641631577
```

**🎯 What `prod-deploy` now includes:**
- **🤖 ML-Optimized Configuration**: 2048MB memory, 900s timeout, 1024MB storage
- **🐍 Python 3.12**: Same runtime as QA
- **📦 TensorFlow Support**: Sufficient storage for 504MB model  
- **⏰ EventBridge Scheduling**: Automatic execution every 6 hours
- **⏸️ Safe Deployment**: Pauses EventBridge during deployment to prevent conflicts
- **🧪 Production Testing**: Automatic invocation after deployment
- **📊 S3 Verification**: Confirms bucket updates after test run
- **🔧 Complete Verification**: End-to-end deployment validation
- **🔄 Auto-Resume**: Automatically resumes scheduling after successful deployment

---

## 🛠️ **Local Testing Configuration**

### **Test Against Specific Environment:**

```bash
# Test against QA buckets locally
export AWS_S3_BUCKET=newvelles-qa-bucket
export AWS_S3_PUBLIC_BUCKET=public-newvelles-qa-bucket
make test-lambda-docker

# Test against production buckets locally (CAREFUL!)
unset AWS_S3_BUCKET
unset AWS_S3_PUBLIC_BUCKET
make test-lambda-docker
```

### **Environment-Specific .env Files:**

Create multiple environment files:
- `.env.test` - Testing environment
- `.env.qa` - QA environment  
- `.env.prod` - Production environment (minimal)

---

## 🎯 **Key Benefits**

1. **✅ Same Docker Image:** No code changes between environments
2. **✅ Environment Isolation:** Each environment has separate data
3. **✅ Safe Testing:** QA validates before production
4. **✅ Easy Rollback:** Environment variables are easily changed
5. **✅ Cost Effective:** Single image, multiple deployments

---

## 🚨 **Safety Considerations**

1. **Bucket Permissions:** Ensure each environment can only access its buckets
2. **Environment Variables:** Double-check variables before deployment
3. **Data Separation:** Never mix test/QA data with production
4. **Monitoring:** Set up CloudWatch alerts for each environment
5. **Access Control:** Use IAM roles specific to each environment

---

## 🎯 **Quick Reference Commands**

### **Deploy to Environments:**
```bash
# Deploy to QA for testing
make deploy-to-env ENV=qa TAG=v2-py312-20250817-181418

# Deploy to Production (after QA validation)  
make deploy-to-env ENV=prod TAG=v2-py312-20250817-181418

# Deploy to Testing environment
make deploy-to-env ENV=test TAG=v2-py312-20250817-181418
```

### **Test Lambda Functions:**
```bash
# Test Production Lambda
aws lambda invoke --function-name RunNewvelles response.json

# Test QA Lambda
aws lambda invoke --function-name RunNewvelles-qa response.json

# Test Testing Lambda
aws lambda invoke --function-name RunNewvelles-test response.json
```

### **Monitor Logs:**
```bash
# Production logs
aws logs tail /aws/lambda/RunNewvelles --follow

# QA logs  
aws logs tail /aws/lambda/RunNewvelles-qa --follow

# Testing logs
aws logs tail /aws/lambda/RunNewvelles-test --follow
```

This strategy gives you complete control over your deployment pipeline while maintaining safety and isolation between environments! 🛡️
