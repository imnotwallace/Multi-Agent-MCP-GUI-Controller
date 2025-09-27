#!/usr/bin/env python3
"""
Test script for new team and bulk operation features
"""
import sys
import os
import sqlite3
import tempfile

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_database_schema():
    """Test that new tables and columns exist"""
    try:
        from archive.main import CachedMCPDataModel

        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            test_db = tmp.name

        try:
            model = CachedMCPDataModel(test_db)

            with model.pool.get_connection() as conn:
                cursor = conn.cursor()

                # Check teams table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='teams'")
                assert cursor.fetchone() is not None, "Teams table not found"
                print("[OK] Teams table exists")

                # Check agents table has team_id column
                cursor.execute("PRAGMA table_info(agents)")
                columns = [col[1] for col in cursor.fetchall()]
                assert 'team_id' in columns, "team_id column not found in agents table"
                print("[OK] Agents table has team_id column")

                # Check indexes
                cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_agents_team'")
                assert cursor.fetchone() is not None, "Team index not found"
                print("[OK] Team indexes created")

        finally:
            try:
                os.unlink(test_db)
            except (OSError, PermissionError):
                pass  # Ignore Windows file locking issues

        return True

    except Exception as e:
        print(f"[FAIL] Database schema test failed: {e}")
        return False

def test_team_operations():
    """Test team creation and operations"""
    try:
        from archive.main import CachedMCPDataModel

        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            test_db = tmp.name

        try:
            model = CachedMCPDataModel(test_db)

            # Test team creation
            team_id = model.create_team("Test Team", None, "Test team description")
            assert team_id, "Team creation failed"
            print("[OK] Team creation works")

            # Test getting teams
            teams = model.get_teams()
            assert len(teams) == 1, f"Expected 1 team, found {len(teams)}"
            assert teams[team_id]['name'] == "Test Team", "Team name mismatch"
            print("[OK] Team retrieval works")

            # Test agent creation
            with model.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO agents (id, name, status, last_active) VALUES (?, ?, ?, ?)',
                              ("agent_test", "Test Agent", "disconnected", "2024-01-01"))
                conn.commit()

            # Test agent-team assignment
            model.assign_agents_to_team(["agent_test"], team_id)

            agents = model.get_agents()
            assert agents["agent_test"]["team_id"] == team_id, "Agent team assignment failed"
            print("[OK] Agent team assignment works")

            # Test bulk unassignment
            model.assign_agents_to_team(["agent_test"], None)
            agents = model.get_agents()
            assert agents["agent_test"]["team_id"] is None, "Agent team unassignment failed"
            print("[OK] Agent team unassignment works")

        finally:
            try:
                os.unlink(test_db)
            except (OSError, PermissionError):
                pass  # Ignore Windows file locking issues

        return True

    except Exception as e:
        print(f"[FAIL] Team operations test failed: {e}")
        return False

def test_bulk_session_operations():
    """Test bulk session assignment operations"""
    try:
        from archive.main import CachedMCPDataModel

        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            test_db = tmp.name

        try:
            model = CachedMCPDataModel(test_db)

            # Create test project and session
            project_id = f"proj_test_project"
            session_id = f"sess_test_session"

            with model.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                              (project_id, "Test Project", "", "2024-01-01", "2024-01-01"))
                cursor.execute('INSERT INTO sessions (id, name, project_id, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                              (session_id, "Test Session", project_id, "", "2024-01-01", "2024-01-01"))

                # Create multiple test agents
                for i in range(3):
                    cursor.execute('INSERT INTO agents (id, name, status, last_active) VALUES (?, ?, ?, ?)',
                                  (f"agent_test_{i}", f"Test Agent {i}", "disconnected", "2024-01-01"))
                conn.commit()

            # Test bulk session assignment
            agent_ids = [f"agent_test_{i}" for i in range(3)]
            model.assign_agents_to_session(agent_ids, session_id)

            agents = model.get_agents()
            for agent_id in agent_ids:
                assert agents[agent_id]["session_id"] == session_id, f"Agent {agent_id} not assigned to session"
                assert agents[agent_id]["status"] == "connected", f"Agent {agent_id} status not updated"
            print("[OK] Bulk session assignment works")

            # Test bulk disconnection
            model.assign_agents_to_session(agent_ids, None)
            agents = model.get_agents()
            for agent_id in agent_ids:
                assert agents[agent_id]["session_id"] is None, f"Agent {agent_id} not disconnected"
                assert agents[agent_id]["status"] == "disconnected", f"Agent {agent_id} status not updated"
            print("[OK] Bulk session disconnection works")

        finally:
            try:
                os.unlink(test_db)
            except (OSError, PermissionError):
                pass  # Ignore Windows file locking issues

        return True

    except Exception as e:
        print(f"[FAIL] Bulk session operations test failed: {e}")
        return False

def test_agent_renaming():
    """Test agent renaming functionality"""
    try:
        from archive.main import CachedMCPDataModel

        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            test_db = tmp.name

        try:
            model = CachedMCPDataModel(test_db)

            # Create test agent
            with model.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO agents (id, name, status, last_active) VALUES (?, ?, ?, ?)',
                              ("agent_rename_test", "Original Name", "disconnected", "2024-01-01"))
                conn.commit()

            # Test renaming
            model.rename_agent("agent_rename_test", "New Name")

            agents = model.get_agents()
            assert agents["agent_rename_test"]["name"] == "New Name", "Agent renaming failed"
            print("[OK] Agent renaming works")

        finally:
            try:
                os.unlink(test_db)
            except (OSError, PermissionError):
                pass  # Ignore Windows file locking issues

        return True

    except Exception as e:
        print(f"[FAIL] Agent renaming test failed: {e}")
        return False

def test_caching():
    """Test that caching works with new features"""
    try:
        from archive.main import CachedMCPDataModel

        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            test_db = tmp.name

        try:
            model = CachedMCPDataModel(test_db)

            # Create test team
            team_id = model.create_team("Cache Test Team")

            # First call should populate cache
            teams1 = model.get_teams()

            # Second call should hit cache (check by modifying database directly)
            with model.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO teams (id, name, created_at) VALUES (?, ?, ?)',
                              ("team_direct", "Direct Team", "2024-01-01"))
                conn.commit()

            # Should still get cached result (without direct team)
            teams2 = model.get_teams()
            assert len(teams2) == len(teams1), "Cache not working - new team appeared"
            print("[OK] Team caching works")

            # Clear cache and verify new team appears
            model.clear_cache()
            teams3 = model.get_teams()
            assert len(teams3) == len(teams1) + 1, "Cache clearing not working"
            print("[OK] Team cache clearing works")

        finally:
            try:
                os.unlink(test_db)
            except (OSError, PermissionError):
                pass  # Ignore Windows file locking issues

        return True

    except Exception as e:
        print(f"[FAIL] Caching test failed: {e}")
        return False

def main():
    """Run all new feature tests"""
    print("Testing New Features...")
    print("=" * 40)

    tests = [
        test_database_schema,
        test_team_operations,
        test_bulk_session_operations,
        test_agent_renaming,
        test_caching
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
    print(f"New Feature Tests passed: {passed}/{total}")

    if passed == total:
        print("[SUCCESS] All new feature tests passed!")
        return True
    else:
        print("[WARN] Some new feature tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)