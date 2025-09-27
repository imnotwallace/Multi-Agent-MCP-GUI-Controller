#!/usr/bin/env python3
"""
Core functionality test - Tests key features without threading complications
"""
import unittest
import sys
import os
import tempfile
import shutil
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from archive.main import CachedMCPDataModel


class TestCoreFunctionality(unittest.TestCase):
    """Test core functionality"""

    def setUp(self):
        """Set up test database"""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_core.db")
        self.model = CachedMCPDataModel(self.test_db_path)

    def tearDown(self):
        """Clean up"""
        if hasattr(self.model, 'pool'):
            self.model.pool.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_database_initialization(self):
        """Test database creation and schema"""
        self.assertTrue(os.path.exists(self.test_db_path))

        # Test that basic queries work
        projects = self.model.get_projects()
        sessions = self.model.get_sessions()
        agents = self.model.get_agents()
        teams = self.model.get_teams()

        self.assertIsInstance(projects, dict)
        self.assertIsInstance(sessions, dict)
        self.assertIsInstance(agents, dict)
        self.assertIsInstance(teams, dict)

    def test_team_creation_and_retrieval(self):
        """Test creating and retrieving teams"""
        # Create a team
        team_name = "Test Team Alpha"
        team_description = "A test team for Alpha operations"

        team_id = self.model.create_team(team_name, None, team_description)
        self.assertIsNotNone(team_id)
        self.assertTrue(team_id.startswith("team_"))

        # Retrieve teams
        teams = self.model.get_teams()
        self.assertIn(team_id, teams)
        self.assertEqual(teams[team_id]['name'], team_name)
        self.assertEqual(teams[team_id]['description'], team_description)

    def test_project_and_session_workflow(self):
        """Test creating projects and sessions"""
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            # Create project
            project_id = "proj_test"
            cursor.execute(
                'INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                (project_id, "Test Project", "Test description", now, now)
            )

            # Create session
            session_id = "sess_test"
            cursor.execute(
                'INSERT INTO sessions (id, name, project_id, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                (session_id, "Test Session", project_id, "Test session", now, now)
            )

            # Create agent
            agent_id = "agent_test"
            cursor.execute(
                'INSERT INTO agents (id, name, status, last_active) VALUES (?, ?, ?, ?)',
                (agent_id, "Test Agent", 'disconnected', now)
            )

            conn.commit()

        # Test retrieval
        projects = self.model.get_projects()
        sessions = self.model.get_sessions()
        agents = self.model.get_agents()

        self.assertIn(project_id, projects)
        self.assertIn(session_id, sessions)
        self.assertIn(agent_id, agents)

        # Test relationships
        self.assertEqual(sessions[session_id]['project_id'], project_id)

    def test_agent_team_assignment(self):
        """Test assigning agents to teams"""
        # Create team
        team_id = self.model.create_team("Assignment Team", None, "For testing assignments")

        # Create agent
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            agent_id = "agent_assign_test"
            cursor.execute(
                'INSERT INTO agents (id, name, status, last_active) VALUES (?, ?, ?, ?)',
                (agent_id, "Assignment Test Agent", 'disconnected', now)
            )
            conn.commit()

        # Test assignment
        self.model.assign_agents_to_team([agent_id], team_id)

        # Verify assignment
        agents = self.model.get_agents()
        self.assertEqual(agents[agent_id]['team_id'], team_id)

    def test_agent_session_assignment(self):
        """Test assigning agents to sessions"""
        # Create prerequisites
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            # Project
            project_id = "proj_assign"
            cursor.execute(
                'INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)',
                (project_id, "Assignment Project", now, now)
            )

            # Session
            session_id = "sess_assign"
            cursor.execute(
                'INSERT INTO sessions (id, name, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                (session_id, "Assignment Session", project_id, now, now)
            )

            # Agent
            agent_id = "agent_session_test"
            cursor.execute(
                'INSERT INTO agents (id, name, status, last_active) VALUES (?, ?, ?, ?)',
                (agent_id, "Session Test Agent", 'disconnected', now)
            )

            conn.commit()

        # Test assignment
        self.model.assign_agents_to_session([agent_id], session_id)

        # Verify assignment
        agents = self.model.get_agents()
        self.assertEqual(agents[agent_id]['session_id'], session_id)

    def test_team_to_session_assignment_logic(self):
        """Test the new team-to-session assignment logic"""
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            # Create project and sessions
            cursor.execute('INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)',
                         ("proj_team_assign", "Team Assignment Project", now, now))

            cursor.execute('INSERT INTO sessions (id, name, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                         ("sess_target", "Target Session", "proj_team_assign", now, now))

            # Create team
            team_id = self.model.create_team("Assignment Team", None, "Team for assignment testing")

            # Create team agents
            team_agents = ["agent_team1", "agent_team2", "agent_team3"]
            for agent_id in team_agents:
                cursor.execute('INSERT INTO agents (id, name, team_id, status, last_active) VALUES (?, ?, ?, ?, ?)',
                             (agent_id, f"Team Agent {agent_id[-1]}", team_id, 'disconnected', now))

            # Create non-team agents in target session
            cursor.execute('INSERT INTO agents (id, name, session_id, status, last_active) VALUES (?, ?, ?, ?, ?)',
                         ("agent_solo1", "Solo Agent 1", "sess_target", 'connected', now))
            cursor.execute('INSERT INTO agents (id, name, session_id, status, last_active) VALUES (?, ?, ?, ?, ?)',
                         ("agent_solo2", "Solo Agent 2", "sess_target", 'connected', now))

            conn.commit()

        # Execute team-to-session assignment logic
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()

            # Get current agents in target session (not from our team)
            cursor.execute('SELECT id FROM agents WHERE session_id = ? AND team_id != ?',
                         ("sess_target", team_id))
            agents_to_disconnect = cursor.fetchall()

            # Disconnect them
            for (agent_id,) in agents_to_disconnect:
                cursor.execute('UPDATE agents SET session_id = NULL WHERE id = ?', (agent_id,))

            # Connect all team agents to target session
            cursor.execute('UPDATE agents SET session_id = ? WHERE team_id = ?',
                         ("sess_target", team_id))

            conn.commit()

        # Verify results
        agents = self.model.get_agents()

        # All team agents should be in target session
        for agent_id in team_agents:
            self.assertEqual(agents[agent_id]['session_id'], "sess_target")
            self.assertEqual(agents[agent_id]['team_id'], team_id)

        # Solo agents should be disconnected
        self.assertIsNone(agents["agent_solo1"]['session_id'])
        self.assertIsNone(agents["agent_solo2"]['session_id'])

    def test_data_consistency(self):
        """Test data consistency after operations"""
        # Create comprehensive test scenario
        team_id = self.model.create_team("Consistency Team", None, "For consistency testing")

        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            # Create project and session
            cursor.execute('INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)',
                         ("proj_consistency", "Consistency Project", now, now))
            cursor.execute('INSERT INTO sessions (id, name, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                         ("sess_consistency", "Consistency Session", "proj_consistency", now, now))

            # Create agents
            cursor.execute('INSERT INTO agents (id, name, team_id, status, last_active) VALUES (?, ?, ?, ?, ?)',
                         ("agent_consist1", "Consistent Agent 1", team_id, 'disconnected', now))
            cursor.execute('INSERT INTO agents (id, name, team_id, status, last_active) VALUES (?, ?, ?, ?, ?)',
                         ("agent_consist2", "Consistent Agent 2", team_id, 'disconnected', now))

            conn.commit()

        # Perform assignment
        self.model.assign_agents_to_session(["agent_consist1", "agent_consist2"], "sess_consistency")

        # Verify data consistency
        agents = self.model.get_agents()
        teams = self.model.get_teams()
        sessions = self.model.get_sessions()

        # Agents should maintain team membership while being in session
        self.assertEqual(agents["agent_consist1"]['team_id'], team_id)
        self.assertEqual(agents["agent_consist1"]['session_id'], "sess_consistency")
        self.assertEqual(agents["agent_consist2"]['team_id'], team_id)
        self.assertEqual(agents["agent_consist2"]['session_id'], "sess_consistency")

        # Team should still exist
        self.assertIn(team_id, teams)

        # Session should still exist
        self.assertIn("sess_consistency", sessions)

    def test_cache_functionality(self):
        """Test that caching doesn't break basic operations"""
        # Create data
        team_id = self.model.create_team("Cache Test Team", None, "For cache testing")

        # Get data (should populate cache)
        teams1 = self.model.get_teams()
        self.assertIn(team_id, teams1)

        # Get data again (should use cache)
        teams2 = self.model.get_teams()
        self.assertEqual(teams1, teams2)

        # Clear cache
        self.model.clear_cache()

        # Get data again (should repopulate cache)
        teams3 = self.model.get_teams()
        self.assertEqual(teams1, teams3)

if __name__ == '__main__':
    unittest.main(verbosity=2)