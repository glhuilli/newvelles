# Local Testing Guide

This guide provides the recommended workflows for testing your Newvelles application locally.

## 🎯 Recommended Workflows

### **Primary: Complete Local Testing** (Recommended)
```bash
make test-local-complete
```

**What it does:**
1. ✅ **Core end-to-end tests** (unit, coverage, S3 schema, integration)
2. ✅ **Lambda unit tests** 
3. ✅ **Docker Lambda container test** (simulates AWS environment)
4. ✅ **S3 schema validation** on newly generated data
5. ✅ **Automatic cleanup** of Docker containers

**When to use:** Before committing changes, before deployment, comprehensive validation

**Time:** ~5-8 minutes

### **Secondary: Quick Local Testing** (Development)
```bash
make test-local-quick
```

**What it does:**
1. ✅ **Quick end-to-end tests** (essential functionality)
2. ✅ **Docker Lambda test**
3. ✅ **Basic S3 schema validation**
4. ✅ **Automatic cleanup**

**When to use:** During development, quick validation cycles

**Time:** ~2-3 minutes

## 🔧 Individual Test Components

If you need to run specific parts of the testing workflow:

### Core Functionality Tests
```bash
make test-end-to-end     # Full test suite (no Docker)
make test-quick          # Fast development tests
```

### Lambda Testing
```bash
make test-lambda-unit    # Lambda unit tests
make test-lambda-docker  # Lambda in Docker container
make test-lambda-stop    # Stop/cleanup Lambda containers
```

### S3 Schema Validation
```bash
make test-s3-schema           # Comprehensive S3 validation
make test-s3-schema-simple    # Basic validation (no dependencies)
```

### Docker Management
```bash
make docker-list        # See running containers/images
make docker-cleanup     # Clean up old Docker resources
make docker-stop        # Stop all newvelles containers
```

## 📋 Prerequisites

### Required for all testing:
- Python virtual environment activated (`newvelles`)
- Development dependencies installed (`make install-dev`)

### Required for complete workflow:
- **Docker** installed and running
- **AWS credentials** configured (for S3 testing)
- **Test S3 buckets** available:
  - `newvelles-test-bucket` 
  - `public-newvelles-test-bucket`

### Optional:
- `.env.local` file for custom AWS configuration (see `env.local.example`)

## 🚀 Getting Started

### First-time setup:
```bash
# 1. Install dependencies
make install-dev

# 2. Run complete tests to verify everything works
make test-local-complete
```

### Daily development workflow:
```bash
# Quick validation during development
make test-local-quick

# Full validation before committing
make test-local-complete
```

## 🛠️ Troubleshooting

### Docker issues:
```bash
# Clean up Docker resources
make docker-cleanup

# Check what's running
make docker-list

# Stop everything
make docker-stop
```

### Test failures:
```bash
# Run individual components to isolate issues
make test-unit           # Check core functionality
make test-s3-schema-simple  # Check schema validation
make test-lambda-unit    # Check Lambda functionality
```

### AWS/S3 issues:
- Verify AWS credentials: `aws s3 ls`
- Check bucket access: `make validate-s3 BUCKET=newvelles-test-bucket`
- Review `.env.local` configuration

## 📊 Understanding Test Output

The workflows provide clear progress indicators:
- 🚀 **Starting** - Workflow beginning
- 📋 **Step X/Y** - Current progress  
- ✅ **Success** - Tests passed
- ❌ **Failure** - Tests failed (with details)
- 🧹 **Cleanup** - Automatic cleanup running

## 💡 Best Practices

1. **Always run `test-local-complete` before committing**
2. **Use `test-local-quick` during active development**
3. **Check Docker resources periodically** with `make docker-list`
4. **Clean up regularly** with `make docker-cleanup`
5. **Keep AWS credentials current** for S3 testing
6. **Review test output** for warnings or performance issues

## 🎯 Summary

| Command | Use Case | Time | Docker | AWS |
|---------|----------|------|--------|-----|
| `make test-local-complete` | **Pre-commit validation** | 5-8 min | ✅ | ✅ |
| `make test-local-quick` | **Development cycles** | 2-3 min | ✅ | ✅ |
| `make test-end-to-end` | **Core functionality** | 3-5 min | ❌ | ✅ |
| `make test-quick` | **Fast development** | 1-2 min | ❌ | ❌ |

**Recommended:** Start with `make test-local-complete` to ensure your setup works, then use `make test-local-quick` for daily development.
