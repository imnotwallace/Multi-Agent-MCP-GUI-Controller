#!/usr/bin/env python3
"""
MCP Test Runner for Multi-Agent MCP Context Manager
Executes all MCP-related test suites and provides consolidated results
"""

import subprocess
import sys
import os
from datetime import datetime

def run_test_file(test_file: str, description: str):
    """Run a single test file and return results"""
    print(f"\n🔧 Running {description}...")
    print("="*50)

    try:
        result = subprocess.run([sys.executable, test_file],
                              capture_output=True, text=True,
                              cwd=os.path.dirname(__file__))

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        print(f"❌ Failed to run {test_file}: {e}")
        return False, "", str(e)

def main():
    """Main test runner"""
    print("🚀 Multi-Agent MCP Context Manager - Complete Test Suite")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # Check if we're in the tests directory
    current_dir = os.path.dirname(__file__)

    # List of tests to run (in order of complexity)
    tests = [
        ("simple_test.py", "Simple Connectivity Test"),
        ("test_basic_permissions.py", "Basic Permission System Test"),
        ("comprehensive_test_suite.py", "Comprehensive System Test"),
        ("test_permission_system.py", "Full Permission System Test"),
        ("test_new_workflow.py", "New Workflow Test")
    ]

    results = []

    for test_file, description in tests:
        test_path = os.path.join(current_dir, test_file)
        if os.path.exists(test_path):
            success, stdout, stderr = run_test_file(test_path, description)
            results.append((test_file, description, success, stdout, stderr))
        else:
            print(f"⚠️ Test file not found: {test_file}")
            results.append((test_file, description, False, "", "File not found"))

    # Summary
    print("\n" + "="*60)
    print("TEST EXECUTION SUMMARY")
    print("="*60)

    passed = 0
    failed = 0

    for test_file, description, success, stdout, stderr in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {description}")
        if success:
            passed += 1
        else:
            failed += 1

    total = passed + failed
    print(f"\nTotal: {passed}/{total} tests passed")

    if failed > 0:
        print("\nFAILED TESTS:")
        for test_file, description, success, stdout, stderr in results:
            if not success:
                print(f"  - {description} ({test_file})")
                if stderr:
                    print(f"    Error: {stderr[:200]}...")

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())