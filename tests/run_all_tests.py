#!/usr/bin/env python3
"""
Test runner for Multi-Agent MCP GUI Controller
Runs all test suites and provides comprehensive coverage report
"""
import unittest
import sys
import os
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_all_tests():
    """Run all test suites"""
    print("=" * 70)
    print("MULTI-AGENT MCP GUI CONTROLLER - TEST SUITE")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Discover and run all tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test modules
    test_modules = [
        'test_data_model',
        'test_ui_functionality',
        'test_sorting_functionality'
    ]

    total_tests = 0
    loaded_modules = []

    for module_name in test_modules:
        try:
            # Import the test module
            module = __import__(module_name, fromlist=[''])

            # Load tests from the module
            module_suite = loader.loadTestsFromModule(module)
            suite.addTest(module_suite)

            # Count tests in this module
            test_count = module_suite.countTestCases()
            total_tests += test_count
            loaded_modules.append((module_name, test_count))

            print(f"[OK] Loaded {test_count} tests from {module_name}")

        except ImportError as e:
            print(f"[FAIL] Failed to load {module_name}: {e}")
        except Exception as e:
            print(f"[ERROR] Error loading {module_name}: {e}")

    print()
    print(f"Total tests loaded: {total_tests}")
    print("-" * 70)
    print()

    # Run the tests
    runner = unittest.TextTestRunner(
        verbosity=2,
        stream=sys.stdout,
        buffer=True,  # Capture stdout/stderr during tests
        failfast=False  # Run all tests even if some fail
    )

    start_time = time.time()
    result = runner.run(suite)
    end_time = time.time()

    # Print summary
    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
    print(f"Time taken: {end_time - start_time:.2f} seconds")

    success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100) if result.testsRun > 0 else 0
    print(f"Success rate: {success_rate:.1f}%")

    # Print detailed failure information
    if result.failures:
        print("\nFAILURES:")
        print("-" * 30)
        for test, traceback in result.failures:
            print(f"FAIL: {test}")
            print(f"Traceback:\n{traceback}")

    if result.errors:
        print("\nERRORS:")
        print("-" * 30)
        for test, traceback in result.errors:
            print(f"ERROR: {test}")
            print(f"Traceback:\n{traceback}")

    # Overall result
    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print("[SUCCESS] ALL TESTS PASSED!")
        return 0
    else:
        print("[FAILURE] SOME TESTS FAILED")
        return 1

if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)