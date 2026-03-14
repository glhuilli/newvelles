# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Newvelles** is a news aggregation and clustering tool that fetches RSS feeds, groups similar news stories using NLP/ML techniques, and generates visualization data that gets uploaded to S3 for web consumption. The project runs as both a CLI tool and an AWS Lambda function scheduled via EventBridge.

**Tech Stack**: Python 3.12, scikit-learn (TF-IDF/cosine similarity), spaCy (NLP), AWS Lambda (containerized), S3, EventBridge

## Common Development Commands

### Local Setup
```bash
# Create virtual environment (one-time)
python3.12 -m venv .python/newvelles
source .python/newvelles/bin/activate

# Install dependencies
pip install -e .
make install-dev

# Run locally with RSS feeds
newvelles --rss_file data/rss_source_short.txt
newvelles --rss_file data/rss_source.txt --s3  # Upload to S3
```

### Testing
```bash
# Comprehensive local testing (recommended before commits)
make test-local-complete          # 5-8 minutes, includes Docker + S3 validation

# Quick testing during development
make test-local-quick             # 2-3 minutes

# Unit tests
make test                         # Run all tests
make test-unit                    # Fast unit tests only
make test-coverage                # With coverage report
pytest test/test_handler.py -v   # Single test file

# S3 schema validation
make test-s3-schema              # Comprehensive schema tests
make test-s3-schema-simple       # Quick validation, no dependencies

# Lambda testing
make test-lambda-unit            # Lambda unit tests
make test-lambda-docker          # Test in Docker container (simulates AWS)
```

### Linting and Formatting
```bash
make lint        # Run pylint + flake8
make format      # Format with black + isort
```

### Docker & Deployment
```bash
# Build Docker image
make docker-build

# QA deployment workflow
make qa-build                    # Build QA image with Python 3.12
make qa-deploy                   # Deploy to RunNewvelles-qa Lambda
make qa-invoke                   # Test QA Lambda
make qa-check-s3                 # Verify S3 uploads

# Production deployment (requires confirmation)
make prod-deploy

# Deploy to specific environment
make deploy-to-env ENV=qa TAG=py312-qa-20250817-181418
```

### EventBridge Management
```bash
make check-eventbridge           # Check scheduling config
make pause-eventbridge           # Emergency stop
make resume-eventbridge          # Resume scheduling
```

## Architecture

### Core Data Flow

1. **RSS Ingestion** (`newvelles/feed/parser.py`, `newvelles/feed/load.py`)
   - Fetches news from 84 RSS feeds (13 in QA mode)
   - Filters news published within last 2 weeks
   - Extracts title, link, date, source metadata

2. **Text Processing** (`newvelles/utils/text.py`)
   - Preprocesses titles: removes stop words, numbers, special chars
   - Extracts nouns/verbs using spaCy for better grouping summaries

3. **Clustering** (`newvelles/models/grouping.py`)
   - Groups similar news using TF-IDF + cosine similarity (threshold: 0.7)
   - Hierarchical clustering: first groups similar titles, then clusters groups by context
   - Extracts common substrings for group headers
   - Filters groups with fewer than 2 titles

4. **Visualization** (`newvelles/display/show.py`)
   - Generates JSON output with grouped news structure
   - Schema version: 0.2.1 (defined in `VISUALIZATION_VERSION`)

5. **S3 Upload** (`newvelles/utils/s3.py`, `newvelles/feed/log.py`)
   - Private bucket: raw data + metadata (`latest_news_metadata.json`)
   - Public bucket: visualization data (`latest_news.json`)
   - All uploads validated against JSON schemas in `schemas/`

### Entry Points

- **CLI**: `newvelles/__main__.py` - Local execution with Click
  - `newvelles --rss_file data/rss_source.txt`
  - `--daemon` flag for continuous updates
  - `--s3` flag to upload results

- **Lambda**: `handler.py` - AWS Lambda handler
  - Invoked by EventBridge on schedule
  - Auto-detects environment (prod/QA) via S3 bucket names
  - Uses production RSS (84 feeds) or QA RSS (13 feeds)

### Environment Detection

The application auto-detects environments based on `AWS_S3_BUCKET`:
- **QA**: Bucket name contains "qa" or "test" → uses `data/rss_qa_reliable.txt` (13 feeds)
- **Production**: Default → uses `data/rss_source.txt` (84 feeds)
- **Lambda**: `AWS_LAMBDA=true` environment variable set

### AWS Lambda Architecture

- **Runtime**: Python 3.12 in Docker container (Amazon Linux 2023 base)
- **Functions**:
  - `RunNewvelles` (production)
  - `RunNewvelles-qa` (QA/shadow testing)
  - `RunNewvelles-test` (development)
- **Scheduling**: EventBridge rules trigger Lambda on schedule
- **Storage**: EFS for spaCy models, /tmp for TensorFlow Hub cache
- **Deployment**: ECR for Docker images, timestamped tags for rollback support

## Environment Variables

