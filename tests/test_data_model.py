#!/usr/bin/env python3
"""
Test suite for the CachedMCPDataModel class
Tests database operations, caching, and data integrity
"""
import unittest
import sqlite3
import os
import tempfile
import shutil
from datetime import datetime
import sys
import threading
import time

# Add parent directory to path to import main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import CachedMCPDataModel


class TestCachedMCPDataModel(unittest.TestCase):
    """Test cases for CachedMCPDataModel"""

    def setUp(self):
        """Set up test database and model instance"""
        # Create temporary directory for test database
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_mcp.db")

        # Create model instance with test database
        self.model = CachedMCPDataModel(self.test_db_path)

    def tearDown(self):
        """Clean up test database and temporary files"""
        # Close any open connections
        if hasattr(self.model, 'pool'):
            self.model.pool.close()

        # Remove temporary directory
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_database_initialization(self):
        """Test that database is initialized with correct schema"""
        self.assertTrue(os.path.exists(self.test_db_path))

        # Check that tables exist
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            expected_tables = ['projects', 'sessions', 'agents', 'contexts', 'teams']
            for table in expected_tables:
                self.assertIn(table, tables, f"Table {table} should exist")

    def test_create_project(self):
        """Test project creation and retrieval"""
        # Create a project
        project_id = "test_project_1"
        project_name = "Test Project 1"
        description = "A test project"

        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                'INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                (project_id, project_name, description, now, now)
            )
            conn.commit()

        # Retrieve projects
        projects = self.model.get_projects()

        self.assertIn(project_id, projects)
        self.assertEqual(projects[project_id]['name'], project_name)
        self.assertEqual(projects[project_id]['description'], description)

    def test_create_session(self):
        """Test session creation and project association"""
        # First create a project
        project_id = "test_project_1"
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                'INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                (project_id, "Test Project", "Description", now, now)
            )
            conn.commit()

        # Create a session
        session_id = "test_session_1"
        session_name = "Test Session 1"
        description = "A test session"

        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO sessions (id, name, project_id, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                (session_id, session_name, project_id, description, now, now)
            )
            conn.commit()

        # Retrieve sessions
        sessions = self.model.get_sessions()

        self.assertIn(session_id, sessions)
        self.assertEqual(sessions[session_id]['name'], session_name)
        self.assertEqual(sessions[session_id]['project_id'], project_id)

    def test_create_team(self):
        """Test team creation"""
        team_name = "Test Team"
        description = "A test team"

        team_id = self.model.create_team(team_name, None, description)

        # Verify team was created
        teams = self.model.get_teams()
        self.assertIn(team_id, teams)
        self.assertEqual(teams[team_id]['name'], team_name)
        self.assertEqual(teams[team_id]['description'], description)
        self.assertIsNone(teams[team_id]['session_id'])  # Teams are session-independent

    def test_create_agent(self):
        """Test agent creation"""
        # Create agent via database (simulating UI creation)
        agent_id = "agent_test_agent"
        agent_name = "Test Agent"

        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                'INSERT INTO agents (id, name, status, last_active) VALUES (?, ?, ?, ?)',
                (agent_id, agent_name, 'disconnected', now)
            )
            conn.commit()

        # Retrieve agents
        agents = self.model.get_agents()

        self.assertIn(agent_id, agents)
        self.assertEqual(agents[agent_id]['name'], agent_name)
        self.assertEqual(agents[agent_id]['status'], 'disconnected')

    def test_assign_agents_to_session(self):
        """Test assigning agents to sessions"""
        # Create prerequisites
        project_id = "test_project"
        session_id = "test_session"
        agent_id = "test_agent"

        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            # Create project
            cursor.execute(
                'INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)',
                (project_id, "Test Project", now, now)
            )

            # Create session
            cursor.execute(
                'INSERT INTO sessions (id, name, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                (session_id, "Test Session", project_id, now, now)
            )

            # Create agent
            cursor.execute(
                'INSERT INTO agents (id, name, status, last_active) VALUES (?, ?, ?, ?)',
                (agent_id, "Test Agent", 'disconnected', now)
            )
            conn.commit()

        # Test assignment
        self.model.assign_agents_to_session([agent_id], session_id)

        # Verify assignment
        agents = self.model.get_agents()
        self.assertEqual(agents[agent_id]['session_id'], session_id)

    def test_assign_agents_to_team(self):
        """Test assigning agents to teams"""
        # Create team and agent
        team_id = self.model.create_team("Test Team")
        agent_id = "test_agent"

        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                'INSERT INTO agents (id, name, status, last_active) VALUES (?, ?, ?, ?)',
                (agent_id, "Test Agent", 'disconnected', now)
            )
            conn.commit()

        # Test assignment
        self.model.assign_agents_to_team([agent_id], team_id)

        # Verify assignment
        agents = self.model.get_agents()
        self.assertEqual(agents[agent_id]['team_id'], team_id)

    def test_rename_agent(self):
        """Test agent renaming"""
        # Create agent
        agent_id = "test_agent"
        original_name = "Original Agent"
        new_name = "Renamed Agent"

        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                'INSERT INTO agents (id, name, status, last_active) VALUES (?, ?, ?, ?)',
                (agent_id, original_name, 'disconnected', now)
            )
            conn.commit()

        # Test rename
        self.model.rename_agent(agent_id, new_name)

        # Verify rename
        agents = self.model.get_agents()
        self.assertEqual(agents[agent_id]['name'], new_name)

    def test_caching_functionality(self):
        """Test that caching works correctly"""
        # Create some data
        team_id = self.model.create_team("Cached Team")

        # First call should populate cache
        teams1 = self.model.get_teams()

        # Second call should use cache
        teams2 = self.model.get_teams()

        # Should be identical objects (cached)
        self.assertEqual(teams1, teams2)
        self.assertIn(team_id, teams1)

    def test_cache_clearing(self):
        """Test cache clearing functionality"""
        # Create data and populate cache
        team_id = self.model.create_team("Test Team")
        teams_before = self.model.get_teams()

        # Clear cache
        self.model.clear_cache()

        # Verify cache is empty (by checking internal cache structures)
        self.assertEqual(len(self.model.teams_cache), 0)
        self.assertEqual(len(self.model.agents_cache), 0)
        self.assertEqual(len(self.model.sessions_cache), 0)
        self.assertEqual(len(self.model.projects_cache), 0)

    def test_connection_pooling(self):
        """Test that connection pooling works"""
        # Test multiple concurrent connections
        results = []

        def get_teams():
            teams = self.model.get_teams()
            results.append(len(teams))

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=get_teams)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # All should complete successfully
        self.assertEqual(len(results), 5)

    def test_soft_delete(self):
        """Test soft delete functionality"""
        # Create team
        team_id = self.model.create_team("Delete Me")

        # Verify it exists
        teams_before = self.model.get_teams()
        self.assertIn(team_id, teams_before)

        # Soft delete
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE teams SET deleted_at = ? WHERE id = ?',
                (datetime.now().isoformat(), team_id)
            )
            conn.commit()

        # Clear cache to force reload
        self.model.clear_cache()

        # Verify it's not returned in normal queries
        teams_after = self.model.get_teams()
        self.assertNotIn(team_id, teams_after)

    def test_foreign_key_constraints(self):
        """Test foreign key relationships"""
        # Create project and session
        project_id = "fk_project"
        session_id = "fk_session"

        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            cursor.execute(
                'INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)',
                (project_id, "FK Project", now, now)
            )

            cursor.execute(
                'INSERT INTO sessions (id, name, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                (session_id, "FK Session", project_id, now, now)
            )
            conn.commit()

        # Create agent assigned to session
        agent_id = "fk_agent"
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO agents (id, name, session_id, status, last_active) VALUES (?, ?, ?, ?, ?)',
                (agent_id, "FK Agent", session_id, 'connected', now)
            )
            conn.commit()

        # Verify relationships
        agents = self.model.get_agents()
        sessions = self.model.get_sessions()

        self.assertEqual(agents[agent_id]['session_id'], session_id)
        self.assertEqual(sessions[session_id]['project_id'], project_id)

    def test_data_integrity(self):
        """Test data integrity and validation"""
        # Test unique constraints
        team_name = "Unique Team"
        team_id1 = self.model.create_team(team_name)

        # Should raise error for duplicate name
        with self.assertRaises(sqlite3.IntegrityError):
            self.model.create_team(team_name)

    def test_concurrent_operations(self):
        """Test concurrent database operations"""
        results = []

        def create_teams():
            try:
                for i in range(5):
                    team_id = self.model.create_team(f"Concurrent Team {threading.current_thread().ident}_{i}")
                    results.append(team_id)
                    time.sleep(0.01)  # Small delay to test concurrency
            except Exception as e:
                results.append(f"Error: {e}")

        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=create_teams)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Count successful creations
        successful_creations = [r for r in results if not str(r).startswith("Error")]
        self.assertGreater(len(successful_creations), 0)

        # Verify teams were created
        teams = self.model.get_teams()
        for team_id in successful_creations:
            self.assertIn(team_id, teams)


if __name__ == '__main__':
    unittest.main(verbosity=2)