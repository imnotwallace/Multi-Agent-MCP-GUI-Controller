#!/usr/bin/env python3
"""
Import validation tests - ensures main.py can be imported without issues
"""
import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestImportValidation(unittest.TestCase):
    """Test that all main components can be imported"""

    def test_main_module_import(self):
        """Test that main module can be imported"""
        try:
            import main
            self.assertTrue(True)  # If we get here, import succeeded
        except ImportError as e:
            self.fail(f"Failed to import main module: {e}")
        except Exception as e:
            self.fail(f"Error importing main module: {e}")

    def test_cached_mcp_data_model_import(self):
        """Test that CachedMCPDataModel can be imported and instantiated"""
        try:
            from main import CachedMCPDataModel
            # Try creating instance with in-memory database
            model = CachedMCPDataModel(":memory:")
            self.assertIsInstance(model, CachedMCPDataModel)
        except Exception as e:
            self.fail(f"Failed to import/create CachedMCPDataModel: {e}")

    def test_unified_dialog_import(self):
        """Test that UnifiedDialog can be imported"""
        try:
            from main import UnifiedDialog
            self.assertTrue(hasattr(UnifiedDialog, '__init__'))
        except Exception as e:
            self.fail(f"Failed to import UnifiedDialog: {e}")

    def test_performant_mcp_view_import(self):
        """Test that PerformantMCPView can be imported"""
        try:
            from main import PerformantMCPView
            self.assertTrue(hasattr(PerformantMCPView, '__init__'))
        except Exception as e:
            self.fail(f"Failed to import PerformantMCPView: {e}")

    def test_all_required_dependencies(self):
        """Test that all required dependencies are available"""
        required_modules = [
            'tkinter',
            'sqlite3',
            'json',
            'logging',
            'threading',
            'datetime',
            'contextlib',
            'functools',
            'cachetools'
        ]

        for module_name in required_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                self.fail(f"Required dependency {module_name} not available: {e}")

    def test_main_classes_exist(self):
        """Test that main classes exist and have expected methods"""
        from main import CachedMCPDataModel, PerformantMCPView, UnifiedDialog

        # Test CachedMCPDataModel methods
        expected_model_methods = [
            'get_projects', 'get_sessions', 'get_agents', 'get_teams',
            'create_team', 'assign_agents_to_session', 'assign_agents_to_team',
            'rename_agent', 'clear_cache'
        ]

        for method in expected_model_methods:
            self.assertTrue(hasattr(CachedMCPDataModel, method),
                          f"CachedMCPDataModel missing method: {method}")

        # Test PerformantMCPView methods
        expected_view_methods = [
            'setup_ui', 'setup_project_view', 'setup_agent_management',
            'setup_team_management', 'sort_agents', 'sort_teams'
        ]

        for method in expected_view_methods:
            self.assertTrue(hasattr(PerformantMCPView, method),
                          f"PerformantMCPView missing method: {method}")

if __name__ == '__main__':
    unittest.main(verbosity=2)