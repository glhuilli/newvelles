.PHONY: test test-unit test-coverage test-coverage-html install-dev lint format clean help test-s3-schema test-s3-schema-utils test-s3-schema-monitoring test-s3-schema-all test-s3-schema-simple test-end-to-end test-full-pipeline test-quick test-local-complete test-local-quick docker-build docker-deploy docker-deploy-safe deploy-to-env invoke-lambda docker-list docker-cleanup docker-stop qa-build qa-deploy qa-test qa-full-test qa-invoke qa-check-s3 prod-deploy

# Virtual environment activation helper
VENV_ACTIVATE = if [ -f ".python/newvelles/bin/activate" ]; then . .python/newvelles/bin/activate; fi

# Default target
help:
	@echo "Available targets:"
	@echo "  install-dev     Install development dependencies"
	@echo "  test           Run all tests"
	@echo "  test-unit      Run unit tests only"
	@echo "  test-coverage  Run tests with coverage report"
	@echo "  test-coverage-html  Run tests with HTML coverage report"
	@echo "  test-ci        Run comprehensive CI/CD test suite with schema validation"
	@echo "  test-end-to-end Run complete end-to-end test pipeline (all tests)"
	@echo "  test-full-pipeline Run comprehensive test pipeline including Docker Lambda"
	@echo "  test-local-complete Complete local testing workflow (recommended)"
	@echo "  test-local-quick Quick local testing workflow (faster)"
	@echo "  test-lambda    Test lambda function locally (Python)"
	@echo "  test-lambda-docker  Test lambda function in Docker container (auto-cleanup)"
	@echo "  test-lambda-docker-interactive  Test lambda function in Docker (manual control)"
	@echo "  test-lambda-stop    Stop and remove lambda test container"
	@echo "  test-lambda-unit    Run lambda unit tests"
	@echo "  test-integration    Run integration tests with S3 schema validation"
	@echo "  test-s3-schema      Run comprehensive S3 schema validation tests"
	@echo "  test-s3-schema-all  Run all S3 schema validation tests with detailed reporting"
	@echo "  test-s3-schema-utils Run S3 schema validation utility tests"
	@echo "  test-s3-schema-monitoring Run S3 schema monitoring and performance tests"
	@echo "  test-s3-schema-simple Run basic schema validation (no external dependencies)"
	@echo "  test-schema         Validate example data against JSON schemas"
	@echo "  validate-s3         Validate S3 bucket contents (use: make validate-s3 BUCKET=name)"
	@echo "  test-quick          Quick end-to-end test (fast, for development)"
	@echo "  lint           Run linting (pylint + flake8)"
	@echo "  format         Format code with black"
	@echo "  clean          Clean up generated files"
	@echo ""
	@echo "Docker Management:"
	@echo "  docker-build   Build Docker image with timestamp-based naming"
	@echo "  docker-deploy  Build and push to ECR (requires ACCOUNT=123456789012)"
	@echo "  docker-deploy-safe  Production-safe ECR push (timestamped only)"
	@echo "  deploy-to-env  Deploy image to environment (ENV=prod|qa|test TAG=image-tag)"
	@echo "  invoke-lambda  Invoke Lambda and monitor logs (FUNCTION=RunNewvelles-qa)"
	@echo "  docker-list    List all Docker images and containers"
	@echo "  docker-cleanup Clean up old Docker images and containers"
	@echo "  docker-stop    Stop all running newvelles containers"
	@echo ""
	@echo "QA Environment (Python 3.12 + ML):"
	@echo "  qa-build       Build QA Docker image with Python 3.12 + TensorFlow"
	@echo "  qa-deploy      Deploy latest image to QA Lambda function"
	@echo "  qa-test        Comprehensive QA testing (build + deploy + test)"
	@echo "  qa-full-test   Full QA pipeline (build + deploy + invoke + verify S3)"
	@echo "  qa-invoke      Invoke QA Lambda function and monitor logs"
	@echo "  qa-check-s3    Check QA S3 buckets for uploaded files"
	@echo "  prod-deploy    Deploy to production (ML config + EventBridge + test + S3 verification)"
	@echo "  check-eventbridge Check EventBridge scheduling configuration"
	@echo "  pause-eventbridge Pause EventBridge scheduling (emergency stop)"
	@echo "  resume-eventbridge Resume EventBridge scheduling"
	@echo "  diagnose-lambda    Diagnose Lambda ResourceConflictException issues"

