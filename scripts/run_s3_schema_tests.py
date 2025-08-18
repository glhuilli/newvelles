#!/usr/bin/env python3
"""
Comprehensive test runner for S3 schema validation tests.

This script runs all schema validation tests and provides detailed reporting
on the status of S3 upload schema compliance.

Usage:
    python scripts/run_s3_schema_tests.py [--verbose] [--test-type TYPE]
    
Test Types:
    - integration: Run integration tests with mock S3
    - utils: Run utility function tests
    - monitoring: Run monitoring and performance tests
    - all: Run all tests (default)
"""

import argparse
import sys
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any


class S3SchemaTestRunner:
    """Test runner for S3 schema validation tests."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.test_results = {}
        
    def run_tests(self, test_type: str = "all") -> Dict[str, Any]:
        """Run the specified type of tests."""
        print("🚀 Starting S3 Schema Validation Tests")
        print("=" * 50)
        
        test_modules = self._get_test_modules(test_type)
        
        overall_success = True
        for module_name, module_path in test_modules.items():
            print(f"\n📋 Running {module_name}...")
            success = self._run_pytest_module(module_path)
            self.test_results[module_name] = success
            overall_success = overall_success and success
            
            if success:
                print(f"✅ {module_name} - PASSED")
            else:
                print(f"❌ {module_name} - FAILED")
        
        print("\\n" + "=" * 50)
        print("📊 Test Summary")
        print("=" * 50)
        
        for module_name, success in self.test_results.items():
            status = "PASSED" if success else "FAILED"
            icon = "✅" if success else "❌"
            print(f"{icon} {module_name}: {status}")
        
        if overall_success:
            print("\\n🎉 All S3 schema validation tests PASSED!")
            print("✨ Your S3 uploads are properly validated against JSON schemas.")
        else:
            print("\\n⚠️  Some S3 schema validation tests FAILED!")
            print("🔍 Please review the test output above for details.")
        
        return {
            "overall_success": overall_success,
            "results": self.test_results,
            "summary": self._generate_summary()
        }
    
    def _get_test_modules(self, test_type: str) -> Dict[str, str]:
        """Get test modules based on the specified type."""
        all_modules = {
            "Integration Tests": "test/test_integration_s3_schema.py",
            "Utility Tests": "test/test_schema_validation_utils.py", 
            "Monitoring Tests": "test/test_s3_schema_monitoring.py"
        }
        
        if test_type == "integration":
            return {"Integration Tests": all_modules["Integration Tests"]}
        elif test_type == "utils":
            return {"Utility Tests": all_modules["Utility Tests"]}
        elif test_type == "monitoring":
            return {"Monitoring Tests": all_modules["Monitoring Tests"]}
        else:  # all
            return all_modules
    
    def _run_pytest_module(self, module_path: str) -> bool:
        """Run pytest on a specific module."""
        cmd = ["python", "-m", "pytest", module_path]
        
        if self.verbose:
            cmd.extend(["-v", "-s"])
        else:
            cmd.append("-q")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=not self.verbose,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            if not self.verbose and result.returncode != 0:
                print(f"Error output: {result.stderr}")
                print(f"Standard output: {result.stdout}")
                
            return result.returncode == 0
            
        except Exception as e:
            print(f"Error running tests: {e}")
            return False
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate a detailed summary of test results."""
        total_modules = len(self.test_results)
        passed_modules = sum(1 for success in self.test_results.values() if success)
        failed_modules = total_modules - passed_modules
        
        return {
            "total_test_modules": total_modules,
            "passed_modules": passed_modules,
            "failed_modules": failed_modules,
            "success_rate": passed_modules / total_modules if total_modules > 0 else 0,
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        if all(self.test_results.values()):
            recommendations.extend([
                "✨ All tests are passing! Your schema validation is working correctly.",
                "🔄 Consider running these tests regularly as part of your CI/CD pipeline.",
                "📊 Monitor S3 upload schema compliance in production using the monitoring tools."
            ])
        else:
            failed_tests = [name for name, success in self.test_results.items() if not success]
            
            if "Integration Tests" in failed_tests:
                recommendations.append(
                    "🔧 Fix integration test failures - these indicate issues with S3 upload validation."
                )
            
            if "Utility Tests" in failed_tests:
                recommendations.append(
                    "🛠️  Fix utility test failures - these indicate issues with schema validation helpers."
                )
            
            if "Monitoring Tests" in failed_tests:
                recommendations.append(
                    "📈 Fix monitoring test failures - these affect production monitoring capabilities."
                )
            
            recommendations.extend([
                "🚨 Address failing tests before deploying to production.",
                "🔍 Review schema definitions in the schemas/ directory.",
                "📋 Check that S3 upload functions conform to expected data structures."
            ])
        
        return recommendations


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description="Run S3 schema validation tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Run tests in verbose mode"
    )
    
    parser.add_argument(
        "--test-type", "-t",
        choices=["integration", "utils", "monitoring", "all"],
        default="all",
        help="Type of tests to run (default: all)"
    )
    
    parser.add_argument(
        "--output-json",
        help="Save test results to JSON file"
    )
    
    args = parser.parse_args()
    
    # Verify we're in the right directory
    if not Path("schemas").exists():
        print("❌ Error: schemas/ directory not found.")
        print("🔍 Please run this script from the project root directory.")
        sys.exit(1)
    
    # Run tests
    runner = S3SchemaTestRunner(verbose=args.verbose)
    results = runner.run_tests(args.test_type)
    
    # Save results to JSON if requested
    if args.output_json:
        with open(args.output_json, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\\n💾 Test results saved to {args.output_json}")
    
    # Print recommendations
    print("\\n" + "=" * 50)
    print("💡 Recommendations")
    print("=" * 50)
    for rec in results["summary"]["recommendations"]:
        print(rec)
    
    # Exit with appropriate code
    sys.exit(0 if results["overall_success"] else 1)


if __name__ == "__main__":
    main()