See `docs/ENVIRONMENT.md` for comprehensive documentation. Key variables:

**Required for AWS operations:**
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`
- `AWS_ACCOUNT_ID` (for deployments)

**Environment-specific S3 buckets:**
- Local/Test: `AWS_S3_BUCKET=newvelles-test-bucket`, `AWS_S3_PUBLIC_BUCKET=public-newvelles-test-bucket`
- QA: `AWS_S3_BUCKET=newvelles-qa-bucket`, `AWS_S3_PUBLIC_BUCKET=public-newvelles-qa-bucket`
- Production: Uses config defaults (no env vars needed)

**Configuration files:**
- `.env.local` for local development
- `.env.qa` for QA testing
- `.env.prod` for production

Always refer to `docs/ENVIRONMENT.md` when introducing new environment variables.

## Code Style Guidelines (from .cursor/rules/)

### Python Style
- Use functional, declarative programming; avoid classes where possible
- Prefer iteration and modularization over code duplication
- Use descriptive variable names with auxiliary verbs (e.g., `is_active`, `has_permission`)
- Use lowercase with underscores for files/dirs (e.g., `newvelles/feed/parser.py`)
- Keep methods and files short by extracting logic that could be modularized

### Testing Philosophy
- Validate that code behaves correctly, not just that it doesn't crash
- Test happy path AND edge cases
- No placeholder tests that assert expected behavior without verification
- List test cases based on expected behavior before implementing
- Test observable behavior, not internal implementation details
- Test both success and failure paths
- Use clear, descriptive test names explaining the scenario
- Only mock external dependencies (network, databases, third-party APIs)
- Do not mock internal application logic, business logic, or pure functions
- Avoid mocking simple utility functions unless strictly necessary
- Keep mocks readable and minimal; extract complex mocks into helpers

### Configuration Management
- Always use environment variables (assume they're already set)
- Track new environment variables in `docs/ENVIRONMENT.md`
- Do not unset environment variables unless explicitly instructed

## Project Structure

```
newvelles/
├── newvelles/           # Main package
│   ├── config/         # Configuration loading
│   ├── feed/           # RSS parsing and data loading
│   ├── models/         # Clustering and grouping logic
│   ├── utils/          # S3, text processing utilities
│   └── display/        # Visualization output
├── test/               # Test suite
├── data/               # RSS source lists and examples
├── schemas/            # JSON schemas for S3 validation
├── docs/               # Comprehensive documentation
├── bin/                # Deployment and management scripts
├── handler.py          # AWS Lambda entry point
└── Makefile            # Development and deployment commands
```

## Key Files

- `handler.py:23-32` - Environment detection logic (prod vs QA RSS selection)
- `newvelles/models/grouping.py:33` - `group_similar_titles()` uses TF-IDF + cosine similarity
- `newvelles/utils/s3.py:9` - `upload_to_s3()` handles S3 uploads with optional public ACLs
- `newvelles/feed/log.py` - S3 upload orchestration
- `schemas/latest_news_schema.json` - Visualization data schema
- `schemas/latest_news_metadata_schema.json` - Metadata schema

## Important Testing Notes

- **Always run schema validation**: S3 uploads must conform to JSON schemas
- **Docker testing is critical**: `make test-lambda-docker` simulates the Lambda environment
- **Test both environments**: Use QA bucket names to test QA mode RSS selection
- **S3 validation timing**: Wait 10 seconds after upload before validating (see `Makefile:326`)

## Deployment Workflow

1. **Development**: Make changes, run `make test-local-complete`
2. **QA Testing**:
   - `make qa-build` (builds Docker image)
   - `make qa-deploy` (deploys to `RunNewvelles-qa`)
   - `make qa-invoke` (tests Lambda)
   - `make qa-check-s3` (verifies S3 uploads)
3. **Production**: `make prod-deploy` (requires confirmation, uses latest QA image)
4. **Rollback**: `make rollback-prod` (interactive rollback to previous image)

## Rollback Support

- All Docker images are timestamped (e.g., `py312-qa-20250817-181418`)
- Use `make list-prod-images` to see available images
- Use `make rollback-prod` for interactive rollback to previous versions
- See `docs/PRODUCTION_ROLLBACK_GUIDE.md` for detailed rollback procedures

## Additional Documentation

Refer to `docs/` for detailed guides:
- `GROUPING_ALGORITHM.md` - Detailed explanation of the hierarchical clustering algorithm
- `ENVIRONMENT.md` - Environment variables reference
- `LOCAL_TESTING_GUIDE.md` - Testing workflows
- `LAMBDA_DEPLOYMENT_SUMMARY.md` - Deployment commands
- `PRODUCTION_ROLLBACK_GUIDE.md` - Rollback procedures
- `EVENTBRIDGE_SCHEDULING.md` - Scheduling configuration
- `S3_SCHEMA_TESTING.md` - Schema validation details
- `RSS_SOURCE_CONFIGURATION.md` - RSS feed management
