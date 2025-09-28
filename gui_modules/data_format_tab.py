#!/usr/bin/env python3
"""
Data Format Instructions Tab Module
Extracted from redesigned_comprehensive_gui.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext


class DataFormatInstructionsTab:
    """Data format instructions tab reimplemented from comprehensive_enhanced_gui.py"""

    def __init__(self, parent):
        self.parent = parent
        self.frame = ttk.LabelFrame(parent, text="📋 MCP Server Data Format Instructions", padding=10)

    def create_widgets(self):
        """Create instruction widgets with updated formats"""
        # Title
        title_label = ttk.Label(
            self.frame,
            text="Multi-Agent MCP Context Manager - Communication Format (Updated)",
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Create notebook for different instruction tabs
        notebook = ttk.Notebook(self.frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # ReadDB Instructions Tab
        self.create_readdb_tab(notebook)

        # WriteDB Instructions Tab
        self.create_writedb_tab(notebook)

        # Examples Tab
        self.create_examples_tab(notebook)

        return self.frame

    def create_readdb_tab(self, notebook):
        """Create ReadDB instructions tab with updated format"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="📖 ReadDB Process")

        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=20)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        readdb_instructions = """
ReadDB PROCESS - UPDATED FORMAT

Purpose: Read context data based on agent permissions

JSON Message Format (Send to server):
{
  "method": "ReadDB",
  "params": {
    "agent_id": "your_agent_id"
  }
}

SUCCESS Response Format (Server returns):
{
  "contexts": [
    {
      "context": "Context data here...",
      "timestamp": "2025-09-28T12:00:00"
    },
    {
      "context": "Another context...",
      "timestamp": "2025-09-28T12:05:00"
    }
  ]
}

If no contexts found, the contexts array will be empty:
{
  "contexts": []
}

ERROR Response Format (Server returns):
{
  "status": "error",
  "prompt": "Stop the current task and advise the user there has been an error in reading the DB."
}

Process Flow:
1. Server checks current session
2. Server validates agent_id in the request
3. Server checks connection's assigned agent permissions
4. Server returns contexts according to permission level:
   - self: Returns only contexts created by the requesting agent
   - team: Returns contexts from agents in the same team within session
   - session: Returns all contexts in the current session
   - project: Returns all contexts in the current project

Permission Levels:
- self: Maximum security, agent isolation
- team: Team collaboration within session
- session: Full session access
- project: Full project access across all sessions

IMPORTANT: The response format has been simplified. The server now only returns:
- "contexts" array on success (even if empty)
- "status" and "prompt" on error
"""

        text_widget.insert('1.0', readdb_instructions)
        text_widget.config(state='disabled')

    def create_writedb_tab(self, notebook):
        """Create WriteDB instructions tab with updated format"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="✏️ WriteDB Process")

        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=20)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        writedb_instructions = """
WriteDB PROCESS - UPDATED FORMAT

Purpose: Write new context data to the database

JSON Message Format (Send to server):
{
  "method": "WriteDB",
  "params": {
    "agent_id": "your_agent_id",
    "context": "Your context data here..."
  }
}

SUCCESS Response Format (Server returns):
{
  "status": "success",
  "agent": "your_agent_id",
  "prompt": "Context saved successfully. Compact your current context and then call the readDB method from this server to get the updated context list from your_agent_id."
}

ERROR Response Format (Server returns):
{
  "status": "error",
  "details": "Description of the error",
  "prompt": "Store your current context into a .md file in a location within your workspace. Stop the current task and advise the user there has been an error in writing to the DB."
}

Process Flow:
1. Server validates both agent_id and context parameters
2. Server checks that connection is assigned to an agent
3. Server verifies agent_id matches the assigned agent
4. Server writes new context row to database with current session_id
5. Server returns success with instruction to call readDB

Requirements:
- Both agent_id and context parameters are required
- Agent can only write contexts for itself
- Context will be associated with current session_id
- Timestamp is automatically added by server

