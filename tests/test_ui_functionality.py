#!/usr/bin/env python3
"""
Test suite for UI functionality and user interactions
Tests the PerformantMCPView class and dialog operations
"""
import unittest
import tkinter as tk
import os
import tempfile
import shutil
import sqlite3
from datetime import datetime
import sys
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path to import main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import CachedMCPDataModel, PerformantMCPView, UnifiedDialog


class TestUIFunctionality(unittest.TestCase):
    """Test cases for UI functionality"""

    def setUp(self):
        """Set up test environment"""
        # Create temporary directory for test database
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_ui_mcp.db")

        # Create model instance with test database
        self.model = CachedMCPDataModel(self.test_db_path)

        # Set up test data
        self.setup_test_data()

    def tearDown(self):
        """Clean up test environment"""
        # Close any open connections
        if hasattr(self.model, 'pool'):
            self.model.pool.close()

        # Remove temporary directory
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def setup_test_data(self):
        """Set up test data in database"""
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            # Create test projects
            cursor.execute(
                'INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                ("proj_test1", "Test Project 1", "First test project", now, now)
            )
            cursor.execute(
                'INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                ("proj_test2", "Test Project 2", "Second test project", now, now)
            )

            # Create test sessions
            cursor.execute(
                'INSERT INTO sessions (id, name, project_id, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                ("sess_test1", "Test Session 1", "proj_test1", "First test session", now, now)
            )
            cursor.execute(
                'INSERT INTO sessions (id, name, project_id, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                ("sess_test2", "Test Session 2", "proj_test2", "Second test session", now, now)
            )

            # Create test teams
            team1_id = self.model.create_team("Alpha Team", None, "First team")
            team2_id = self.model.create_team("Beta Team", None, "Second team")

            # Create test agents
            cursor.execute(
                'INSERT INTO agents (id, name, team_id, session_id, status, last_active) VALUES (?, ?, ?, ?, ?, ?)',
                ("agent_alpha1", "Alpha Agent 1", team1_id, None, 'disconnected', now)
            )
            cursor.execute(
                'INSERT INTO agents (id, name, team_id, session_id, status, last_active) VALUES (?, ?, ?, ?, ?, ?)',
                ("agent_alpha2", "Alpha Agent 2", team1_id, None, 'disconnected', now)
            )
            cursor.execute(
                'INSERT INTO agents (id, name, team_id, session_id, status, last_active) VALUES (?, ?, ?, ?, ?, ?)',
                ("agent_beta1", "Beta Agent 1", team2_id, "sess_test1", 'connected', now)
            )
            cursor.execute(
                'INSERT INTO agents (id, name, team_id, session_id, status, last_active) VALUES (?, ?, ?, ?, ?, ?)',
                ("agent_solo", "Solo Agent", None, "sess_test2", 'connected', now)
            )

            conn.commit()


class TestUnifiedDialog(unittest.TestCase):
    """Test cases for UnifiedDialog"""

    def setUp(self):
        """Set up test environment"""
        # Create a root window for testing
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the window during testing

    def tearDown(self):
        """Clean up test environment"""
        if self.root:
            self.root.destroy()

    def test_dialog_creation(self):
        """Test dialog creation with basic parameters"""
        dialog = UnifiedDialog(
            self.root,
            "Test Dialog",
            "Name:",
            "Description:"
        )

        # Check dialog properties
        self.assertEqual(dialog.dialog.title(), "Test Dialog")
        self.assertIsNotNone(dialog.name_entry)
        self.assertIsNotNone(dialog.description_text)

    def test_dialog_with_extra_fields(self):
        """Test dialog creation with extra fields"""
        extra_fields = {
            'project': {
                'label': 'Project:',
                'type': 'combobox',
                'values': ['Project 1', 'Project 2'],
                'default': 'Project 1'
            }
        }

        dialog = UnifiedDialog(
            self.root,
            "Test Dialog",
            "Name:",
            "Description:",
            extra_fields=extra_fields
        )

        # Check extra field was created
        self.assertIn('project', dialog.extra_widgets)
        self.assertEqual(dialog.extra_widgets['project'].get(), 'Project 1')


