#!/usr/bin/env python3
"""
Comprehensive test suite for the permission-aware agent system
Tests all three access levels and permission validation
"""

import asyncio
import websockets
import json
import sqlite3
import sys
import time
from datetime import datetime

DB_PATH = "multi-agent_mcp_context_manager.db"

async def setup_test_data():
    """Set up test data for permission testing"""
    print("Setting up test data...")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        # Clean up existing test data
        cur.execute("DELETE FROM contexts WHERE agent_id LIKE 'test_%'")
        cur.execute("DELETE FROM agents WHERE id LIKE 'test_%'")
        cur.execute("DELETE FROM teams WHERE id LIKE 'test_%'")
        cur.execute("DELETE FROM sessions WHERE id LIKE 'test_%'")
        cur.execute("DELETE FROM projects WHERE id LIKE 'test_%'")

        # Create test project
        cur.execute("""
            INSERT INTO projects (id, name, description, created_at)
            VALUES ('test_project_1', 'Test Project', 'Test project for permissions', ?)
        """, (datetime.now().isoformat(),))

        # Create test session
        cur.execute("""
            INSERT INTO sessions (id, name, project_id, description, created_at)
            VALUES ('test_session_1', 'Test Session', 'test_project_1', 'Test session', ?)
        """, (datetime.now().isoformat(),))

        # Create test team
        cur.execute("""
            INSERT INTO teams (id, name, session_id, description, created_at)
            VALUES ('test_team_1', 'Test Team', 'test_session_1', 'Test team', ?)
        """, (datetime.now().isoformat(),))

        # Create test agents with different permission levels
        agents = [
            ('test_agent_self', 'Test Agent Self', 'self_only', None),
            ('test_agent_team1', 'Test Agent Team 1', 'team_level', 'test_team_1'),
            ('test_agent_team2', 'Test Agent Team 2', 'team_level', 'test_team_1'),
            ('test_agent_session', 'Test Agent Session', 'session_level', None)
        ]

        for agent_id, name, access_level, team_id in agents:
            cur.execute("""
                INSERT INTO agents (id, name, session_id, team_id, status, last_active,
                                  registration_status, selected_tool, assigned_agent_id,
                                  access_level, permission_granted_by, permission_granted_at)
                VALUES (?, ?, 'test_session_1', ?, 'connected', ?, 'assigned', 'read', ?, ?, 'Test Setup', ?)
            """, (agent_id, name, team_id, datetime.now().isoformat(), agent_id, access_level, datetime.now().isoformat()))

        # Create test contexts from different agents
        contexts = [
            ('ctx_self_1', 'Self Context 1', 'Context created by self-only agent', 'test_agent_self'),
            ('ctx_team1_1', 'Team Context 1', 'Context created by team agent 1', 'test_agent_team1'),
            ('ctx_team2_1', 'Team Context 2', 'Context created by team agent 2', 'test_agent_team2'),
            ('ctx_session_1', 'Session Context 1', 'Context created by session agent', 'test_agent_session')
        ]

        for ctx_id, title, content, agent_id in contexts:
            cur.execute("""
                INSERT INTO contexts (id, title, content, project_id, session_id, agent_id, created_at)
                VALUES (?, ?, ?, 'test_project_1', 'test_session_1', ?, ?)
            """, (ctx_id, title, content, agent_id, datetime.now().isoformat()))

        conn.commit()
        print("Test data setup completed successfully")
        return True

    except Exception as e:
        print(f"Error setting up test data: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

async def test_agent_permission_level(agent_id: str, expected_access_level: str, expected_context_count: int):
    """Test a specific agent's permission level"""
    print(f"\nTesting agent {agent_id} with {expected_access_level} access...")

    uri = f"ws://localhost:8765/ws/{agent_id}_client"

    try:
        async with websockets.connect(uri) as websocket:
            # Skip tool selection prompt
            await websocket.recv()

            # Authenticate as the test agent
            auth_msg = [agent_id + "_client", "authenticate", {"agent_id": agent_id}]
            await websocket.send(json.dumps(auth_msg))

            auth_response = await websocket.recv()
            auth_result = json.loads(auth_response)

            if auth_result.get("type") != "authentication_success":
                print(f"  FAIL: Authentication failed for {agent_id}")
                return False

            # Request contexts
            read_msg = [agent_id, "read", {"resource_type": "contexts", "limit": 20}]
            await websocket.send(json.dumps(read_msg))

            read_response = await websocket.recv()
            read_result = json.loads(read_response)

            if read_result.get("type") != "read_response":
                print(f"  FAIL: Read operation failed for {agent_id}")
                return False

            actual_access_level = read_result.get("access_level")
            actual_count = read_result.get("count", 0)
            contexts = read_result.get("data", [])

            # Validate access level
            if actual_access_level != expected_access_level:
                print(f"  FAIL: Expected access level {expected_access_level}, got {actual_access_level}")
                return False

            # Validate context count
            if actual_count != expected_context_count:
                print(f"  FAIL: Expected {expected_context_count} contexts, got {actual_count}")
                print(f"  Contexts received: {[ctx.get('title', 'No title') for ctx in contexts]}")
                return False

            print(f"  PASS: Agent {agent_id} correctly retrieved {actual_count} contexts with {actual_access_level} access")
            return True

    except Exception as e:
        print(f"  FAIL: Exception testing {agent_id}: {e}")
        return False

async def test_permission_isolation():
    """Test that permissions properly isolate agent access"""
    print("\n" + "="*60)
    print("TESTING PERMISSION ISOLATION")
    print("="*60)

    test_cases = [
        ("test_agent_self", "self_only", 1),      # Should see only own context
        ("test_agent_team1", "team_level", 2),    # Should see team contexts (team1 + team2)
        ("test_agent_team2", "team_level", 2),    # Should see team contexts (team1 + team2)
        ("test_agent_session", "session_level", 4) # Should see all session contexts
    ]

    results = []
    for agent_id, access_level, expected_count in test_cases:
        result = await test_agent_permission_level(agent_id, access_level, expected_count)
        results.append((agent_id, result))

    return results

async def test_new_agent_registration():
    """Test new agent registration with permission assignment"""
    print("\n" + "="*60)
    print("TESTING NEW AGENT REGISTRATION")
    print("="*60)

    uri = "ws://localhost:8765/ws/new_test_agent"

    try:
        async with websockets.connect(uri) as websocket:
            # Should receive tool selection prompt
            response = await websocket.recv()
            prompt = json.loads(response)

            if prompt.get("type") != "tool_selection_prompt":
                print("FAIL: Expected tool selection prompt")
                return False

            # Register new agent
            register_msg = ["new_test_agent", "select_tool", {
                "tool": "register",
                "name": "New Test Agent",
                "capabilities": {"test": True}
            }]
            await websocket.send(json.dumps(register_msg))

            # Should receive registration success
            response = await websocket.recv()
            result = json.loads(response)

            if result.get("type") != "registration_success":
                print(f"FAIL: Registration failed: {result}")
                return False

            agent_id = result.get("agent_id")
            print(f"PASS: New agent registered with ID: {agent_id}")

            # Verify agent in database
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT access_level, registration_status FROM agents WHERE id = ?", (agent_id,))
            row = cur.fetchone()
            conn.close()

            if not row:
                print("FAIL: Agent not found in database")
                return False

            access_level, reg_status = row
            if access_level != "self_only":
                print(f"FAIL: Expected default access_level 'self_only', got '{access_level}'")
                return False

            if reg_status != "pending":
                print(f"FAIL: Expected registration_status 'pending', got '{reg_status}'")
                return False

            print("PASS: New agent has correct default permissions")
            return True

    except Exception as e:
        print(f"FAIL: Exception in registration test: {e}")
        return False

async def test_legacy_compatibility():
    """Test that legacy agents still work"""
    print("\n" + "="*60)
    print("TESTING LEGACY COMPATIBILITY")
    print("="*60)

    uri = "ws://localhost:8765/ws/legacy_test_agent"

    try:
        async with websockets.connect(uri) as websocket:
            # Skip tool selection prompt
            await websocket.recv()

            # Send legacy announce message
            legacy_msg = {
                "type": "announce",
                "agent_id": "legacy_test_agent_001",
                "name": "Legacy Test Agent"
            }
            await websocket.send(json.dumps(legacy_msg))

            # Should receive acknowledgment
            response = await websocket.recv()
            result = json.loads(response)

            if result.get("type") != "announce_ack":
                print(f"FAIL: Legacy announce failed: {result}")
                return False

            print("PASS: Legacy agent announce works")

            # Verify agent has correct default permissions
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT access_level, registration_status FROM agents WHERE assigned_agent_id = ?",
                       ("legacy_test_agent_001",))
            row = cur.fetchone()
            conn.close()

            if not row:
                print("FAIL: Legacy agent not found in database")
                return False

            access_level, reg_status = row
            if access_level != "self_only":
                print(f"FAIL: Expected default access_level 'self_only', got '{access_level}'")
                return False

            print("PASS: Legacy agent has correct default permissions")
            return True

    except Exception as e:
        print(f"FAIL: Exception in legacy test: {e}")
        return False

