# Environment Variables Configuration

This document describes all environment variables needed to run the Newvelles project successfully across different environments.

## 🔧 Required Environment Variables

### AWS Configuration

#### Core AWS Credentials
- **`AWS_ACCESS_KEY_ID`** (Required)
  - Your AWS access key ID for authentication
  - Used for all AWS services (S3, ECR, Lambda, EventBridge)

- **`AWS_SECRET_ACCESS_KEY`** (Required)
  - Your AWS secret access key for authentication
  - Used for all AWS services (S3, ECR, Lambda, EventBridge)

- **`AWS_DEFAULT_REGION`** (Required)
  - AWS region for all resources
  - Default: `us-west-2`
  - Used for S3, Lambda, ECR operations

#### AWS Account
- **`AWS_ACCOUNT_ID`** (Required for deployment)
  - Your 12-digit AWS account ID
  - Required for ECR image URIs and Lambda deployment
  - Example: `617641631577`

### S3 Storage Configuration

#### Private S3 Bucket
- **`AWS_S3_BUCKET`** (Environment-dependent)
  - Private S3 bucket for storing processed news data
  - **Local/Test**: `newvelles-test-bucket`
  - **QA**: `newvelles-qa-bucket`
  - **Production**: Uses config default `newvelles-data-bucket`

#### Public S3 Bucket
- **`AWS_S3_PUBLIC_BUCKET`** (Environment-dependent)
  - Public S3 bucket for serving visualization data
  - **Local/Test**: `public-newvelles-test-bucket`
  - **QA**: `public-newvelles-qa-bucket`
  - **Production**: Uses config default `public-newvelles-data-bucket`

## 🏷️ Optional Environment Variables

### Application Configuration
- **`NEWVELLES_DEBUG`** (Optional)
  - Enable verbose logging and debug output
  - Values: `true` | `false`
  - Default: `false`

### LLM Naming (stories.json headlines)
- **`NEWVELLES_NAMING_PROVIDER`** (Optional)
  - Which provider generates neutral story headlines
  - Values: `bedrock` | `anthropic` | `openai` | `local`
  - Default: `local` (spaCy, no network, no credentials — a fresh clone runs offline)
  - Production/QA use `bedrock`: IAM auth via the Lambda role's `bedrock:InvokeModel`,
    **no API key in the Lambda**

- **`NEWVELLES_NAMING_MODEL`** (Optional)
  - Model id for the chosen provider
  - Default: `us.anthropic.claude-haiku-4-5-20251001-v1:0` (Bedrock inference
    profile — the bare `anthropic.` id is not invokable on-demand)

- **`NEWVELLES_NAMING_TIMEOUT`** (Optional)
  - Seconds per naming call (2 retries)
  - Default: `8`

- **`NEWVELLES_NAMING_MAX_CALLS`** (Optional)
  - Cap on new LLM calls per run (cache hits are free); `kind=="story"` is named first
  - Default: `60` — the guard against a clustering bug producing 900 tiny stories

- **`NEWVELLES_NAMING_CACHE`** (Optional, local runs only)
  - Path of the local naming cache (production uses `story_names.json` in the private bucket)
  - Default: `./cache/story_names.json`

- **`BEDROCK_REGION`** (Optional)
  - Region for the Bedrock client; defaults to `AWS_DEFAULT_REGION`, then `us-west-2`

- **`ANTHROPIC_API_KEY`** / **`OPENAI_API_KEY`** (Optional)
  - Only for the dormant `anthropic`/`openai` escape-hatch providers — never set in Lambda

### Publish Sanity Gate (stories.json)
- **`NEWVELLES_GATE_MAX_DEVIATION`** (Optional)
  - Maximum allowed story-count deviation vs. the previously published `stories.json`
    before the publish is refused (legacy files publish normally either way)
  - Default: `0.6` (block when deviation exceeds 60%)

- **`NEWVELLES_GATE_MIN_ARTICLES`** (Optional)
  - Minimum article count for a run to be considered publishable
  - Default: `50` (production runs carry ~600; QA ~120)