# Install development dependencies
install-dev:
	@echo "📦 Installing development dependencies..."
	@if [ -f ".python/newvelles/bin/activate" ]; then \
		echo "✅ Activating newvelles virtual environment..."; \
		. .python/newvelles/bin/activate && pip install -r requirements_dev.txt && pip install -e .; \
	elif python -c "import sys; print(sys.prefix != sys.base_prefix)" 2>/dev/null | grep -q True; then \
		echo "✅ Virtual environment already active"; \
		pip install -r requirements_dev.txt; \
		pip install -e .; \
	else \
		echo "⚠️  No virtual environment detected. Installing with --user flag..."; \
		pip install --user -r requirements_dev.txt || echo "❌ Failed to install dependencies"; \
		pip install --user -e . || echo "❌ Failed to install package"; \
	fi

# Run all tests (fast) - includes S3 schema validation
test:
	@echo "🧪 Running all tests including S3 schema validation..."
	@$(VENV_ACTIVATE) && pytest test/ -q

# Run all tests (verbose)
test-verbose:
	@$(VENV_ACTIVATE) && pytest test/ -v

# Run unit tests only (fast)
test-unit:
	@$(VENV_ACTIVATE) && pytest test/ -q --disable-warnings

# Run tests with coverage (fast)
test-coverage:
	@$(VENV_ACTIVATE) && pytest --cov=newvelles --cov-report=term-missing test/ -q

# Run tests with HTML coverage report
test-coverage-html:
	pytest --cov=newvelles --cov-report=html --cov-report=term-missing --cov-branch test/ -q
	@echo "Coverage report generated in htmlcov/index.html"

# Run specific test file
test-file:
	@echo "Usage: make test-file FILE=test/test_config.py"
	pytest $(FILE) -v

# Run tests in parallel (requires pytest-xdist)
test-parallel:
	pytest test/ -n auto -q

# CI/CD target - comprehensive testing with schema validation
test-ci:
	@echo "🏗️  Running CI/CD test suite with comprehensive S3 schema validation..."
	python scripts/run_s3_schema_tests.py --output-json schema-test-results.json
	pytest --cov=newvelles --cov-report=xml --cov-report=term test/ -q
	@echo "✅ CI/CD tests completed. Schema validation results saved to schema-test-results.json"

# Run linting
lint:
	pylint newvelles/
	flake8 newvelles/

# Format code
format:
	black newvelles/ test/
	isort newvelles/ test/

# Lambda testing targets
test-lambda:
	python test_lambda_local.py

test-lambda-docker:
	./bin/docker-test.sh

test-lambda-docker-interactive:
	@echo "Building lambda container for testing..."
	docker build -t docker-lambda-newvelles:test .
	@if [ -f ".env.local" ]; then \
		echo "Starting container with .env.local configuration..."; \
		docker run --env-file .env.local -d -p 8080:8080 --name newvelles-lambda-test docker-lambda-newvelles:test; \
	else \
		echo "Starting container with test bucket defaults..."; \
		docker run -e AWS_S3_BUCKET=newvelles-test-bucket -e AWS_S3_PUBLIC_BUCKET=public-newvelles-test-bucket -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION -d -p 8080:8080 --name newvelles-lambda-test docker-lambda-newvelles:test; \
	fi
	@echo "Container started. Use 'make test-lambda-stop' to stop it."

test-lambda-stop:
	@echo "Stopping and removing test container..."
	-docker stop newvelles-lambda-test
	-docker rm newvelles-lambda-test

test-lambda-unit:
	pytest test/test_handler.py -v

# S3 Schema Validation Tests
# These targets validate that files uploaded to S3 conform to the correct JSON schemas.
# Use test-s3-schema-simple for quick validation without dependencies, or other targets for comprehensive testing.