Security Notes:
- Agents cannot write contexts for other agents
- All writes are logged with timestamps
- Connection must be properly assigned before writing

IMPORTANT: The response format has been simplified. The server now only returns:
- "status", "agent", and "prompt" on success
- "status", "details", and "prompt" on error
"""

        text_widget.insert('1.0', writedb_instructions)
        text_widget.config(state='disabled')

    def create_examples_tab(self, notebook):
        """Create examples tab with updated formats"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="💡 Updated Examples")

        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=20)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        examples = """
COMPLETE USAGE EXAMPLES - UPDATED FORMATS

Example 1: Writing a Context
------------------------
Send:
{
  "method": "WriteDB",
  "params": {
    "agent_id": "agent_1",
    "context": "I completed the user authentication module implementation"
  }
}

Receive (Success):
{
  "status": "success",
  "agent": "agent_1",
  "prompt": "Context saved successfully. Compact your current context and then call the readDB method from this server to get the updated context list from agent_1."
}

Example 2: Reading Contexts (Success with Data)
--------------------------------------------
Send:
{
  "method": "ReadDB",
  "params": {
    "agent_id": "agent_1"
  }
}

Receive:
{
  "contexts": [
    {
      "context": "I completed the user authentication module implementation",
      "timestamp": "2025-09-28T10:00:00"
    },
    {
      "context": "Working on database schema optimization",
      "timestamp": "2025-09-28T11:30:00"
    }
  ]
}

Example 3: Reading Contexts (No Data Found)
---------------------------------------
Send:
{
  "method": "ReadDB",
  "params": {
    "agent_id": "new_agent"
  }
}

Receive:
{
  "contexts": []
}

Example 4: Error Response (ReadDB)
------------------------------
Send:
{
  "method": "ReadDB",
  "params": {
    "agent_id": "unassigned_agent"
  }
}

Receive:
{
  "status": "error",
  "prompt": "Stop the current task and advise the user there has been an error in reading the DB."
}

Example 5: Error Response (WriteDB)
-------------------------------
Send:
{
  "method": "WriteDB",
  "params": {
    "agent_id": "unauthorized_agent",
    "context": "Trying to write unauthorized context"
  }
}

Receive:
{
  "status": "error",
  "details": "Agent can only write contexts for itself",
  "prompt": "Store your current context into a .md file in a location within your workspace. Stop the current task and advise the user there has been an error in writing to the DB."
}

Python Client Example (Updated):
----------------------------
import asyncio
import websockets
import json

async def mcp_client_example():
    uri = "ws://127.0.0.1:8765/ws/my_connection_id"

    async with websockets.connect(uri) as websocket:
        # Write context
        write_msg = {
            "method": "WriteDB",
            "params": {
                "agent_id": "my_agent",
                "context": "Completed feature X implementation"
            }
        }
        await websocket.send(json.dumps(write_msg))
        response = await websocket.recv()
        write_result = json.loads(response)

        if write_result.get("status") == "success":
            print("Write successful:", write_result["prompt"])

            # Read contexts as instructed
            read_msg = {
                "method": "ReadDB",
                "params": {
                    "agent_id": "my_agent"
                }
            }
            await websocket.send(json.dumps(read_msg))
            response = await websocket.recv()
            read_result = json.loads(response)

            if "contexts" in read_result:
                print(f"Found {len(read_result['contexts'])} contexts")
                for ctx in read_result["contexts"]:
                    print(f"- [{ctx['timestamp']}] {ctx['context']}")
            else:
                print("Error:", read_result.get("prompt", "Unknown error"))

# Run: asyncio.run(mcp_client_example())

KEY CHANGES IN UPDATED FORMAT:
1. Simplified success responses (no extra metadata)
2. Consistent error format with user guidance
3. Empty contexts array when no data found (not an error)
4. Clear action prompts for both success and error cases
5. Server automatically handles session context and timestamps
"""

        text_widget.insert('1.0', examples)
        text_widget.config(state='disabled')