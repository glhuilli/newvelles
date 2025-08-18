# S3 Schema Validation Testing Framework

This document describes the comprehensive testing framework for validating that files uploaded to S3 conform to the correct JSON schemas.

## Overview

The schema validation testing framework ensures that all data uploaded to S3 follows the defined JSON schemas, providing confidence in data integrity and API contracts. The framework includes:

- **Integration Tests**: End-to-end testing of S3 uploads with schema validation
- **Utility Tests**: Testing of schema validation helper functions and utilities
- **Monitoring Tests**: Performance testing and production monitoring capabilities
- **Error Detection**: Comprehensive error handling and reporting

## Test Files

### Core Test Files

1. **`test/test_integration_s3_schema.py`**
   - Integration tests for S3 upload and schema validation
   - Tests end-to-end Lambda execution with S3 uploads
   - Validates both `latest_news.json` and `latest_news_metadata.json`
   - Tests with mock RSS data and real example data

2. **`test/test_schema_validation_utils.py`**
   - Utility functions for schema validation
   - Helper classes and data generation functions
   - Stress tests with large datasets
   - Edge case testing (minimal data, very long data, various timestamp formats)

3. **`test/test_s3_schema_monitoring.py`**
   - Monitoring and performance tests
   - Continuous upload validation testing
   - Performance benchmarks for large datasets
   - Error detection and alerting mechanisms
   - Validation reporting and metrics collection

### Supporting Files

4. **`scripts/run_s3_schema_tests.py`**
   - Comprehensive test runner script
   - Provides detailed reporting and recommendations
   - Supports different test types and output formats

## JSON Schemas

The tests validate against these schemas:

- **`schemas/latest_news_schema.json`**: Schema for news visualization data
- **`schemas/latest_news_metadata_schema.json`**: Schema for metadata files

### Schema Structure

#### Latest News Schema
```json
{
  "group_name": {
    "subgroup_name": {
      "article_title": {
        "title": "string (required)",
        "link": "string (URI format, required)",
        "timestamp": "string (RSS timestamp format, required)",
        "source": "string (URI format, required)"
      }
    }
  }
}
```

#### Metadata Schema
```json
{
  "datetime": "string (ISO 8601: YYYY-MM-DDTHH:mm:ss, required)",
  "version": "string (semantic version: major.minor.patch, required)"
}
```

## Running the Tests

### Quick Start

Run all schema validation tests:
```bash
python scripts/run_s3_schema_tests.py
```

### Test Types

Run specific test categories:
```bash
# Integration tests only
python scripts/run_s3_schema_tests.py --test-type integration

# Utility tests only
python scripts/run_s3_schema_tests.py --test-type utils

# Monitoring tests only
python scripts/run_s3_schema_tests.py --test-type monitoring
```

### Verbose Output

For detailed test output:
```bash
python scripts/run_s3_schema_tests.py --verbose
```

### Save Results

Save test results to JSON:
```bash
python scripts/run_s3_schema_tests.py --output-json results.json
```

### Direct Pytest

Run individual test files directly:
```bash
# Run integration tests
pytest test/test_integration_s3_schema.py -v

# Run utility tests
pytest test/test_schema_validation_utils.py -v

# Run monitoring tests
pytest test/test_s3_schema_monitoring.py -v
```

## Test Categories

### 1. Integration Tests (`TestS3SchemaValidation`)

**Purpose**: Ensure end-to-end S3 upload process validates schemas correctly.

**Key Tests**:
- `test_s3_upload_schema_validation`: Basic S3 upload with schema validation
- `test_schema_validation_with_real_example`: Validation against real example data
- `test_schema_validation_failures`: Error detection for invalid data
- `test_end_to_end_lambda_s3_validation`: Complete Lambda → S3 → Validation flow
- `test_s3_upload_large_data_validation`: Performance with large datasets
- `test_schema_edge_cases`: Boundary conditions and edge cases

### 2. Utility Tests (`TestSchemaValidationUtils`)

**Purpose**: Test reusable components and helper functions.

**Key Tests**:
- `test_load_schema_success`: Schema loading functionality
- `test_validate_data_against_schema_success`: Data validation helpers
- `test_generate_valid_news_entry`: Test data generation
- `test_create_nested_news_structure`: Complex data structure creation

### 3. Stress Tests (`TestSchemaValidationStressTests`)

**Purpose**: Ensure the system handles large datasets and edge cases.