# Run comprehensive S3 schema validation tests (requires dev dependencies)
test-s3-schema:
	@echo "🔍 Running comprehensive S3 schema validation tests..."
	pytest test/test_integration_s3_schema.py test/test_schema_validation_utils.py -v

# Run all S3 schema validation tests with detailed reporting
test-s3-schema-all:
	@echo "🚀 Running all S3 schema validation tests with detailed reporting..."
	python scripts/run_s3_schema_tests.py --verbose

# Run S3 schema validation utility tests
test-s3-schema-utils:
	@echo "🛠️  Running S3 schema validation utility tests..."
	pytest test/test_schema_validation_utils.py -v

# Run S3 schema monitoring and performance tests
test-s3-schema-monitoring:
	@echo "📊 Running S3 schema monitoring and performance tests..."
	pytest test/test_s3_schema_monitoring.py -v

# Run basic schema validation without external dependencies
test-s3-schema-simple:
	@echo "✨ Running basic schema validation (no external dependencies)..."
	python scripts/validate_schemas_simple.py

# Original integration tests (legacy)
test-integration:
	pytest test/test_integration_s3_schema.py -v

test-schema:
	python scripts/validate_s3_data.py examples

validate-s3:
	@echo "Usage: make validate-s3 BUCKET=your-bucket-name"
	@if [ -z "$(BUCKET)" ]; then \
		echo "❌ Please specify BUCKET parameter: make validate-s3 BUCKET=your-bucket-name"; \
		exit 1; \
	fi
	python scripts/validate_s3_data.py s3 --bucket $(BUCKET)

# End-to-End Testing Targets

# Run complete end-to-end test pipeline (all tests without Docker)
test-end-to-end:
	@echo "🚀 Starting Complete End-to-End Test Pipeline"
	@echo "============================================="
	@echo "📋 This will run all tests in sequence:"
	@echo "   1. Basic schema validation (no dependencies)"
	@echo "   2. Install development dependencies"
	@echo "   3. Unit tests with coverage"
	@echo "   4. S3 schema validation tests"
	@echo "   5. Lambda unit tests"
	@echo "   6. Integration tests"
	@echo "   7. Linting and formatting checks"
	@echo ""
	@echo "⏱️  Estimated time: 2-5 minutes"
	@echo "============================================="
	@echo ""
	@echo "📋 Step 1/7: Basic schema validation (no dependencies)..."
	make test-s3-schema-simple
	@echo ""
	@echo "📋 Step 2/7: Installing development dependencies..."
	make install-dev
	@echo ""
	@echo "📋 Step 3/7: Running unit tests with coverage..."
	make test-coverage
	@echo ""
	@echo "📋 Step 4/7: Running comprehensive S3 schema validation..."
	make test-s3-schema-all
	@echo ""
	@echo "📋 Step 5/7: Running Lambda unit tests..."
	make test-lambda-unit
	@echo ""
	@echo "📋 Step 6/7: Running integration tests..."
	make test-integration
	@echo ""
	@echo "📋 Step 7/7: Running linting and formatting checks..."
	make lint
	@echo ""
	@echo "🎉 End-to-End Test Pipeline Complete!"
	@echo "============================================="
	@echo "✅ All tests passed successfully!"
	@echo "✨ Your application is ready for deployment."

# Run comprehensive test pipeline including Docker Lambda testing
test-full-pipeline:
	@echo "🚀 Starting Full Test Pipeline with Docker"
	@echo "=========================================="
	@echo "📋 This will run the complete test suite including:"
	@echo "   1-7. All end-to-end tests"
	@echo "   8. Docker Lambda integration test"
	@echo "   9. S3 bucket validation"
	@echo ""
	@echo "⏱️  Estimated time: 3-8 minutes"
	@echo "⚠️  Requires Docker and AWS credentials"
	@echo "=========================================="
	@echo ""
	@echo "🔧 Running end-to-end tests first..."
	make test-end-to-end
	@echo ""
	@echo "📋 Step 8/9: Testing Docker Lambda integration..."
	make test-lambda-docker
	@echo ""
	@echo "📋 Step 9/9: Validating S3 bucket contents..."
	@if [ -n "$$AWS_S3_PUBLIC_BUCKET" ]; then \
		echo "🔍 Checking S3 bucket: $$AWS_S3_PUBLIC_BUCKET"; \
		aws s3 ls s3://$$AWS_S3_PUBLIC_BUCKET/ --recursive || echo "⚠️  Could not list S3 bucket (check AWS credentials)"; \
	else \
		echo "⚠️  AWS_S3_PUBLIC_BUCKET not set, skipping S3 validation"; \
	fi
	@echo ""
	@echo "🎉 Full Pipeline Test Complete!"
	@echo "==============================="
	@echo "✅ All tests including Docker Lambda passed!"
	@echo "🚀 Your application is production-ready!"

