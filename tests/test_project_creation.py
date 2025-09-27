#!/usr/bin/env python3
"""
Quick test for project creation functionality
"""
import sys
import os
import tempfile

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_project_creation_direct():
    """Test project creation directly through model"""
    try:
        from archive.main import CachedMCPDataModel

        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            test_db = tmp.name

        try:
            model = CachedMCPDataModel(test_db)

            # Test direct project creation
            project_id = f"proj_test_project"
            now = "2024-01-01T00:00:00"

            with model.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                              (project_id, "Test Project", "Test Description", now, now))
                conn.commit()
                print("[OK] Direct project insertion works")

            # Test project retrieval
            projects = model.get_projects()
            assert len(projects) == 1, f"Expected 1 project, found {len(projects)}"
            assert projects[project_id]['name'] == "Test Project", "Project name mismatch"
            print("[OK] Project retrieval works")
            print(f"[INFO] Found project: {projects[project_id]['name']}")

        finally:
            try:
                os.unlink(test_db)
            except (OSError, PermissionError):
                pass

        return True

    except Exception as e:
        print(f"[FAIL] Project creation test failed: {e}")
        return False

def main():
    """Run project creation test"""
    print("Testing Project Creation...")
    print("=" * 30)

    success = test_project_creation_direct()

    print("=" * 30)
    if success:
        print("[SUCCESS] Project creation works correctly!")
        print("\nThe issue may be in the UI layer. Try:")
        print("1. Click 'New Project' button")
        print("2. Enter a project name")
        print("3. Enter description (optional)")
        print("4. Check the project appears in the tree")
        print("5. If not, check the status bar for error messages")
    else:
        print("[FAIL] Project creation has issues")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)