class TestTeamAssignmentFunctionality(unittest.TestCase):
    """Test cases for the new team assignment functionality"""

    def setUp(self):
        """Set up test environment"""
        # Create temporary directory for test database
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_team_assign.db")

        # Create model instance with test database
        self.model = CachedMCPDataModel(self.test_db_path)
        self.setup_test_data()

    def tearDown(self):
        """Clean up test environment"""
        if hasattr(self.model, 'pool'):
            self.model.pool.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def setup_test_data(self):
        """Set up comprehensive test data for team assignment"""
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            # Create test projects
            cursor.execute(
                'INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                ("proj_alpha", "Alpha Project", "Alpha project description", now, now)
            )
            cursor.execute(
                'INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                ("proj_beta", "Beta Project", "Beta project description", now, now)
            )

            # Create test sessions
            cursor.execute(
                'INSERT INTO sessions (id, name, project_id, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                ("sess_alpha1", "Alpha Session 1", "proj_alpha", "Alpha session 1", now, now)
            )
            cursor.execute(
                'INSERT INTO sessions (id, name, project_id, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                ("sess_alpha2", "Alpha Session 2", "proj_alpha", "Alpha session 2", now, now)
            )
            cursor.execute(
                'INSERT INTO sessions (id, name, project_id, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                ("sess_beta1", "Beta Session 1", "proj_beta", "Beta session 1", now, now)
            )

            # Create test teams
            self.team_alpha_id = self.model.create_team("Alpha Team", None, "Alpha team")
            self.team_beta_id = self.model.create_team("Beta Team", None, "Beta team")

            # Create test agents
            # Alpha team agents (currently disconnected)
            cursor.execute(
                'INSERT INTO agents (id, name, team_id, session_id, status, last_active) VALUES (?, ?, ?, ?, ?, ?)',
                ("agent_alpha1", "Alpha Agent 1", self.team_alpha_id, None, 'disconnected', now)
            )
            cursor.execute(
                'INSERT INTO agents (id, name, team_id, session_id, status, last_active) VALUES (?, ?, ?, ?, ?, ?)',
                ("agent_alpha2", "Alpha Agent 2", self.team_alpha_id, None, 'disconnected', now)
            )
            cursor.execute(
                'INSERT INTO agents (id, name, team_id, session_id, status, last_active) VALUES (?, ?, ?, ?, ?, ?)',
                ("agent_alpha3", "Alpha Agent 3", self.team_alpha_id, "sess_beta1", 'connected', now)
            )

            # Beta team agents (currently in various sessions)
            cursor.execute(
                'INSERT INTO agents (id, name, team_id, session_id, status, last_active) VALUES (?, ?, ?, ?, ?, ?)',
                ("agent_beta1", "Beta Agent 1", self.team_beta_id, "sess_alpha1", 'connected', now)
            )
            cursor.execute(
                'INSERT INTO agents (id, name, team_id, session_id, status, last_active) VALUES (?, ?, ?, ?, ?, ?)',
                ("agent_beta2", "Beta Agent 2", self.team_beta_id, None, 'disconnected', now)
            )

            # Solo agents (not in teams, currently in sessions)
            cursor.execute(
                'INSERT INTO agents (id, name, team_id, session_id, status, last_active) VALUES (?, ?, ?, ?, ?, ?)',
                ("agent_solo1", "Solo Agent 1", None, "sess_alpha1", 'connected', now)
            )
            cursor.execute(
                'INSERT INTO agents (id, name, team_id, session_id, status, last_active) VALUES (?, ?, ?, ?, ?, ?)',
                ("agent_solo2", "Solo Agent 2", None, "sess_alpha2", 'connected', now)
            )

            conn.commit()

    def test_team_assignment_logic_basic(self):
        """Test basic team to session assignment logic"""
        # Test assigning Alpha team to sess_alpha1
        # This should:
        # 1. Disconnect agent_solo1 (currently in sess_alpha1)
        # 2. Connect agent_alpha1, agent_alpha2 to sess_alpha1
        # 3. Move agent_alpha3 from sess_beta1 to sess_alpha1

        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()

            # Get agents in Alpha team before assignment
            cursor.execute('SELECT id, name, session_id FROM agents WHERE team_id = ? AND deleted_at IS NULL',
                         (self.team_alpha_id,))
            alpha_agents_before = cursor.fetchall()

            # Get agents currently in sess_alpha1 (not in Alpha team)
            cursor.execute('SELECT id, name, team_id FROM agents WHERE session_id = ? AND team_id != ? AND deleted_at IS NULL',
                         ("sess_alpha1", self.team_alpha_id))
            current_session_agents = cursor.fetchall()

            # Execute the assignment logic (simulating the UI method)
            disconnected_count = 0
            connected_count = 0

            # Disconnect current agents in session (not from our team)
            for agent_id, agent_name, agent_team_id in current_session_agents:
                cursor.execute('UPDATE agents SET session_id = NULL, updated_at = ? WHERE id = ?',
                             (datetime.now().isoformat(), agent_id))
                disconnected_count += 1

            # Connect all team agents to target session
            for agent_id, agent_name, current_session_id in alpha_agents_before:
                if current_session_id != "sess_alpha1":
                    cursor.execute('UPDATE agents SET session_id = ?, updated_at = ? WHERE id = ?',
                                 ("sess_alpha1", datetime.now().isoformat(), agent_id))
                    connected_count += 1

            conn.commit()

        # Verify results
        self.assertEqual(disconnected_count, 1)  # agent_solo1 should be disconnected
        self.assertEqual(connected_count, 3)     # All 3 alpha agents should be connected

        # Verify final state
        agents = self.model.get_agents()

        # All Alpha team agents should be in sess_alpha1
        for agent_id in ["agent_alpha1", "agent_alpha2", "agent_alpha3"]:
            self.assertEqual(agents[agent_id]['session_id'], "sess_alpha1")

        # Solo agent should be disconnected
        self.assertIsNone(agents["agent_solo1"]['session_id'])

        # Other agents should be unchanged
        self.assertEqual(agents["agent_beta1"]['session_id'], "sess_alpha1")  # Was already there, but different team
        self.assertIsNone(agents["agent_beta2"]['session_id'])  # Was disconnected
        self.assertEqual(agents["agent_solo2"]['session_id'], "sess_alpha2")  # Different session, unchanged

    def test_team_assignment_edge_cases(self):
        """Test edge cases for team assignment"""
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()

            # Test 1: Assign team to session where some agents are already assigned
            # Alpha agents: agent_alpha1, agent_alpha2 (disconnected), agent_alpha3 (in sess_beta1)

            # First, connect agent_alpha1 to sess_alpha2
            cursor.execute('UPDATE agents SET session_id = ? WHERE id = ?',
                         ("sess_alpha2", "agent_alpha1"))
            conn.commit()

        # Clear cache to get fresh data
        self.model.clear_cache()

        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()

            # Now assign Alpha team to sess_alpha2
            # agent_alpha1 is already there, so should not be updated
            # agent_solo2 should be disconnected

            # Get current state
            cursor.execute('SELECT id, name, session_id FROM agents WHERE team_id = ? AND deleted_at IS NULL',
                         (self.team_alpha_id,))
            alpha_agents = cursor.fetchall()

            cursor.execute('SELECT id, name, team_id FROM agents WHERE session_id = ? AND team_id != ? AND deleted_at IS NULL',
                         ("sess_alpha2", self.team_alpha_id))
            current_session_agents = cursor.fetchall()

            disconnected_count = 0
            connected_count = 0

            # Disconnect non-team agents
            for agent_id, agent_name, agent_team_id in current_session_agents:
                cursor.execute('UPDATE agents SET session_id = NULL WHERE id = ?', (agent_id,))
                disconnected_count += 1

            # Connect team agents
            for agent_id, agent_name, current_session_id in alpha_agents:
                if current_session_id != "sess_alpha2":
                    cursor.execute('UPDATE agents SET session_id = ? WHERE id = ?',
                                 ("sess_alpha2", agent_id))
                    connected_count += 1

            conn.commit()

        # Verify results
        self.assertEqual(disconnected_count, 1)  # agent_solo2 disconnected
        self.assertEqual(connected_count, 2)     # agent_alpha2, agent_alpha3 connected (alpha1 already there)

    def test_team_assignment_no_agents(self):
        """Test team assignment when team has no agents"""
        # Create empty team
        empty_team_id = self.model.create_team("Empty Team", None, "Team with no agents")

        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()

            # Try to assign empty team to a session
            cursor.execute('SELECT id, name, session_id FROM agents WHERE team_id = ? AND deleted_at IS NULL',
                         (empty_team_id,))
            team_agents = cursor.fetchall()

            # Should have no agents
            self.assertEqual(len(team_agents), 0)

    def test_session_clearing_logic(self):
        """Test that session is properly cleared before team assignment"""
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()

            # Put multiple agents in sess_beta1
            cursor.execute('UPDATE agents SET session_id = ? WHERE id IN (?, ?)',
                         ("sess_beta1", "agent_beta1", "agent_solo1"))
            conn.commit()

            # Verify they're there
            cursor.execute('SELECT COUNT(*) FROM agents WHERE session_id = ?', ("sess_beta1",))
            count_before = cursor.fetchone()[0]
            self.assertGreater(count_before, 0)

            # Now assign Alpha team to sess_beta1
            # This should disconnect all current agents and connect Alpha team

            # Get current agents in session (not from Alpha team)
            cursor.execute('SELECT id FROM agents WHERE session_id = ? AND team_id != ?',
                         ("sess_beta1", self.team_alpha_id))
            agents_to_disconnect = cursor.fetchall()

            # Disconnect them
            for (agent_id,) in agents_to_disconnect:
                cursor.execute('UPDATE agents SET session_id = NULL WHERE id = ?', (agent_id,))

            # Connect Alpha team
            cursor.execute('UPDATE agents SET session_id = ? WHERE team_id = ?',
                         ("sess_beta1", self.team_alpha_id))

            conn.commit()

        # Verify final state
        agents = self.model.get_agents()

        # Alpha team agents should be in sess_beta1
        alpha_agents = [a for a in agents.values() if a['team_id'] == self.team_alpha_id]
        for agent in alpha_agents:
            self.assertEqual(agent['session_id'], "sess_beta1")

        # Previously connected agents should be disconnected
        self.assertIsNone(agents["agent_beta1"]['session_id'])
        self.assertIsNone(agents["agent_solo1"]['session_id'])

    def test_data_consistency_after_assignment(self):
        """Test that data remains consistent after team assignment operations"""
        # Perform multiple team assignments
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()

            # Assign Alpha team to sess_alpha1
            cursor.execute('UPDATE agents SET session_id = NULL WHERE session_id = ? AND team_id != ?',
                         ("sess_alpha1", self.team_alpha_id))
            cursor.execute('UPDATE agents SET session_id = ? WHERE team_id = ?',
                         ("sess_alpha1", self.team_alpha_id))

            # Assign Beta team to sess_alpha2
            cursor.execute('UPDATE agents SET session_id = NULL WHERE session_id = ? AND team_id != ?',
                         ("sess_alpha2", self.team_beta_id))
            cursor.execute('UPDATE agents SET session_id = ? WHERE team_id = ?',
                         ("sess_alpha2", self.team_beta_id))

            conn.commit()

        # Verify data consistency
        agents = self.model.get_agents()

        # Check that no agent is assigned to multiple sessions
        session_assignments = {}
        for agent_id, agent in agents.items():
            if agent['session_id']:
                if agent['session_id'] not in session_assignments:
                    session_assignments[agent['session_id']] = []
                session_assignments[agent['session_id']].append(agent_id)

        # Verify Alpha team is in sess_alpha1
        alpha_agents_in_session = [aid for aid in session_assignments.get("sess_alpha1", [])
                                 if agents[aid]['team_id'] == self.team_alpha_id]
        self.assertEqual(len(alpha_agents_in_session), 3)  # All Alpha agents

        # Verify Beta team is in sess_alpha2
        beta_agents_in_session = [aid for aid in session_assignments.get("sess_alpha2", [])
                                if agents[aid]['team_id'] == self.team_beta_id]
        self.assertEqual(len(beta_agents_in_session), 2)  # All Beta agents

        # Verify team memberships are unchanged
        for agent_id, agent in agents.items():
            if agent_id.startswith("agent_alpha"):
                self.assertEqual(agent['team_id'], self.team_alpha_id)
            elif agent_id.startswith("agent_beta"):
                self.assertEqual(agent['team_id'], self.team_beta_id)
            elif agent_id.startswith("agent_solo"):
                self.assertIsNone(agent['team_id'])


if __name__ == '__main__':
    # Run tests with high verbosity
    unittest.main(verbosity=2)