#!/usr/bin/env python3
"""
Basic test to verify permission system is working
"""

import asyncio
import websockets
import json
import sqlite3
from datetime import datetime

async def test_basic_permission_workflow():
    """Test basic permission workflow"""
    print("Testing basic permission workflow...")

    # 1. Test agent registration
    uri = "ws://localhost:8765/ws/basic_test_client"

    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to server")

            # Should receive tool selection prompt
            response = await websocket.recv()
            prompt = json.loads(response)
            print(f"Received prompt: {prompt}")

            if prompt.get("type") != "tool_selection_prompt":
                print("FAIL: Expected tool selection prompt")
                return False

            # Register new agent
            register_msg = ["basic_test_client", "select_tool", {
                "tool": "register",
                "name": "Basic Test Agent"
            }]
            await websocket.send(json.dumps(register_msg))
            print("Sent registration request")

            # Should receive registration success
            response = await websocket.recv()
            result = json.loads(response)
            print(f"Registration result: {result}")

            if result.get("type") != "registration_success":
                print(f"FAIL: Registration failed: {result}")
                return False

            agent_id = result.get("agent_id")
            print(f"SUCCESS: Agent registered with ID: {agent_id}")

            # Verify in database
            conn = sqlite3.connect("multi-agent_mcp_context_manager.db")
            cur = conn.cursor()
            cur.execute("""
                SELECT access_level, registration_status, assigned_agent_id
                FROM agents WHERE id = ?
            """, (agent_id,))
            row = cur.fetchone()
            conn.close()

            if not row:
                print("FAIL: Agent not found in database")
                return False

            access_level, reg_status, assigned_id = row
            print(f"Database check: access_level={access_level}, status={reg_status}, assigned_id={assigned_id}")

            if access_level != "self_only":
                print(f"FAIL: Expected access_level 'self_only', got '{access_level}'")
                return False

            if reg_status != "pending":
                print(f"FAIL: Expected status 'pending', got '{reg_status}'")
                return False

            print("SUCCESS: Agent has correct default permissions")
            return True

    except Exception as e:
        print(f"FAIL: Exception: {e}")
        return False

async def main():
    print("Running basic permission system test...")

    result = await test_basic_permission_workflow()

    if result:
        print("\nBASIC TEST PASSED: Permission system is working!")
        return 0
    else:
        print("\nBASIC TEST FAILED: Permission system has issues")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))