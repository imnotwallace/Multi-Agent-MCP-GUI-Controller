#!/usr/bin/env python3
"""
Basic functionality test - Simple test without cleanup issues
"""
import unittest
import sys
import os
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBasicFunctionality(unittest.TestCase):
    """Basic functionality tests"""

    def test_imports_work(self):
        """Test that imports work correctly"""
        try:
            from main import CachedMCPDataModel, PerformantMCPView, UnifiedDialog
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Import failed: {e}")

    def test_database_creation(self):
        """Test database can be created"""
        try:
            from main import CachedMCPDataModel
            model = CachedMCPDataModel(":memory:")
            self.assertIsNotNone(model)
        except Exception as e:
            self.fail(f"Database creation failed: {e}")

    def test_basic_operations(self):
        """Test basic CRUD operations"""
        try:
            from main import CachedMCPDataModel
            model = CachedMCPDataModel(":memory:")

            # Test getting empty data
            projects = model.get_projects()
            sessions = model.get_sessions()
            agents = model.get_agents()
            teams = model.get_teams()

            self.assertIsInstance(projects, dict)
            self.assertIsInstance(sessions, dict)
            self.assertIsInstance(agents, dict)
            self.assertIsInstance(teams, dict)

            # Test creating team
            team_id = model.create_team("Test Team", None, "Test description")
            self.assertIsNotNone(team_id)

            # Test retrieving team
            teams_after = model.get_teams()
            self.assertIn(team_id, teams_after)

        except Exception as e:
            self.fail(f"Basic operations failed: {e}")

    def test_team_to_session_assignment_core_logic(self):
        """Test the core logic of team-to-session assignment"""
        try:
            from main import CachedMCPDataModel
            from datetime import datetime

            model = CachedMCPDataModel(":memory:")

            # Set up test data
            with model.pool.get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()

                # Create project
                cursor.execute('INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)',
                             ("test_proj", "Test Project", now, now))

                # Create session
                cursor.execute('INSERT INTO sessions (id, name, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                             ("test_sess", "Test Session", "test_proj", now, now))

                # Create team
                team_id = model.create_team("Test Team", None, "Test team")

                # Create agents
                cursor.execute('INSERT INTO agents (id, name, team_id, status, last_active) VALUES (?, ?, ?, ?, ?)',
                             ("agent1", "Team Agent 1", team_id, 'disconnected', now))
                cursor.execute('INSERT INTO agents (id, name, team_id, status, last_active) VALUES (?, ?, ?, ?, ?)',
                             ("agent2", "Team Agent 2", team_id, 'disconnected', now))
                cursor.execute('INSERT INTO agents (id, name, session_id, status, last_active) VALUES (?, ?, ?, ?, ?)',
                             ("agent3", "Solo Agent", "test_sess", 'connected', now))

                conn.commit()

            # Test the assignment logic
            with model.pool.get_connection() as conn:
                cursor = conn.cursor()

                # Disconnect non-team agents from target session
                cursor.execute('UPDATE agents SET session_id = NULL WHERE session_id = ? AND team_id != ?',
                             ("test_sess", team_id))

                # Connect team agents to session
                cursor.execute('UPDATE agents SET session_id = ? WHERE team_id = ?',
                             ("test_sess", team_id))

                conn.commit()

            # Verify results
            agents = model.get_agents()

            # Team agents should be in session
            self.assertEqual(agents["agent1"]['session_id'], "test_sess")
            self.assertEqual(agents["agent2"]['session_id'], "test_sess")

            # Solo agent should be disconnected
            self.assertIsNone(agents["agent3"]['session_id'])

            # Team membership should remain unchanged
            self.assertEqual(agents["agent1"]['team_id'], team_id)
            self.assertEqual(agents["agent2"]['team_id'], team_id)

        except Exception as e:
            self.fail(f"Team assignment logic test failed: {e}")

    def test_sorting_logic(self):
        """Test sorting logic without UI components"""
        try:
            # Test data
            test_data = [
                ("zebra", "zebra_item", ["Zebra", "Session A", "Team Z", "connected"]),
                ("alpha", "alpha_item", ["Alpha", "Session B", "Team A", "disconnected"]),
                ("beta", "beta_item", ["Beta", "", "Team B", "connecting"]),
            ]

            # Test sorting by name (index 0)
            sorted_by_name = sorted(test_data, key=lambda x: x[2][0].lower())
            names = [item[2][0] for item in sorted_by_name]
            self.assertEqual(names, ["Alpha", "Beta", "Zebra"])

            # Test sorting by session (index 1, handling empty strings)
            sorted_by_session = sorted(test_data, key=lambda x: x[2][1].lower() if x[2][1] else "")
            sessions = [item[2][1] for item in sorted_by_session]
            # Empty string should come first
            self.assertEqual(sessions[0], "")

            # Test reverse sorting
            sorted_reverse = sorted(test_data, key=lambda x: x[2][0].lower(), reverse=True)
            names_reverse = [item[2][0] for item in sorted_reverse]
            self.assertEqual(names_reverse, ["Zebra", "Beta", "Alpha"])

        except Exception as e:
            self.fail(f"Sorting logic test failed: {e}")

    def test_application_startup_simulation(self):
        """Test simulating application startup without GUI"""
        try:
            from main import CachedMCPDataModel

            # Simulate application startup
            model = CachedMCPDataModel(":memory:")

            # Load initial data (should not crash)
            projects = model.get_projects()
            sessions = model.get_sessions()
            agents = model.get_agents()
            teams = model.get_teams()

            # Should all be empty initially
            self.assertEqual(len(projects), 0)
            self.assertEqual(len(sessions), 0)
            self.assertEqual(len(agents), 0)
            self.assertEqual(len(teams), 0)

            # Create some initial data
            team_id = model.create_team("Default Team", None, "Default team")
            teams_after = model.get_teams()
            self.assertEqual(len(teams_after), 1)

        except Exception as e:
            self.fail(f"Application startup simulation failed: {e}")

    def test_new_team_assignment_button_logic(self):
        """Test the logic that would be behind the new team assignment button"""
        try:
            from main import CachedMCPDataModel
            from datetime import datetime

            model = CachedMCPDataModel(":memory:")

            # Setup: Create comprehensive test scenario
            with model.pool.get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()

                # Create projects and sessions
                cursor.execute('INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)',
                             ("proj1", "Project Alpha", now, now))
                cursor.execute('INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)',
                             ("proj2", "Project Beta", now, now))

                cursor.execute('INSERT INTO sessions (id, name, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                             ("sess1", "Session Alpha", "proj1", now, now))
                cursor.execute('INSERT INTO sessions (id, name, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                             ("sess2", "Session Beta", "proj2", now, now))

                conn.commit()

            # Create teams
            team_alpha_id = model.create_team("Alpha Team", None, "Alpha operations team")
            team_beta_id = model.create_team("Beta Team", None, "Beta operations team")

            # Create agents
            with model.pool.get_connection() as conn:
                cursor = conn.cursor()

                # Alpha team agents
                cursor.execute('INSERT INTO agents (id, name, team_id, status, last_active) VALUES (?, ?, ?, ?, ?)',
                             ("agent_a1", "Alpha Agent 1", team_alpha_id, 'disconnected', now))
                cursor.execute('INSERT INTO agents (id, name, team_id, status, last_active) VALUES (?, ?, ?, ?, ?)',
                             ("agent_a2", "Alpha Agent 2", team_alpha_id, 'disconnected', now))

                # Beta team agents
                cursor.execute('INSERT INTO agents (id, name, team_id, status, last_active) VALUES (?, ?, ?, ?, ?)',
                             ("agent_b1", "Beta Agent 1", team_beta_id, 'disconnected', now))

                # Solo agents currently in sessions
                cursor.execute('INSERT INTO agents (id, name, session_id, status, last_active) VALUES (?, ?, ?, ?, ?)',
                             ("agent_s1", "Solo Agent 1", "sess1", 'connected', now))
                cursor.execute('INSERT INTO agents (id, name, session_id, status, last_active) VALUES (?, ?, ?, ?, ?)',
                             ("agent_s2", "Solo Agent 2", "sess1", 'connected', now))

                conn.commit()

            # Test 1: Assign Alpha team to sess1
            # This should disconnect solo agents and connect Alpha team
            target_session = "sess1"
            target_team_id = team_alpha_id

            with model.pool.get_connection() as conn:
                cursor = conn.cursor()

                # Get agents in target team
                cursor.execute('SELECT id, name, session_id FROM agents WHERE team_id = ? AND deleted_at IS NULL',
                             (target_team_id,))
                team_agents = cursor.fetchall()

                # Get non-team agents in target session
                cursor.execute('SELECT id, name, team_id FROM agents WHERE session_id = ? AND team_id != ? AND deleted_at IS NULL',
                             (target_session, target_team_id))
                current_session_agents = cursor.fetchall()

                disconnected_count = 0
                connected_count = 0

                # Disconnect current session agents (not from target team)
                for agent_id, agent_name, agent_team_id in current_session_agents:
                    cursor.execute('UPDATE agents SET session_id = NULL WHERE id = ?', (agent_id,))
                    disconnected_count += 1

                # Connect team agents to session
                for agent_id, agent_name, current_session_id in team_agents:
                    if current_session_id != target_session:
                        cursor.execute('UPDATE agents SET session_id = ? WHERE id = ?',
                                     (target_session, agent_id))
                        connected_count += 1

                conn.commit()

            # Verify results
            agents = model.get_agents()

            # Alpha team agents should be in sess1
            self.assertEqual(agents["agent_a1"]['session_id'], "sess1")
            self.assertEqual(agents["agent_a2"]['session_id'], "sess1")

            # Solo agents should be disconnected
            self.assertIsNone(agents["agent_s1"]['session_id'])
            self.assertIsNone(agents["agent_s2"]['session_id'])

            # Beta team should be unchanged
            self.assertIsNone(agents["agent_b1"]['session_id'])

            # Team memberships should remain intact
            self.assertEqual(agents["agent_a1"]['team_id'], team_alpha_id)
            self.assertEqual(agents["agent_a2"]['team_id'], team_alpha_id)
            self.assertEqual(agents["agent_b1"]['team_id'], team_beta_id)

            print("Team assignment logic test passed!")

        except Exception as e:
            self.fail(f"Team assignment button logic failed: {e}")


if __name__ == '__main__':
    unittest.main(verbosity=2)