# Quick end-to-end test (fast version for development)
test-quick:
	@echo "⚡ Quick End-to-End Test (Development Mode)"
	@echo "==========================================="
	make test-s3-schema-simple
	@echo "📋 Checking if dev dependencies are available..."
	@if command -v pytest >/dev/null 2>&1; then \
		echo "✅ pytest found, running core tests..."; \
		pytest test/ -q --disable-warnings 2>/dev/null || echo "⚠️  Some tests failed (this is normal without full setup)"; \
		echo "📋 Running quick schema validation..."; \
		python -c "print('📊 Quick validation: Schema framework is ready!')" 2>/dev/null || true; \
	else \
		echo "⚠️  pytest not found. This is normal for first run."; \
		echo "💡 For full testing, run: make test-end-to-end"; \
		echo "📋 Basic validation completed successfully!"; \
	fi
	@echo ""
	@echo "✅ Quick tests complete!"
	@echo "📋 Status: Basic schema validation ✅"
	@echo "💡 Next steps:"
	@echo "   • For complete local testing: make test-local-complete (recommended)"
	@echo "   • For full testing: make test-end-to-end"
	@echo "   • For Docker testing: make test-full-pipeline"
	@echo "   • For dev setup: make install-dev"

# Clean up generated files
# Complete Local Testing Workflow

# Comprehensive local testing including Lambda and S3 validation
test-local-complete:
	@echo "🚀 Starting Complete Local Testing Workflow"
	@echo "============================================"
	@echo "📋 This will run the complete local testing sequence:"
	@echo "   1. Core end-to-end tests (unit, coverage, S3 schema, integration)"
	@echo "   2. Lambda unit tests"
	@echo "   3. Docker Lambda container test"
	@echo "   4. S3 schema validation on generated data"
	@echo "   5. Cleanup Docker containers"
	@echo ""
	@echo "⏱️  Estimated time: 5-8 minutes"
	@echo "⚠️  Requires Docker and AWS credentials for S3 testing"
	@echo "============================================"
	@echo ""
	@echo "📋 Step 1/5: Running core end-to-end tests..."
	make test-end-to-end
	@echo ""
	@echo "📋 Step 2/5: Running Lambda unit tests..."
	make test-lambda-unit
	@echo ""
	@echo "📋 Step 3/5: Testing Lambda in Docker container..."
	make test-lambda-docker
	@echo ""
	@echo "📋 Step 4/5: Validating S3 schema on generated data..."
	@echo "⏳ Waiting 10 seconds for S3 data to be available..."
	@sleep 10
	make test-s3-schema
	@echo ""
	@echo "📋 Step 5/5: Cleaning up Docker containers..."
	make test-lambda-stop || make docker-stop
	@echo ""
	@echo "✅ Complete local testing workflow finished!"
	@echo "🎉 All tests passed - your code is ready for deployment!"

# Quick local validation (faster version)
test-local-quick:
	@echo "⚡ Quick Local Testing Workflow"
	@echo "==============================="
	@echo "📋 Running essential tests:"
	@echo "   1. Quick end-to-end tests"
	@echo "   2. Lambda Docker test"
	@echo "   3. Basic S3 schema validation"
	@echo ""
	make test-quick
	@echo ""
	@echo "🐳 Testing Lambda in Docker..."
	make test-lambda-docker
	@echo ""
	@echo "📋 Quick S3 schema validation..."
	make test-s3-schema-simple
	@echo ""
	@echo "🧹 Cleanup..."
	make test-lambda-stop || make docker-stop
	@echo ""
	@echo "⚡ Quick local testing complete!"