### Testing Configuration
- **`NEWVELLES_TEST_UPLOAD_TIMEOUT`** (Optional)
  - Timeout in seconds for S3 upload operations during testing
  - Default: `300` (5 minutes)

- **`NEWVELLES_TEST_VALIDATION_TIMEOUT`** (Optional)
  - Timeout in seconds for S3 schema validation during testing
  - Default: `30` seconds

### TensorFlow/ML Configuration (Auto-configured)
- **`TFHUB_CACHE_DIR`** (Auto-set)
  - TensorFlow Hub cache directory
  - Lambda: `/tmp/tfhub_cache`
  - Local: `/opt/tfhub_models`

- **`TF_CPP_MIN_LOG_LEVEL`** (Auto-set)
  - TensorFlow logging level
  - Default: `2` (reduce TF logging)

- **`AWS_LAMBDA`** (Auto-set in Docker)
  - Indicates Lambda environment
  - Set to `true` in Docker containers

## 🌍 Environment-Specific Configurations

### Local Development
```bash
# Core AWS
AWS_ACCESS_KEY_ID=your_local_access_key_here
AWS_SECRET_ACCESS_KEY=your_local_secret_key_here
AWS_DEFAULT_REGION=us-west-2

# Local S3 buckets
AWS_S3_BUCKET=newvelles-test-bucket
AWS_S3_PUBLIC_BUCKET=public-newvelles-test-bucket

# Debug mode
NEWVELLES_DEBUG=true
```

### QA Environment
```bash
# Core AWS
AWS_ACCESS_KEY_ID=your_aws_access_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here
AWS_DEFAULT_REGION=us-west-2

# QA S3 buckets
AWS_S3_BUCKET=newvelles-qa-bucket
AWS_S3_PUBLIC_BUCKET=public-newvelles-qa-bucket

# Minimal debug
NEWVELLES_DEBUG=false
```

### Production Environment
```bash
# Core AWS
AWS_ACCESS_KEY_ID=your_production_access_key_here
AWS_SECRET_ACCESS_KEY=your_production_secret_key_here
AWS_DEFAULT_REGION=us-west-2

# Production uses config defaults (no bucket env vars needed)
# - newvelles-data-bucket (private)
# - public-newvelles-data-bucket (public)

# Minimal logging
NEWVELLES_DEBUG=false
```

### Deployment/CI Environment
```bash
# All previous variables plus:
AWS_ACCOUNT_ID=your-12-digit-account-id
```

## 📝 Configuration Files

Environment variables can be loaded from:
- `.env.local` (local development)
- `.env.qa` (QA testing)
- `.env.prod` (production)

Use the provided example files:
```bash
cp env.local.example .env.local
cp env.qa.example .env.qa
cp env.prod.example .env.prod
```

## 🔒 Security Notes

1. **Never commit actual credentials** to version control
2. Use `.env*` files locally (already in `.gitignore`)
3. Use AWS IAM roles in production when possible
4. Use AWS Secrets Manager for sensitive production values
5. Rotate credentials regularly

## 📊 Environment Detection

The application automatically detects environments based on:
- **QA Environment**: S3 bucket name contains `qa` or `test`
- **Production**: Uses config file defaults
- **Lambda**: `AWS_LAMBDA=true` environment variable

## 🛠️ Setup Commands

```bash
# Set AWS Account ID (required for deployment)
export AWS_ACCOUNT_ID=your-12-digit-account-id

# Verify configuration
echo $AWS_ACCOUNT_ID
aws sts get-caller-identity

# Load environment file
source .env.local  # or .env.qa, .env.prod
```

## 🔍 Troubleshooting

- **Missing AWS_ACCOUNT_ID**: Required for ECR and Lambda operations
- **Wrong S3 bucket**: Check environment-specific bucket names
- **Permission errors**: Verify AWS credentials and IAM policies
- **TensorFlow cache**: Automatically configured for Lambda vs local