async def cleanup_test_data():
    """Clean up test data"""
    print("\nCleaning up test data...")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        # Clean up test data
        cur.execute("DELETE FROM contexts WHERE agent_id LIKE 'test_%'")
        cur.execute("DELETE FROM agents WHERE id LIKE 'test_%' OR id LIKE 'new_test_%' OR assigned_agent_id LIKE 'legacy_%'")
        cur.execute("DELETE FROM teams WHERE id LIKE 'test_%'")
        cur.execute("DELETE FROM sessions WHERE id LIKE 'test_%'")
        cur.execute("DELETE FROM projects WHERE id LIKE 'test_%'")

        conn.commit()
        print("Test data cleaned up successfully")

    except Exception as e:
        print(f"Error cleaning up test data: {e}")
    finally:
        conn.close()

async def main():
    """Run all permission system tests"""
    print("Starting comprehensive permission system tests...")
    print("Make sure the MCP server is running on localhost:8765")

    # Wait a moment for server to be ready
    await asyncio.sleep(1)

    # Setup test data
    if not await setup_test_data():
        print("FAILED: Could not set up test data")
        return 1

    try:
        # Run tests
        test_results = []

        # Test permission isolation
        isolation_results = await test_permission_isolation()
        test_results.extend(isolation_results)

        # Test new agent registration
        reg_result = await test_new_agent_registration()
        test_results.append(("new_agent_registration", reg_result))

        # Test legacy compatibility
        legacy_result = await test_legacy_compatibility()
        test_results.append(("legacy_compatibility", legacy_result))

        # Print results
        print("\n" + "="*60)
        print("TEST RESULTS SUMMARY")
        print("="*60)

        passed = 0
        total = len(test_results)

        for test_name, result in test_results:
            status = "PASS" if result else "FAIL"
            print(f"{test_name:25} {status}")
            if result:
                passed += 1

        print(f"\nSummary: {passed}/{total} tests passed")

        if passed == total:
            print("ALL TESTS PASSED! Permission system is working correctly.")
            return 0
        else:
            print("SOME TESTS FAILED! Please review the permission system.")
            return 1

    finally:
        await cleanup_test_data()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))