#!/usr/bin/env python3
"""Simple test of the new workflow"""
import asyncio
import websockets
import json

async def simple_test():
    uri = "ws://localhost:8765/ws/simple_test"

    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")

            # Should receive tool selection prompt
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            msg = json.loads(response)
            print(f"Received: {msg}")

            if msg.get("type") == "tool_selection_prompt":
                print("Tool selection prompt received correctly")

                # Try to register
                register_msg = ["simple_test", "select_tool", {
                    "tool": "register",
                    "name": "Simple Test Agent"
                }]
                await websocket.send(json.dumps(register_msg))
                print(f"Sent: {register_msg}")

                # Get response
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                result = json.loads(response)
                print(f"Registration result: {result}")

                if result.get("type") == "registration_success":
                    print("Registration successful!")
                    return True
                else:
                    print("Registration failed")
                    return False
            else:
                print(f"Unexpected response: {msg}")
                return False

    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(simple_test())
    print("Test result:", "PASSED" if result else "FAILED")