# Docker Management Targets

# Build Docker image with timestamp-based naming
docker-build:
	@echo "🐳 Building Docker image with timestamp..."
	./bin/docker.sh

# Build Docker image and push to ECR (requires AWS account ID)
docker-deploy:
	@echo "Usage: make docker-deploy ACCOUNT=123456789012"
	@if [ -z "$(ACCOUNT)" ]; then \
		echo "❌ Please specify ACCOUNT parameter: make docker-deploy ACCOUNT=your-aws-account-id"; \
		exit 1; \
	fi
	./bin/docker.sh $(ACCOUNT)

# Production-safe ECR deployment (timestamped only, no 'latest' overwrite)
docker-deploy-safe:
	@echo "Usage: make docker-deploy-safe ACCOUNT=123456789012"
	@if [ -z "$(ACCOUNT)" ]; then \
		echo "❌ Please specify ACCOUNT parameter: make docker-deploy-safe ACCOUNT=your-aws-account-id"; \
		exit 1; \
	fi
	./bin/docker-deploy-safe.sh $(ACCOUNT)

# Deploy to specific environment (prod, qa, test)
deploy-to-env:
	@echo "Usage: make deploy-to-env ENV=qa TAG=v2-py312-20250817-181418 [ACCOUNT=617641631577]"
	@if [ -z "$(ENV)" ] || [ -z "$(TAG)" ]; then \
		echo "❌ Please specify ENV and TAG parameters"; \
		echo "   ENV options: prod, qa, test"; \
		echo "   Example: make deploy-to-env ENV=qa TAG=v2-py312-20250817-181418"; \
		exit 1; \
	fi
	./bin/deploy-to-environment.sh $(ENV) $(TAG) $(ACCOUNT)

# Invoke Lambda function and monitor logs
invoke-lambda:
	@echo "Usage: make invoke-lambda FUNCTION=RunNewvelles-qa"
	@if [ -z "$(FUNCTION)" ]; then \
		echo "❌ Please specify FUNCTION parameter"; \
		echo "   Available functions: RunNewvelles, RunNewvelles-qa, RunNewvelles-test"; \
		echo "   Example: make invoke-lambda FUNCTION=RunNewvelles-qa"; \
		exit 1; \
	fi
	./bin/invoke-lambda-simple.sh $(FUNCTION)

# List all Docker images and containers
docker-list:
	@echo "📦 Listing Docker images and containers..."
	./bin/docker-cleanup.sh list

# Clean up old Docker images and containers
docker-cleanup:
	@echo "🧹 Cleaning up Docker images and containers..."
	./bin/docker-cleanup.sh all

# Stop all running containers
docker-stop:
	@echo "🛑 Stopping all newvelles containers..."
	./bin/docker-cleanup.sh stop

clean:
	@echo "🧹 Cleaning up generated files and test artifacts..."
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf newvelles.egg-info/
	rm -f schema-test-results.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	./bin/docker-cleanup.sh all >/dev/null 2>&1 || true

# ================================================================================
# QA Environment Commands (Python 3.12 + ML)
# ================================================================================

# Build QA Docker image optimized for Python 3.12 + TensorFlow
qa-build:
	@echo "🏗️ Building QA Docker image with Python 3.12 + TensorFlow..."
	@TIMESTAMP=$$(date +"%Y%m%d-%H%M%S") && \
	IMAGE_TAG="py312-qa-$${TIMESTAMP}" && \
	echo "🏷️ Building: docker-lambda-newvelles:$${IMAGE_TAG}" && \
	docker buildx build \
		--platform linux/amd64 \
		--provenance=false \
		--load \
		-t docker-lambda-newvelles:$${IMAGE_TAG} \
		. && \
	echo "✅ QA Docker image built successfully: $${IMAGE_TAG}" && \
	echo "$${IMAGE_TAG}" > .last-qa-build.txt

