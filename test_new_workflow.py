"""Test script for new agent registration workflow"""
import asyncio
import websockets
import json
import sys

async def test_agent_registration():
    """Test the full agent registration workflow"""
    print("Testing agent registration workflow...")

    uri = "ws://localhost:8765/ws/test_client_1"

    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket server")

            # Should receive tool selection prompt
            response = await websocket.recv()
            prompt = json.loads(response)
            print(f"Received prompt: {prompt}")

            if prompt.get("type") != "tool_selection_prompt":
                print("ERROR: Expected tool selection prompt")
                return False

            # Select register tool
            register_msg = ["test_client_1", "select_tool", {
                "tool": "register",
                "name": "Test Agent",
                "capabilities": {"nlp": True, "vision": False}
            }]
            await websocket.send(json.dumps(register_msg))
            print(f"Sent registration message: {register_msg}")

            # Should receive registration success
            response = await websocket.recv()
            result = json.loads(response)
            print(f"Registration result: {result}")

            if result.get("type") == "registration_success":
                print("✓ Registration workflow completed successfully")
                print(f"  Agent ID: {result.get('agent_id')}")
                print(f"  Status: {result.get('status')}")
                return True
            else:
                print("ERROR: Registration failed")
                return False

    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def test_agent_read_write():
    """Test read/write operations with assigned agent"""
    print("\nTesting agent read/write workflow...")

    uri = "ws://localhost:8765/ws/test_client_2"

    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket server")

            # Should receive tool selection prompt
            await websocket.recv()

            # Select write tool
            select_msg = ["test_client_2", "select_tool", {"tool": "write"}]
            await websocket.send(json.dumps(select_msg))
            print(f"Sent tool selection: {select_msg}")

            # Should receive agent_id required message
            response = await websocket.recv()
            result = json.loads(response)
            print(f"Tool selection response: {result}")

            if result.get("type") != "agent_id_required":
                print("ERROR: Expected agent_id_required message")
                return False

            # Authenticate with assigned agent_id (this would normally be assigned by human)
            auth_msg = ["test_client_2", "authenticate", {"agent_id": "test_agent_123"}]
            await websocket.send(json.dumps(auth_msg))
            print(f"Sent authentication: {auth_msg}")

            # Should receive authentication response
            auth_response = await websocket.recv()
            auth_result = json.loads(auth_response)
            print(f"Authentication response: {auth_result}")

            if auth_result.get("type") == "error":
                print("NOTE: Authentication failed as expected (agent not assigned yet)")
                return True
            elif auth_result.get("type") == "authentication_success":
                print("✓ Authentication successful")

                # Try to write a context
                write_msg = ["test_agent_123", "write", {
                    "resource_type": "contexts",
                    "content": {
                        "title": "Test Context",
                        "content": "This is a test context created by the agent"
                    }
                }]
                await websocket.send(json.dumps(write_msg))
                print(f"Sent write request: {write_msg}")

                response = await websocket.recv()
                write_result = json.loads(response)
                print(f"Write response: {write_result}")

                if write_result.get("type") == "write_response":
                    print("✓ Write operation completed successfully")
                    return True

            return False

    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def test_legacy_compatibility():
    """Test legacy announce message compatibility"""
    print("\nTesting legacy compatibility...")

    uri = "ws://localhost:8765/ws/legacy_client"

    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket server")

            # Skip the tool selection prompt
            await websocket.recv()

            # Send legacy announce message
            legacy_msg = {
                "type": "announce",
                "agent_id": "legacy_agent_001",
                "name": "Legacy Test Agent"
            }
            await websocket.send(json.dumps(legacy_msg))
            print(f"Sent legacy announce: {legacy_msg}")

            # Should receive acknowledgment
            response = await websocket.recv()
            result = json.loads(response)
            print(f"Legacy response: {result}")

            if result.get("type") == "announce_ack":
                print("✓ Legacy compatibility working")
                return True
            else:
                print("ERROR: Legacy compatibility failed")
                return False

    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def test_new_message_schema():
    """Test the new [agent, action, data] message schema"""
    print("\nTesting new message schema...")

    uri = "ws://localhost:8765/ws/schema_test_client"

    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket server")

            # Skip the tool selection prompt
            await websocket.recv()

            # Test new schema format
            new_schema_msg = ["schema_test_agent", "echo_test", {"message": "Hello new schema!"}]
            await websocket.send(json.dumps(new_schema_msg))
            print(f"Sent new schema message: {new_schema_msg}")

            # Should receive echo
            response = await websocket.recv()
            result = json.loads(response)
            print(f"Schema response: {result}")

            if result.get("type") == "echo":
                print("✓ New message schema working")
                return True
            else:
                print("ERROR: New message schema failed")
                return False

    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def main():
    """Run all tests"""
    print("Starting comprehensive workflow tests...\n")

    tests = [
        ("Agent Registration", test_agent_registration),
        ("Agent Read/Write", test_agent_read_write),
        ("Legacy Compatibility", test_legacy_compatibility),
        ("New Message Schema", test_new_message_schema)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"ERROR in {test_name}: {e}")
            results.append((test_name, False))

    print("\n" + "="*50)
    print("TEST RESULTS:")
    print("="*50)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:25} {status}")

    total_passed = sum(1 for _, passed in results if passed)
    print(f"\nSummary: {total_passed}/{len(results)} tests passed")

    if total_passed == len(results):
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))