#!/usr/bin/env python3
"""
Comprehensive Test Suite for Multi-Agent MCP Context Manager
Tests all critical functionality including permission system, WebSocket connections, and database operations
"""

import asyncio
import websockets
import json
import sqlite3
import sys
import time
import traceback
from datetime import datetime
from typing import List, Dict, Any

# Test configuration
DB_PATH = "../multi-agent_mcp_context_manager.db"
WS_BASE_URL = "ws://localhost:8765/ws"

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self, test_name: str):
        self.passed += 1
        print(f"[PASS] {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"[FAIL] {test_name} - {error}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY: {self.passed}/{total} PASSED")
        print(f"{'='*60}")

        if self.failed > 0:
            print("\nFAILED TESTS:")
            for test_name, error in self.errors:
                print(f"  - {test_name}: {error}")

        return self.failed == 0

class DatabaseTestHelper:
    """Helper class for database testing operations"""

    @staticmethod
    def cleanup_test_data():
        """Clean up test data from database"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()

            # Clean up test data
            cur.execute("DELETE FROM contexts WHERE agent_id LIKE 'test_%' OR agent_id LIKE 'comp_test_%'")
            cur.execute("DELETE FROM agents WHERE id LIKE 'test_%' OR id LIKE 'comp_test_%' OR name LIKE '%Test%'")
            cur.execute("DELETE FROM teams WHERE id LIKE 'test_%'")
            cur.execute("DELETE FROM sessions WHERE id LIKE 'test_%'")
            cur.execute("DELETE FROM projects WHERE id LIKE 'test_%'")

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Warning: Could not clean up test data: {e}")
            return False

    @staticmethod
    def setup_test_data():
        """Set up test data for permission testing"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()

            # Create test project
            cur.execute("""
                INSERT OR REPLACE INTO projects (id, name, description, created_at)
                VALUES ('test_project', 'Test Project', 'Test project', ?)
            """, (datetime.now().isoformat(),))

            # Create test session
            cur.execute("""
                INSERT OR REPLACE INTO sessions (id, name, project_id, description, created_at)
                VALUES ('test_session', 'Test Session', 'test_project', 'Test session', ?)
            """, (datetime.now().isoformat(),))

            # Create test team
            cur.execute("""
                INSERT OR REPLACE INTO teams (id, name, session_id, description, created_at)
                VALUES ('test_team', 'Test Team', 'test_session', 'Test team', ?)
            """, (datetime.now().isoformat(),))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error setting up test data: {e}")
            return False

class ComprehensiveTestSuite:
    """Main test suite class"""

    def __init__(self):
        self.results = TestResults()

    async def run_all_tests(self):
        """Run all test suites"""
        print("Starting Comprehensive Test Suite for Multi-Agent MCP Context Manager")
        print(f"Database: {DB_PATH}")
        print(f"WebSocket: {WS_BASE_URL}")
        print("="*60)

        # Setup
        if not DatabaseTestHelper.cleanup_test_data():
            self.results.add_fail("Database Cleanup", "Could not clean test data")

        if not DatabaseTestHelper.setup_test_data():
            self.results.add_fail("Database Setup", "Could not create test data")

        # Run test suites
        await self.test_basic_connectivity()
        await self.test_agent_registration()
        await self.test_permission_system()
        await self.test_context_operations()
        await self.test_websocket_stability()
        await self.test_database_operations()

        # Cleanup
        DatabaseTestHelper.cleanup_test_data()

        # Results
        return self.results.summary()

    async def test_basic_connectivity(self):
        """Test basic WebSocket connectivity"""
        print("\n[INFO] Testing Basic Connectivity...")

        try:
            uri = f"{WS_BASE_URL}/comp_test_basic"
            async with websockets.connect(uri) as websocket:
                # Should receive tool selection prompt
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                prompt = json.loads(response)

                if prompt.get("type") == "tool_selection_prompt":
                    self.results.add_pass("Basic WebSocket Connection")
                else:
                    self.results.add_fail("Basic WebSocket Connection", f"Expected tool_selection_prompt, got {prompt.get('type')}")

        except Exception as e:
            self.results.add_fail("Basic WebSocket Connection", str(e))

    async def test_agent_registration(self):
        """Test agent registration workflow"""
        print("\n[INFO] Testing Agent Registration...")

        # Test successful registration
        try:
            uri = f"{WS_BASE_URL}/comp_test_reg"
            async with websockets.connect(uri) as websocket:
                # Skip tool selection prompt
                await websocket.recv()

                # Register agent
                register_msg = ["comp_test_reg", "select_tool", {
                    "tool": "register",
                    "name": "Comprehensive Test Agent"
                }]
                await websocket.send(json.dumps(register_msg))

                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                result = json.loads(response)

                if result.get("type") == "registration_success":
                    agent_id = result.get("agent_id")
                    self.results.add_pass("Agent Registration Success")

                    # Verify in database
                    conn = sqlite3.connect(DB_PATH)
                    cur = conn.cursor()
                    cur.execute("SELECT access_level FROM agents WHERE id = ?", (agent_id,))
                    row = cur.fetchone()
                    conn.close()

                    if row and row[0] == "self_only":
                        self.results.add_pass("Agent Default Permissions")
                    else:
                        self.results.add_fail("Agent Default Permissions", f"Expected self_only, got {row[0] if row else None}")
                else:
                    self.results.add_fail("Agent Registration Success", f"Registration failed: {result}")

        except Exception as e:
            self.results.add_fail("Agent Registration Success", str(e))

        # Test duplicate name handling
        try:
            uri = f"{WS_BASE_URL}/comp_test_dup"
            async with websockets.connect(uri) as websocket:
                await websocket.recv()

                register_msg = ["comp_test_dup", "select_tool", {
                    "tool": "register",
                    "name": "Comprehensive Test Agent"  # Same name as above
                }]
                await websocket.send(json.dumps(register_msg))

                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                result = json.loads(response)

                if result.get("type") == "registration_success":
                    self.results.add_pass("Duplicate Name Handling")
                else:
                    self.results.add_fail("Duplicate Name Handling", f"Registration failed: {result}")

        except Exception as e:
            self.results.add_fail("Duplicate Name Handling", str(e))

    async def test_permission_system(self):
        """Test three-tier permission system"""
        print("\n[INFO] Testing Permission System...")

        # Setup test agents with different permission levels
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        try:
            # Create test agents directly in database for controlled testing
            test_agents = [
                ('comp_test_self', 'Self Only Agent', 'self_only', None),
                ('comp_test_team1', 'Team Agent 1', 'team_level', 'test_team'),
                ('comp_test_team2', 'Team Agent 2', 'team_level', 'test_team'),
                ('comp_test_session', 'Session Agent', 'session_level', None)
            ]

            for agent_id, name, access_level, team_id in test_agents:
                cur.execute("""
                    INSERT OR REPLACE INTO agents
                    (id, name, session_id, team_id, status, last_active, registration_status,
                     selected_tool, assigned_agent_id, access_level, permission_granted_by, permission_granted_at)
                    VALUES (?, ?, 'test_session', ?, 'connected', ?, 'assigned', 'read', ?, ?, 'Test Setup', ?)
                """, (agent_id, name, team_id, datetime.now().isoformat(), agent_id, access_level, datetime.now().isoformat()))

            # Create test contexts
            contexts = [
                ('ctx_self', 'Self Context', 'Context from self-only agent', 'comp_test_self'),
                ('ctx_team1', 'Team Context 1', 'Context from team agent 1', 'comp_test_team1'),
                ('ctx_team2', 'Team Context 2', 'Context from team agent 2', 'comp_test_team2'),
                ('ctx_session', 'Session Context', 'Context from session agent', 'comp_test_session')
            ]

            for ctx_id, title, content, agent_id in contexts:
                cur.execute("""
                    INSERT OR REPLACE INTO contexts (id, title, content, project_id, session_id, agent_id, created_at)
                    VALUES (?, ?, ?, 'test_project', 'test_session', ?, ?)
                """, (ctx_id, title, content, agent_id, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            # Test permission isolation
            permission_tests = [
                ('comp_test_self', 'self_only', 1),      # Should see only own context
                ('comp_test_team1', 'team_level', 2),    # Should see team contexts (team1 + team2)
                ('comp_test_team2', 'team_level', 2),    # Should see team contexts (team1 + team2)
                ('comp_test_session', 'session_level', 4) # Should see all session contexts
            ]

            for agent_id, expected_level, expected_count in permission_tests:
                try:
                    uri = f"{WS_BASE_URL}/{agent_id}_client"
                    async with websockets.connect(uri) as websocket:
                        # Skip tool selection
                        await websocket.recv()

                        # Authenticate
                        auth_msg = [f"{agent_id}_client", "authenticate", {"agent_id": agent_id}]
                        await websocket.send(json.dumps(auth_msg))
                        auth_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        auth_result = json.loads(auth_response)

                        if auth_result.get("type") != "authentication_success":
                            self.results.add_fail(f"Permission Test {agent_id}", f"Auth failed: {auth_result}")
                            continue

                        # Request contexts
                        read_msg = [agent_id, "read", {"resource_type": "contexts", "limit": 20}]
                        await websocket.send(json.dumps(read_msg))
                        read_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        read_result = json.loads(read_response)

                        if read_result.get("type") == "read_response":
                            actual_level = read_result.get("access_level")
                            actual_count = read_result.get("count", 0)

                            if actual_level == expected_level and actual_count == expected_count:
                                self.results.add_pass(f"Permission Isolation {agent_id}")
                            else:
                                self.results.add_fail(f"Permission Isolation {agent_id}",
                                    f"Expected {expected_level}/{expected_count}, got {actual_level}/{actual_count}")
                        else:
                            self.results.add_fail(f"Permission Isolation {agent_id}", f"Read failed: {read_result}")

                except Exception as e:
                    self.results.add_fail(f"Permission Isolation {agent_id}", str(e))

        except Exception as e:
            self.results.add_fail("Permission System Setup", str(e))

    async def test_context_operations(self):
        """Test context read/write operations"""
        print("\n[INFO] Testing Context Operations...")

        try:
            # Test write operation
            uri = f"{WS_BASE_URL}/comp_test_writer"
            async with websockets.connect(uri) as websocket:
                await websocket.recv()  # Skip tool selection

                # Select write tool
                tool_msg = ["comp_test_writer", "select_tool", {"tool": "write"}]
                await websocket.send(json.dumps(tool_msg))
                await websocket.recv()  # Skip auth prompt

                # Authenticate (create agent for write test)
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute("""
                    INSERT OR REPLACE INTO agents
                    (id, name, status, last_active, registration_status, selected_tool, assigned_agent_id, access_level)
                    VALUES ('comp_test_writer', 'Test Writer', 'connected', ?, 'assigned', 'write', 'comp_test_writer', 'self_only')
                """, (datetime.now().isoformat(),))
                conn.commit()
                conn.close()

                auth_msg = ["comp_test_writer", "authenticate", {"agent_id": "comp_test_writer"}]
                await websocket.send(json.dumps(auth_msg))
                await websocket.recv()  # Auth response

                # Write context
                write_msg = ["comp_test_writer", "write", {
                    "resource_type": "context",
                    "title": "Test Context Write",
                    "content": "This is a test context for write operations"
                }]
                await websocket.send(json.dumps(write_msg))
                write_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                write_result = json.loads(write_response)

                if write_result.get("type") == "write_response" and write_result.get("success"):
                    self.results.add_pass("Context Write Operation")
                else:
                    self.results.add_fail("Context Write Operation", f"Write failed: {write_result}")

        except Exception as e:
            self.results.add_fail("Context Write Operation", str(e))

    async def test_websocket_stability(self):
        """Test WebSocket connection stability and cleanup"""
        print("\n[INFO] Testing WebSocket Stability...")

        # Test multiple concurrent connections
        try:
            connections = []
            for i in range(3):
                uri = f"{WS_BASE_URL}/comp_test_multi_{i}"
                ws = await websockets.connect(uri)
                connections.append(ws)
                await ws.recv()  # Tool selection prompt

            # Close all connections
            for ws in connections:
                await ws.close()

            self.results.add_pass("Multiple WebSocket Connections")

        except Exception as e:
            self.results.add_fail("Multiple WebSocket Connections", str(e))

        # Test connection cleanup after abrupt disconnect
        try:
            uri = f"{WS_BASE_URL}/comp_test_cleanup"
            ws = await websockets.connect(uri)
            await ws.recv()

            # Force close without proper cleanup
            await ws.close()

            # Wait a moment for cleanup
            await asyncio.sleep(0.5)

            # Try to connect again with same ID
            ws2 = await websockets.connect(uri)
            await ws2.recv()
            await ws2.close()

            self.results.add_pass("WebSocket Cleanup")

        except Exception as e:
            self.results.add_fail("WebSocket Cleanup", str(e))

    async def test_database_operations(self):
        """Test database operations and integrity"""
        print("\n[INFO] Testing Database Operations...")

        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()

            # Test database connection
            cur.execute("SELECT COUNT(*) FROM agents")
            agent_count = cur.fetchone()[0]
            self.results.add_pass("Database Connection")

            # Test table existence
            required_tables = ['agents', 'contexts', 'projects', 'sessions', 'teams', 'agent_permission_history']
            for table in required_tables:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
                if cur.fetchone():
                    self.results.add_pass(f"Table Exists: {table}")
                else:
                    self.results.add_fail(f"Table Exists: {table}", "Table not found")

            # Test permission columns
            cur.execute("PRAGMA table_info(agents)")
            columns = [col[1] for col in cur.fetchall()]

            required_columns = ['access_level', 'permission_granted_by', 'permission_granted_at']
            for column in required_columns:
                if column in columns:
                    self.results.add_pass(f"Column Exists: agents.{column}")
                else:
                    self.results.add_fail(f"Column Exists: agents.{column}", "Column not found")

            conn.close()

        except Exception as e:
            self.results.add_fail("Database Operations", str(e))

async def main():
    """Main test runner"""
    print("Multi-Agent MCP Context Manager - Comprehensive Test Suite")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    suite = ComprehensiveTestSuite()
    success = await suite.run_all_tests()

    if success:
        print("\n[SUCCESS] ALL TESTS PASSED! System is functioning correctly.")
        return 0
    else:
        print("\n[WARNING] SOME TESTS FAILED! Please review the issues above.")
        return 1

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(result)
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Test runner crashed: {e}")
        traceback.print_exc()
        sys.exit(1)