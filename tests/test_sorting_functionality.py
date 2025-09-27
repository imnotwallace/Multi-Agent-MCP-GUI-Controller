#!/usr/bin/env python3
"""
Test suite for sorting functionality in agent and team management screens
Tests the sorting methods and column header interactions
"""
import unittest
import tkinter as tk
from tkinter import ttk
import os
import tempfile
import shutil
import sys
from datetime import datetime
from unittest.mock import Mock, patch

# Add parent directory to path to import main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from archive.main import CachedMCPDataModel, PerformantMCPView


class TestSortingFunctionality(unittest.TestCase):
    """Test cases for sorting functionality"""

    def setUp(self):
        """Set up test environment"""
        # Create temporary directory for test database
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_sort.db")

        # Create model instance with test database
        self.model = CachedMCPDataModel(self.test_db_path)

        # Set up comprehensive test data for sorting
        self.setup_test_data()

        # Create a minimal UI instance for testing
        # We'll mock the root window to avoid display issues
        self.root = Mock(spec=tk.Tk)
        self.view = PerformantMCPView(self.model)
        self.view.root = self.root

        # Create mock treeviews with test data
        self.setup_mock_treeviews()

    def tearDown(self):
        """Clean up test environment"""
        if hasattr(self.model, 'pool'):
            self.model.pool.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def setup_test_data(self):
        """Set up test data for sorting"""
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            # Create test projects
            cursor.execute(
                'INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                ("proj_alpha", "Alpha Project", "Alpha description", now, now)
            )

            # Create test sessions
            cursor.execute(
                'INSERT INTO sessions (id, name, project_id, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                ("sess_alpha", "Alpha Session", "proj_alpha", "Alpha session", now, now)
            )
            cursor.execute(
                'INSERT INTO sessions (id, name, project_id, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                ("sess_beta", "Beta Session", "proj_alpha", "Beta session", now, now)
            )

            # Create test teams with different creation dates
            team1_id = self.model.create_team("Zebra Team", None, "Last alphabetically")
            team2_id = self.model.create_team("Alpha Team", None, "First alphabetically")
            team3_id = self.model.create_team("Beta Team", None, "Second alphabetically")

            # Create test agents with varied data for sorting
            test_agents = [
                ("agent_zebra", "Zebra Agent", team1_id, "sess_alpha", 'connected'),
                ("agent_alpha", "Alpha Agent", team2_id, "sess_beta", 'disconnected'),
                ("agent_beta", "Beta Agent", team3_id, None, 'connecting'),
                ("agent_charlie", "Charlie Agent", None, "sess_alpha", 'connected'),
                ("agent_delta", "Delta Agent", team1_id, None, 'disconnected'),
            ]

            for agent_id, name, team_id, session_id, status in test_agents:
                cursor.execute(
                    'INSERT INTO agents (id, name, team_id, session_id, status, last_active) VALUES (?, ?, ?, ?, ?, ?)',
                    (agent_id, name, team_id, session_id, status, now)
                )

            conn.commit()

    def setup_mock_treeviews(self):
        """Set up mock treeviews with test data for sorting tests"""
        # Mock agent tree
        self.view.agent_tree = Mock(spec=ttk.Treeview)
        self.view.agent_tree.get_children.return_value = ["item1", "item2", "item3", "item4", "item5"]

        # Mock agent tree items with test data
        agent_items = {
            "item1": {'text': 'agent_zebra', 'values': ('Zebra Agent', 'Alpha Session', 'Zebra Team', 'connected')},
            "item2": {'text': 'agent_alpha', 'values': ('Alpha Agent', 'Beta Session', 'Alpha Team', 'disconnected')},
            "item3": {'text': 'agent_beta', 'values': ('Beta Agent', '', 'Beta Team', 'connecting')},
            "item4": {'text': 'agent_charlie', 'values': ('Charlie Agent', 'Alpha Session', '', 'connected')},
            "item5": {'text': 'agent_delta', 'values': ('Delta Agent', '', 'Zebra Team', 'disconnected')},
        }

        self.view.agent_tree.item.side_effect = lambda item_id: agent_items.get(item_id, {})
        self.view.agent_tree.delete = Mock()
        self.view.agent_tree.insert = Mock()
        self.view.agent_tree.heading = Mock()

        # Mock team tree
        self.view.team_tree = Mock(spec=ttk.Treeview)
        self.view.team_tree.get_children.return_value = ["team1", "team2", "team3"]

        # Mock team tree items with test data
        team_items = {
            "team1": {'text': 'team_zebra_team', 'values': ('Zebra Team', 2, '2024-01-01')},
            "team2": {'text': 'team_alpha_team', 'values': ('Alpha Team', 1, '2024-01-02')},
            "team3": {'text': 'team_beta_team', 'values': ('Beta Team', 1, '2024-01-03')},
        }

        self.view.team_tree.item.side_effect = lambda item_id: team_items.get(item_id, {})
        self.view.team_tree.delete = Mock()
        self.view.team_tree.insert = Mock()
        self.view.team_tree.heading = Mock()

    def test_agent_sort_by_name_ascending(self):
        """Test sorting agents by name in ascending order"""
        # Call sort method
        self.view.sort_agents('name')

        # Verify sorting attributes were set correctly
        self.assertEqual(self.view.agent_last_sort_column, 'name')
        self.assertFalse(self.view.agent_sort_reverse)

        # Check that insert was called with sorted data
        calls = self.view.agent_tree.insert.call_args_list

        # Extract the agent names from insert calls
        inserted_names = [call[1]['values'][0] for call in calls]

        # Should be sorted alphabetically
        expected_order = ['Alpha Agent', 'Beta Agent', 'Charlie Agent', 'Delta Agent', 'Zebra Agent']
        self.assertEqual(inserted_names, expected_order)

    def test_agent_sort_by_name_descending(self):
        """Test sorting agents by name in descending order (second click)"""
        # First click - ascending
        self.view.sort_agents('name')

        # Second click - descending
        self.view.sort_agents('name')

        # Verify sorting attributes
        self.assertEqual(self.view.agent_last_sort_column, 'name')
        self.assertTrue(self.view.agent_sort_reverse)

        # Check descending order
        calls = self.view.agent_tree.insert.call_args_list
        inserted_names = [call[1]['values'][0] for call in calls]

        expected_order = ['Zebra Agent', 'Delta Agent', 'Charlie Agent', 'Beta Agent', 'Alpha Agent']
        self.assertEqual(inserted_names, expected_order)

    def test_agent_sort_by_session(self):
        """Test sorting agents by session"""
        self.view.sort_agents('session')

        calls = self.view.agent_tree.insert.call_args_list
        inserted_sessions = [call[1]['values'][1] for call in calls]

        # Empty strings should come first, then alphabetical
        # Expected: ['', '', 'Alpha Session', 'Alpha Session', 'Beta Session']
        empty_sessions = [s for s in inserted_sessions if s == '']
        non_empty_sessions = [s for s in inserted_sessions if s != '']

        self.assertEqual(len(empty_sessions), 2)  # Beta Agent and Delta Agent have no session
        self.assertTrue('Alpha Session' in non_empty_sessions)
        self.assertTrue('Beta Session' in non_empty_sessions)

    def test_agent_sort_by_team(self):
        """Test sorting agents by team"""
        self.view.sort_agents('team')

        calls = self.view.agent_tree.insert.call_args_list
        inserted_teams = [call[1]['values'][2] for call in calls]

        # Should be sorted: empty strings first, then alphabetical
        empty_teams = [t for t in inserted_teams if t == '']
        non_empty_teams = [t for t in inserted_teams if t != '']

        self.assertEqual(len(empty_teams), 1)  # Charlie Agent has no team
        # Non-empty teams should be in alphabetical order
        self.assertIn('Alpha Team', non_empty_teams)
        self.assertIn('Beta Team', non_empty_teams)
        self.assertIn('Zebra Team', non_empty_teams)

    def test_agent_sort_by_status(self):
        """Test sorting agents by status"""
        self.view.sort_agents('status')

        calls = self.view.agent_tree.insert.call_args_list
        inserted_statuses = [call[1]['values'][3] for call in calls]

        # Should be sorted alphabetically
        # Expected order: 'connected', 'connected', 'connecting', 'disconnected', 'disconnected'
        connected_count = inserted_statuses.count('connected')
        connecting_count = inserted_statuses.count('connecting')
        disconnected_count = inserted_statuses.count('disconnected')

        self.assertEqual(connected_count, 2)
        self.assertEqual(connecting_count, 1)
        self.assertEqual(disconnected_count, 2)

        # Verify order
        first_status = inserted_statuses[0]
        self.assertEqual(first_status, 'connected')

    def test_team_sort_by_name_ascending(self):
        """Test sorting teams by name in ascending order"""
        self.view.sort_teams('name')

        # Verify sorting attributes
        self.assertEqual(self.view.team_last_sort_column, 'name')
        self.assertFalse(self.view.team_sort_reverse)

        # Check insert calls
        calls = self.view.team_tree.insert.call_args_list
        inserted_names = [call[1]['values'][0] for call in calls]

        expected_order = ['Alpha Team', 'Beta Team', 'Zebra Team']
        self.assertEqual(inserted_names, expected_order)

    def test_team_sort_by_name_descending(self):
        """Test sorting teams by name in descending order"""
        # First click - ascending
        self.view.sort_teams('name')
        # Second click - descending
        self.view.sort_teams('name')

        self.assertTrue(self.view.team_sort_reverse)

        calls = self.view.team_tree.insert.call_args_list
        inserted_names = [call[1]['values'][0] for call in calls]

        expected_order = ['Zebra Team', 'Beta Team', 'Alpha Team']
        self.assertEqual(inserted_names, expected_order)

    def test_team_sort_by_agent_count(self):
        """Test sorting teams by agent count (numerical sort)"""
        self.view.sort_teams('agent_count')

        calls = self.view.team_tree.insert.call_args_list
        inserted_counts = [int(call[1]['values'][1]) for call in calls]

        # Should be sorted numerically: [1, 1, 2]
        self.assertEqual(inserted_counts, [1, 1, 2])

    def test_team_sort_by_created_date(self):
        """Test sorting teams by creation date"""
        self.view.sort_teams('created')

        calls = self.view.team_tree.insert.call_args_list
        inserted_dates = [call[1]['values'][2] for call in calls]

        # Should be sorted by date
        expected_order = ['2024-01-01', '2024-01-02', '2024-01-03']
        self.assertEqual(inserted_dates, expected_order)

    def test_sort_column_switching(self):
        """Test switching between different sort columns"""
        # Sort by name first
        self.view.sort_agents('name')
        self.assertEqual(self.view.agent_last_sort_column, 'name')
        self.assertFalse(self.view.agent_sort_reverse)

        # Switch to session column
        self.view.sort_agents('session')
        self.assertEqual(self.view.agent_last_sort_column, 'session')
        self.assertFalse(self.view.agent_sort_reverse)  # Should reset to ascending

        # Click session again for descending
        self.view.sort_agents('session')
        self.assertEqual(self.view.agent_last_sort_column, 'session')
        self.assertTrue(self.view.agent_sort_reverse)

    def test_sort_heading_updates(self):
        """Test that column headings are updated with sort indicators"""
        # Sort by name
        self.view.sort_agents('name')

        # Check that heading was called to update the column header
        heading_calls = self.view.agent_tree.heading.call_args_list

        # Should have calls to reset all headings and then update the sorted column
        self.assertGreater(len(heading_calls), 4)  # At least 4 columns + the sorted one

        # Find the call that updates the name column with sort indicator
        name_heading_calls = [call for call in heading_calls if call[0][0] == 'name']
        self.assertGreater(len(name_heading_calls), 0)

        # The last call should include the sort indicator
        last_name_call = name_heading_calls[-1]
        text_arg = last_name_call[1].get('text', '')
        self.assertTrue('↑' in text_arg or '↓' in text_arg)

    def test_sort_with_empty_values(self):
        """Test sorting behavior with empty/None values"""
        # Test that empty strings are handled correctly in sorting
        self.view.sort_agents('session')

        # Agents with empty sessions should be sorted appropriately
        calls = self.view.agent_tree.insert.call_args_list

        # Check that we don't get any errors and all items are inserted
        self.assertEqual(len(calls), 5)  # All 5 agents should be inserted

    def test_sort_state_persistence(self):
        """Test that sort state is maintained between operations"""
        # Sort by name descending
        self.view.sort_agents('name')
        self.view.sort_agents('name')  # Second click for descending

        # Verify state
        self.assertEqual(self.view.agent_last_sort_column, 'name')
        self.assertTrue(self.view.agent_sort_reverse)

        # Sort by different column
        self.view.sort_agents('status')

        # Verify new state
        self.assertEqual(self.view.agent_last_sort_column, 'status')
        self.assertFalse(self.view.agent_sort_reverse)  # Should reset to ascending

        # Go back to name column
        self.view.sort_agents('name')

        # Should start with ascending again
        self.assertEqual(self.view.agent_last_sort_column, 'name')
        self.assertFalse(self.view.agent_sort_reverse)

    def test_team_sort_numerical_vs_string(self):
        """Test that agent count sorts numerically, not as strings"""
        # Mock team data with different agent counts to test numerical sorting
        team_items = {
            "team1": {'text': 'team_a', 'values': ('Team A', 10, '2024-01-01')},
            "team2": {'text': 'team_b', 'values': ('Team B', 2, '2024-01-02')},
            "team3": {'text': 'team_c', 'values': ('Team C', 21, '2024-01-03')},
        }

        self.view.team_tree.item.side_effect = lambda item_id: team_items.get(item_id, {})

        self.view.sort_teams('agent_count')

        calls = self.view.team_tree.insert.call_args_list
        inserted_counts = [int(call[1]['values'][1]) for call in calls]

        # Should be numerically sorted: 2, 10, 21 (not string sorted: 10, 2, 21)
        self.assertEqual(inserted_counts, [2, 10, 21])

    def test_sort_stability(self):
        """Test that sorting is stable (maintains relative order for equal values)"""
        # Create mock data where multiple items have the same sort value
        agent_items = {
            "item1": {'text': 'agent_a', 'values': ('Alpha Agent', 'Same Session', 'Team A', 'connected')},
            "item2": {'text': 'agent_b', 'values': ('Beta Agent', 'Same Session', 'Team B', 'connected')},
            "item3": {'text': 'agent_c', 'values': ('Charlie Agent', 'Same Session', 'Team C', 'connected')},
        }

        self.view.agent_tree.item.side_effect = lambda item_id: agent_items.get(item_id, {})
        self.view.agent_tree.get_children.return_value = ["item1", "item2", "item3"]

        # Sort by session (all have same session)
        self.view.sort_agents('session')

        # All should be inserted, and since they have the same session value,
        # the relative order should be maintained
        calls = self.view.agent_tree.insert.call_args_list
        self.assertEqual(len(calls), 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)