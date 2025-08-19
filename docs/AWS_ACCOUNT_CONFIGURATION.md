# AWS Account Configuration Guide

## 🎯 Overview

This guide explains how to configure your AWS account ID for the Newvelles project. All scripts and deployment commands now use the `$AWS_ACCOUNT_ID` environment variable instead of hardcoded account IDs for better security and flexibility.

## 🔧 Setting Up AWS_ACCOUNT_ID

### **Method 1: Environment Variable (Recommended)**

#### **For Current Session:**
```bash
export AWS_ACCOUNT_ID=your-12-digit-account-id
```

#### **For Permanent Setup (add to your shell profile):**
```bash
# Add to ~/.bashrc, ~/.zshrc, or equivalent
echo 'export AWS_ACCOUNT_ID=your-12-digit-account-id' >> ~/.zshrc
source ~/.zshrc
```

#### **Verify Setup:**
```bash
echo $AWS_ACCOUNT_ID
# Should output: your-12-digit-account-id
```

### **Method 2: Find Your AWS Account ID**

If you don't know your AWS account ID:

#### **Using AWS CLI:**
```bash
aws sts get-caller-identity --query Account --output text
```

#### **Using AWS Console:**
1. Log into AWS Console
2. Click your username in top-right corner
3. Your account ID is displayed in the dropdown

#### **From ECR Repository:**
```bash
aws ecr describe-repositories --repository-names newvelles-docker-lambda --query 'repositories[0].registryId' --output text
```

## 📋 Scripts That Now Use $AWS_ACCOUNT_ID

### **Updated Scripts:**
- ✅ `bin/rollback-production.sh` - Production rollback system
- ✅ `bin/qa-deploy.sh` - QA deployment
- ✅ `bin/docker-py312.sh` - Docker build script
- ✅ `bin/deploy-to-environment.sh` - Multi-environment deployment
- ✅ `bin/check-eventbridge.sh` - EventBridge configuration checker
- ✅ `bin/create-qa-lambda-role.sh` - QA role creation
- ✅ `Makefile` - All Docker and deployment targets

### **Updated Documentation:**
- ✅ `docs/MULTI_ENVIRONMENT_STRATEGY.md`
- ✅ `docs/PRODUCTION_ROLLBACK_GUIDE.md`
- ✅ `docs/EVENTBRIDGE_SCHEDULING.md`
- ✅ `docs/PYTHON_312_UPGRADE_GUIDE.md`
- ✅ `docs/LAMBDA_STORAGE_CONFIGURATION.md`
- ✅ `docs/LAMBDA_DEPLOYMENT_SUMMARY.md`

## 🚀 Usage Examples

### **With Environment Variable Set:**
```bash
export AWS_ACCOUNT_ID=617641631577

# All commands now work without specifying account ID
make rollback-prod
make docker-deploy
make prod-deploy
./bin/deploy-to-environment.sh qa py312-latest
```

### **Without Environment Variable (required parameter):**
```bash
# Scripts require AWS_ACCOUNT_ID to be set
export AWS_ACCOUNT_ID=your-account-id

# Or specify explicitly as parameter where supported
make docker-deploy ACCOUNT=123456789012
./bin/deploy-to-environment.sh qa py312-latest 123456789012
```

## 🔒 Security Benefits

### **Before (Hardcoded):**
```bash
# ❌ Account ID exposed in all scripts
ACCOUNT_ID="617641631577"
ECR_URI="617641631577.dkr.ecr.us-west-2.amazonaws.com/..."
```

### **After (Environment Variable Required):**
```bash
# ✅ Account ID from environment - required, no fallback
ACCOUNT_ID="$AWS_ACCOUNT_ID"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com/..."
```

### **Advantages:**
- **🔐 Enhanced Security**: No hardcoded credentials, no fallback account exposure
- **🛡️ Explicit Configuration**: Forces explicit account setup, preventing accidental deployments
- **🔄 Flexibility**: Easy to switch between AWS accounts
- **👥 Team Friendly**: Each developer must configure their own account
- **🧪 Testing**: Prevents accidental use of wrong accounts
- **📦 CI/CD Ready**: Environment variables work well in automated systems

## 🛠️ Makefile Integration

### **Enhanced Makefile Targets:**
```bash
# Docker operations with account detection
make docker-deploy                    # Uses $AWS_ACCOUNT_ID or prompts
make docker-deploy ACCOUNT=123456789012  # Explicit account override

# Environment deployments
make deploy-to-env ENV=qa TAG=py312-latest  # Uses $AWS_ACCOUNT_ID
make prod-deploy                       # Uses $AWS_ACCOUNT_ID

# Rollback operations  
make rollback-prod                     # Uses $AWS_ACCOUNT_ID
make list-prod-images                  # Uses $AWS_ACCOUNT_ID
```

### **Error Handling:**
```bash
# Scripts require environment variable to be set
❌ Error: AWS_ACCOUNT_ID environment variable is required
   Please set it with: export AWS_ACCOUNT_ID=your-account-id
   Find your account ID: aws sts get-caller-identity --query Account --output text
```

## 📝 Configuration Examples

### **Development Setup:**
```bash
# ~/.zshrc or ~/.bashrc
export AWS_ACCOUNT_ID=617641631577
export AWS_DEFAULT_REGION=us-west-2
export AWS_PROFILE=newvelles-dev
```

### **CI/CD Pipeline:**
```yaml
# GitHub Actions / GitLab CI
env:
  AWS_ACCOUNT_ID: ${{ secrets.AWS_ACCOUNT_ID }}
  AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
  AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

### **Docker Environment:**
```bash
# For containerized builds
docker run -e AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID \
           -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
           -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
           your-build-image
```

## 🔍 Verification Commands

### **Check Current Configuration:**
```bash
# Verify environment variable
echo "AWS Account ID: $AWS_ACCOUNT_ID"

# Test with a script
./bin/check-eventbridge.sh

# Verify ECR access
aws ecr describe-repositories --repository-names newvelles-docker-lambda
```

### **Test Deployment Flow:**
```bash
# Complete test without actual deployment
make list-prod-images    # Should list your ECR images
make qa-build           # Should build and tag correctly  
make qa-deploy          # Should push to your ECR
```

## ⚠️ Important Notes

### **Breaking Change Notice:**
- **⚠️ BREAKING**: Scripts now require `$AWS_ACCOUNT_ID` to be explicitly set
- **No fallback**: Removed default account ID for enhanced security
- **Migration needed**: Existing users must set `export AWS_ACCOUNT_ID=your-account-id`

### **Script Validation:**
- All scripts now validate that an account ID is available
- Clear error messages guide users to set the environment variable
- Scripts fail fast if AWS_ACCOUNT_ID is not set (prevents accidental deployments)

### **Multi-Account Support:**
- Easy to switch between development and production accounts
- Scripts detect account from environment automatically
- No code changes needed for different AWS accounts

---

**Last Updated**: August 18, 2025  
**Version**: 1.0  
**Status**: ✅ Production Ready

## 🎯 Quick Start Checklist

- [ ] Find your AWS Account ID: `aws sts get-caller-identity --query Account --output text`
- [ ] Set environment variable: `export AWS_ACCOUNT_ID=your-account-id`
- [ ] Add to shell profile: `echo 'export AWS_ACCOUNT_ID=your-account-id' >> ~/.zshrc`
- [ ] Test configuration: `echo $AWS_ACCOUNT_ID`
- [ ] Verify ECR access: `aws ecr describe-repositories --repository-names newvelles-docker-lambda`
- [ ] Test deployment: `make list-prod-images`

**Ready to deploy with your AWS account!** 🚀
