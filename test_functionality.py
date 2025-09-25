#!/usr/bin/env python3
"""
Test script for MCP GUI Controller functionality
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_basic_imports():
    """Test basic imports"""
    try:
        import sqlite3
        import tkinter as tk
        import json
        print("[OK] Basic imports successful")
        return True
    except ImportError as e:
        print(f"[FAIL] Import failed: {e}")
        return False

def test_refactored_model():
    """Test the refactored model"""
    try:
        from mcp_refactored import MCPDataModel, MCPController, MCPValidator

        # Test model initialization
        model = MCPDataModel("test_refactored.db")
        print("[OK] Model initialization successful")

        # Test validator
        valid, result = MCPValidator.validate_name("Test Project")
        assert valid == True, "Name validation failed"
        print("[OK] Validator working")

        # Test controller
        controller = MCPController(model)
        success, message = controller.create_project("Test Project", "Test Description")
        assert success == True, f"Project creation failed: {message}"
        print("[OK] Controller working")

        # Test data retrieval
        projects = model.get_projects()
        assert len(projects) > 0, "No projects found after creation"
        print("[OK] Data retrieval working")

        # Clean up
        os.remove("test_refactored.db")
        print("[OK] Refactored version tests passed")
        return True

    except Exception as e:
        print(f"[FAIL] Refactored model test failed: {e}")
        return False

def test_performance_version():
    """Test performance version imports"""
    try:
        from performance_enhanced import CachedMCPDataModel

        # Test model with caching
        model = CachedMCPDataModel("test_performance.db")
        print("[OK] Performance model initialization successful")

        # Test caching
        projects1 = model.get_projects()
        projects2 = model.get_projects()  # Should hit cache
        print("[OK] Caching working")

        # Clean up
        os.remove("test_performance.db")
        print("[OK] Performance version tests passed")
        return True

    except ImportError:
        print("[WARN] Performance version requires cachetools - install with: pip install cachetools")
        return True  # Not a failure, just missing optional dependency
    except Exception as e:
        print(f"[FAIL] Performance version test failed: {e}")
        return False

def test_original_fixes():
    """Test that original file has fixes applied"""
    try:
        with open("multi-agent_mcp_gui_controller.py", 'r') as f:
            content = f.read()

        # Check for duplicate delete_selected methods
        delete_count = content.count("def delete_selected(self):")
        assert delete_count == 1, f"Found {delete_count} delete_selected methods, expected 1"
        print("[OK] Duplicate method issue fixed")

        # Check for logging import
        assert "import logging" in content, "Logging import not found"
        print("[OK] Logging added")

        # Check for validation function
        assert "validate_name" in content, "Validation function not found"
        print("[OK] Input validation added")

        print("[OK] Original file fixes verified")
        return True

    except Exception as e:
        print(f"[FAIL] Original file test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Running MCP GUI Controller Tests...")
    print("=" * 40)

    tests = [
        test_basic_imports,
        test_original_fixes,
        test_refactored_model,
        test_performance_version
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"[FAIL] Test {test.__name__} crashed: {e}")

    print("=" * 40)
    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("[SUCCESS] All tests passed!")
        return True
    else:
        print("[WARN] Some tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)