**Key Tests**:
- `test_large_dataset_validation`: 1000+ article validation
- `test_edge_case_data_validation`: Minimal and maximal valid data
- `test_various_timestamp_formats`: Multiple RSS timestamp formats
- `test_metadata_version_formats`: Semantic version validation

### 4. Monitoring Tests (`TestS3SchemaMonitoring`)

**Purpose**: Production monitoring and performance validation.

**Key Tests**:
- `test_continuous_upload_validation`: Multiple consecutive uploads
- `test_performance_schema_validation`: Performance benchmarks
- `test_schema_validation_error_detection`: Error detection capabilities
- `test_schema_validation_monitoring_report`: Monitoring report generation

### 5. Schema Evolution Tests (`TestSchemaEvolution`)

**Purpose**: Ensure backward compatibility as schemas evolve.

**Key Tests**:
- `test_schema_version_compatibility`: Version format compatibility
- `test_schema_backwards_compatibility`: Support for older data formats

## Usage in CI/CD

### GitHub Actions Example

```yaml
name: S3 Schema Validation Tests

on: [push, pull_request]

jobs:
  schema-validation:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements_dev.txt
    
    - name: Run S3 Schema Validation Tests
      run: |
        python scripts/run_s3_schema_tests.py --output-json schema-test-results.json
    
    - name: Upload test results
      uses: actions/upload-artifact@v2
      if: always()
      with:
        name: schema-test-results
        path: schema-test-results.json
```

### Local Development Workflow

1. **Before committing changes**:
   ```bash
   python scripts/run_s3_schema_tests.py
   ```

2. **After modifying schemas**:
   ```bash
   python scripts/run_s3_schema_tests.py --test-type integration --verbose
   ```

3. **Performance testing**:
   ```bash
   python scripts/run_s3_schema_tests.py --test-type monitoring
   ```

## Production Monitoring

### Validation Metrics

The monitoring tests collect these metrics:
- Total validation attempts
- Successful validations
- Failed validations
- Error categorization
- Performance metrics (validation time, upload time)

### Alert Conditions

Set up alerts for:
- Schema validation failure rate > 5%
- Validation time > 10 seconds
- Upload time > 30 seconds
- Missing required fields in uploaded data
- Invalid URL formats in news data
- Malformed timestamp formats

### Monitoring Integration

The framework provides utilities for integration with:
- CloudWatch (AWS)
- Datadog
- Custom monitoring systems

Example integration:
```python
from test.test_s3_schema_monitoring import TestS3SchemaMonitoring

# Generate validation report
report = monitoring_instance._generate_validation_report(s3_client, bucket_name)

# Send to monitoring system
send_metrics_to_cloudwatch(report)
```

## Troubleshooting

### Common Issues

1. **Schema file not found**
   - Ensure you're running tests from the project root
   - Verify `schemas/` directory exists with schema files

2. **Mock AWS failures**
   - Check that `moto` is installed: `pip install moto[s3]`
   - Ensure proper AWS region configuration in tests

3. **Validation errors**
   - Review schema definitions for accuracy
   - Check that test data matches expected formats
   - Verify timestamp formats in RSS data

4. **Performance issues**
   - Large datasets may require increased timeouts
   - Consider pagination for very large validation jobs

### Debug Mode

Run tests with maximum verbosity:
```bash
pytest test/test_integration_s3_schema.py -v -s --tb=long
```

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

When adding new tests:

1. **Follow naming conventions**: `test_*` for test functions
2. **Add docstrings**: Describe what each test validates
3. **Use fixtures**: Leverage existing fixtures for S3 setup
4. **Update documentation**: Add new tests to this README
5. **Test edge cases**: Include boundary conditions and error cases

### Test Development Guidelines

- **Isolation**: Each test should be independent
- **Clarity**: Test names should clearly indicate what's being tested
- **Coverage**: Aim for comprehensive coverage of schema validation scenarios
- **Performance**: Monitor test execution time and optimize as needed
- **Reliability**: Tests should be deterministic and not flaky

## Schema Validation Best Practices

1. **Always validate after upload**: Don't assume S3 uploads are valid
2. **Monitor validation metrics**: Track success/failure rates
3. **Handle errors gracefully**: Provide clear error messages
4. **Version your schemas**: Plan for schema evolution
5. **Test with real data**: Use actual RSS data samples for testing
6. **Performance testing**: Validate with production-sized datasets

This comprehensive testing framework ensures that your S3 uploads maintain data integrity and conform to your API contracts, providing confidence in your data pipeline's reliability.