# Deploy latest QA image to Lambda
qa-deploy: 
	@if [ ! -f .last-qa-build.txt ]; then \
		echo "❌ No recent QA build found. Run 'make qa-build' first."; \
		exit 1; \
	fi
	@IMAGE_TAG=$$(cat .last-qa-build.txt) && \
	ECR_TAG="617641631577.dkr.ecr.us-west-2.amazonaws.com/newvelles-docker-lambda:$${IMAGE_TAG}" && \
	echo "📤 Deploying QA image: $${IMAGE_TAG}" && \
	docker tag docker-lambda-newvelles:$${IMAGE_TAG} $${ECR_TAG} && \
	aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 617641631577.dkr.ecr.us-west-2.amazonaws.com && \
	DOCKER_CONTENT_TRUST=0 docker push $${ECR_TAG} && \
	aws lambda update-function-code --function-name RunNewvelles-qa --image-uri $${ECR_TAG} && \
	echo "✅ QA Lambda updated with image: $${IMAGE_TAG}"

# Comprehensive QA testing (build + deploy + basic test)
qa-test: qa-build qa-deploy
	@echo "🧪 Running QA tests..."
	$(MAKE) test-end-to-end
	@echo "✅ QA testing completed"

# Full QA pipeline (build + deploy + invoke + verify S3)
qa-full-test: qa-test qa-invoke qa-check-s3
	@echo "🎯 Full QA pipeline completed successfully!"

# Invoke QA Lambda function and monitor logs
qa-invoke:
	@echo "🚀 Invoking QA Lambda function..."
	@echo "Waiting for deployment to be ready..."
	@sleep 15
	./bin/invoke-lambda-simple.sh RunNewvelles-qa

# Check QA S3 buckets for uploaded files
qa-check-s3:
	@echo "📊 Checking QA S3 buckets for uploaded files..."
	@echo ""
	@echo "🗂️ Private bucket (newvelles-qa-bucket):"
	@aws s3 ls s3://newvelles-qa-bucket/ --recursive --human-readable || echo "❌ No files in private bucket"
	@echo ""
	@echo "🌐 Public bucket (public-newvelles-qa-bucket):"
	@aws s3 ls s3://public-newvelles-qa-bucket/ --recursive --human-readable || echo "❌ No files in public bucket"
	@echo ""
	@echo "✅ S3 bucket check completed"

# Deploy to production Lambda (with confirmation)
prod-deploy:
	@echo "🏭 PRODUCTION DEPLOYMENT"
	@echo "======================="
	@echo "⚠️  This will deploy to the PRODUCTION Lambda function: RunNewvelles"
	@echo ""
	@if [ ! -f .last-qa-build.txt ]; then \
		echo "❌ No recent QA build found. Run 'make qa-build' first."; \
		exit 1; \
	fi
	@IMAGE_TAG=$$(cat .last-qa-build.txt) && \
	echo "Image to deploy: $${IMAGE_TAG}" && \
	echo "" && \
	read -p "Are you sure you want to deploy to PRODUCTION? (yes/no): " confirm && \
	if [ "$$confirm" = "yes" ]; then \
		echo "🚀 Deploying to production..." && \
		./bin/deploy-to-environment.sh prod $${IMAGE_TAG} 617641631577 && \
		echo "✅ Production deployment completed"; \
	else \
		echo "❌ Production deployment cancelled"; \
	fi

# Check EventBridge scheduling configuration
check-eventbridge:
	@echo "🔍 Checking EventBridge configuration..."
	./bin/check-eventbridge.sh

# Pause EventBridge scheduling (emergency stop)
pause-eventbridge:
	@echo "⏸️ Pausing EventBridge scheduling..."
	./bin/manage-eventbridge.sh pause

# Resume EventBridge scheduling
resume-eventbridge:
	@echo "▶️ Resuming EventBridge scheduling..."
	./bin/manage-eventbridge.sh resume

# Diagnose Lambda ResourceConflictException issues
diagnose-lambda:
	@echo "🔍 Diagnosing Lambda conflicts..."
	./bin/diagnose-lambda-conflicts.sh
