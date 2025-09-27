#!/usr/bin/env python3
"""
Enhanced GUI Module for Multi-Agent MCP Context Manager
Provides clear instructions for data format and JSON that the server expects
Includes agent-connection assignment and permission management
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import sqlite3
import requests
from datetime import datetime
from typing import Dict, List, Optional

class DataFormatInstructions:
    """Widget to display clear data format instructions"""

    def __init__(self, parent):
        self.parent = parent
        self.frame = ttk.LabelFrame(parent, text="📋 MCP Server Data Format Instructions", padding=10)

    def create_widgets(self):
        """Create instruction widgets"""
        # Title
        title_label = ttk.Label(
            self.frame,
            text="Multi-Agent MCP Context Manager - Communication Format",
            font=("Arial", 12, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Create notebook for different instruction tabs
        notebook = ttk.Notebook(self.frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Connection Instructions Tab
        self.create_connection_tab(notebook)

        # ReadDB Instructions Tab
        self.create_readdb_tab(notebook)

        # WriteDB Instructions Tab
        self.create_writedb_tab(notebook)

        # Examples Tab
        self.create_examples_tab(notebook)

        return self.frame

    def create_connection_tab(self, notebook):
        """Create connection instructions tab"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="🔗 Connection Setup")

        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=20)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        connection_instructions = """
CONNECTION SETUP INSTRUCTIONS

1. WebSocket Endpoint:
   ws://127.0.0.1:8765/ws/{connection_id}

   Replace {connection_id} with a unique identifier for your connection.

2. Server Configuration for Claude Code:
   Add this to your Claude Code MCP configuration:

   {
     "mcpServers": {
       "multi-agent-context-manager": {
         "command": "python",
         "args": ["run_redesigned_mcp_server.py"],
         "env": {
           "MCP_SERVER_PORT": "8765",
           "MCP_SERVER_HOST": "127.0.0.1"
         }
       }
     }
   }

3. Connection Registration:
   - When you first connect, your connection will be automatically registered as "pending"
   - Use the GUI to assign an agent to your connection (1-to-1 relationship)
   - Only assigned connections can read/write data

4. Agent Assignment:
   - Each connection must be assigned to exactly one agent
   - Each agent can only be assigned to one connection
   - Use the GUI "Assign Agent" feature to complete this setup

5. Permission Levels:
   Configure your agent's read permission level:
   - self_only: Can only read own contexts
   - team_level: Can read contexts from same team
   - session_level: Can read all contexts in session
"""

        text_widget.insert('1.0', connection_instructions)
        text_widget.config(state='disabled')

    def create_readdb_tab(self, notebook):
        """Create ReadDB instructions tab"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="📖 ReadDB Process")

        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=20)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        readdb_instructions = """
ReadDB PROCESS

Purpose: Read context data based on agent permissions

JSON Message Format:
{
  "method": "ReadDB",
  "params": {
    "agent_id": "your_agent_id"
  }
}

Process Flow:
1. Server checks current session
2. Server validates agent_id in the request
3. Server checks connection's assigned agent permissions
4. Server returns contexts according to permission level

Response Format:
{
  "success": true,
  "session_id": 1,
  "agent_id": "your_agent_id",
  "read_permission": "self_only|team_level|session_level",
  "contexts": [
    {
      "id": 1,
      "agent_id": "agent_1",
      "context": "Context data here...",
      "created_at": "2025-09-28T12:00:00"
    }
  ]
}

Permission Levels:
- self_only: Returns only contexts created by the requesting agent
- team_level: Returns contexts from agents in the same team
- session_level: Returns all contexts in the current session

Error Response:
{
  "error": "Description of error",
  "details": "Additional error information"
}
"""

        text_widget.insert('1.0', readdb_instructions)
        text_widget.config(state='disabled')

    def create_writedb_tab(self, notebook):
        """Create WriteDB instructions tab"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="✏️ WriteDB Process")

        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=20)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        writedb_instructions = """
WriteDB PROCESS

Purpose: Write new context data to the database

JSON Message Format:
{
  "method": "WriteDB",
  "params": {
    "agent_id": "your_agent_id",
    "context": "Your context data here..."
  }
}

Process Flow:
1. Server validates both agent_id and context parameters
2. Server checks that connection is assigned to an agent
3. Server verifies agent_id matches the assigned agent
4. Server writes new context row to database

Response Format:
{
  "success": true,
  "context_id": 123,
  "session_id": 1,
  "agent_id": "your_agent_id",
  "context": "Your context data here..."
}

Requirements:
- Both agent_id and context parameters are required
- Agent can only write contexts for itself
- Context will be associated with current session_id
- Timestamp is automatically added

Error Response:
{
  "error": "Description of error",
  "details": "Additional error information"
}

Security Notes:
- Agents cannot write contexts for other agents
- All writes are logged with timestamps
- Connection must be properly assigned before writing
"""

        text_widget.insert('1.0', writedb_instructions)
        text_widget.config(state='disabled')

    def create_examples_tab(self, notebook):
        """Create examples tab"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="💡 Examples")

        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=20)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        examples = """
COMPLETE USAGE EXAMPLES

Example 1: Reading Own Contexts (self_only permission)
-------------------------------------------------
Send:
{
  "method": "ReadDB",
  "params": {
    "agent_id": "agent_1"
  }
}

Receive:
{
  "success": true,
  "session_id": 1,
  "agent_id": "agent_1",
  "read_permission": "self_only",
  "contexts": [
    {
      "id": 1,
      "agent_id": "agent_1",
      "context": "I completed task A",
      "created_at": "2025-09-28T10:00:00"
    },
    {
      "id": 3,
      "agent_id": "agent_1",
      "context": "Working on task B",
      "created_at": "2025-09-28T11:00:00"
    }
  ]
}

Example 2: Writing New Context
--------------------------
Send:
{
  "method": "WriteDB",
  "params": {
    "agent_id": "agent_1",
    "context": "Started working on new feature X"
  }
}

Receive:
{
  "context": "Started working on new feature X"
}

Example 3: Team-Level Read (team_level permission)
-----------------------------------------------
Send:
{
  "method": "ReadDB",
  "params": {
    "agent_id": "agent_1"
  }
}

Receive:
{
  "success": true,
  "session_id": 1,
  "agent_id": "agent_1",
  "read_permission": "team_level",
  "contexts": [
    {
      "id": 1,
      "agent_id": "agent_1",
      "context": "Task A completed",
      "created_at": "2025-09-28T10:00:00"
    },
    {
      "id": 2,
      "agent_id": "agent_2",
      "context": "Assisting with task A",
      "created_at": "2025-09-28T10:30:00"
    }
  ]
}

Error Example: Unassigned Connection
--------------------------------
Send:
{
  "method": "ReadDB",
  "params": {
    "agent_id": "agent_1"
  }
}

Receive:
{
  "error": "Connection not assigned to any agent"
}

Python Client Example:
-------------------
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
                "context": "Hello from MCP client!"
            }
        }
        await websocket.send(json.dumps(write_msg))
        response = await websocket.recv()
        print("Write response:", json.loads(response))

        # Read contexts
        read_msg = {
            "method": "ReadDB",
            "params": {
                "agent_id": "my_agent"
            }
        }
        await websocket.send(json.dumps(read_msg))
        response = await websocket.recv()
        print("Read response:", json.loads(response))

# Run the example
# asyncio.run(mcp_client_example())
"""

        text_widget.insert('1.0', examples)
        text_widget.config(state='disabled')


class ConnectionAssignmentWidget:
    """Widget for managing agent-connection assignments"""

    def __init__(self, parent):
        self.parent = parent
        self.frame = ttk.LabelFrame(parent, text="🔗 Connection & Agent Assignment", padding=10)
        self.db_path = "multi-agent_mcp_context_manager.db"

    def create_widgets(self):
        """Create assignment management widgets"""
        # Instructions
        instructions = ttk.Label(
            self.frame,
            text="Manage 1-to-1 agent-connection assignments. Each connection must be assigned to exactly one agent.",
            wraplength=600
        )
        instructions.pack(pady=(0, 10))

        # Create main container
        main_container = ttk.Frame(self.frame)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left side - Pending Connections
        left_frame = ttk.LabelFrame(main_container, text="Pending Connections", padding=5)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.connections_tree = ttk.Treeview(
            left_frame,
            columns=('connection_id', 'status', 'first_seen'),
            show='tree headings'
        )
        self.connections_tree.heading('#0', text='#')
        self.connections_tree.heading('connection_id', text='Connection ID')
        self.connections_tree.heading('status', text='Status')
        self.connections_tree.heading('first_seen', text='First Seen')

        # Add scrollbar for connections
        conn_scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.connections_tree.yview)
        self.connections_tree.configure(yscrollcommand=conn_scrollbar.set)

        self.connections_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        conn_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Middle - Assignment Controls
        middle_frame = ttk.Frame(main_container)
        middle_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Label(middle_frame, text="Assignment Actions", font=("Arial", 10, "bold")).pack(pady=(0, 10))

        assign_btn = ttk.Button(
            middle_frame,
            text="Assign Selected →",
            command=self.assign_selected
        )
        assign_btn.pack(pady=5)

        unassign_btn = ttk.Button(
            middle_frame,
            text="← Unassign Selected",
            command=self.unassign_selected
        )
        unassign_btn.pack(pady=5)

        bulk_unassign_btn = ttk.Button(
            middle_frame,
            text="Bulk Unassign",
            command=self.bulk_unassign
        )
        bulk_unassign_btn.pack(pady=5)

        ttk.Separator(middle_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        refresh_btn = ttk.Button(
            middle_frame,
            text="🔄 Refresh",
            command=self.refresh_data
        )
        refresh_btn.pack(pady=5)

        # Right side - Available Agents
        right_frame = ttk.LabelFrame(main_container, text="Available Agents", padding=5)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.agents_tree = ttk.Treeview(
            right_frame,
            columns=('agent_id', 'name', 'connection_id', 'read_permission'),
            show='tree headings'
        )
        self.agents_tree.heading('#0', text='#')
        self.agents_tree.heading('agent_id', text='Agent ID')
        self.agents_tree.heading('name', text='Name')
        self.agents_tree.heading('connection_id', text='Assigned Connection')
        self.agents_tree.heading('read_permission', text='Permission Level')

        # Add scrollbar for agents
        agent_scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.agents_tree.yview)
        self.agents_tree.configure(yscrollcommand=agent_scrollbar.set)

        self.agents_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        agent_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load initial data
        self.refresh_data()

        return self.frame

    def refresh_data(self):
        """Refresh connections and agents data"""
        self.load_connections()
        self.load_agents()

    def load_connections(self):
        """Load connections from database"""
        # Clear existing items
        for item in self.connections_tree.get_children():
            self.connections_tree.delete(item)

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT connection_id, assigned_agent_id, status, first_seen
                    FROM connections
                    ORDER BY first_seen DESC
                ''')

                for i, row in enumerate(cursor.fetchall(), 1):
                    connection_id, assigned_agent_id, status, first_seen = row
                    display_status = f"{status} ({'assigned' if assigned_agent_id else 'pending'})"

                    self.connections_tree.insert(
                        '',
                        'end',
                        text=str(i),
                        values=(connection_id, display_status, first_seen)
                    )
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load connections: {e}")

    def load_agents(self):
        """Load agents from database"""
        # Clear existing items
        for item in self.agents_tree.get_children():
            self.agents_tree.delete(item)

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT assigned_agent_id, name, connection_id, read_permission
                    FROM agents
                    WHERE is_active = 1
                    ORDER BY created_at DESC
                ''')

                for i, row in enumerate(cursor.fetchall(), 1):
                    agent_id, name, connection_id, read_permission = row
                    connection_display = connection_id if connection_id else "Not Assigned"

                    self.agents_tree.insert(
                        '',
                        'end',
                        text=str(i),
                        values=(agent_id, name, connection_display, read_permission)
                    )
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load agents: {e}")

    def assign_selected(self):
        """Assign selected connection to selected agent"""
        # Get selected connection
        conn_selection = self.connections_tree.selection()
        if not conn_selection:
            messagebox.showwarning("Selection Required", "Please select a connection to assign")
            return

        # Get selected agent
        agent_selection = self.agents_tree.selection()
        if not agent_selection:
            messagebox.showwarning("Selection Required", "Please select an agent for assignment")
            return

        # Get values
        conn_values = self.connections_tree.item(conn_selection[0])['values']
        agent_values = self.agents_tree.item(agent_selection[0])['values']

        connection_id = conn_values[0]
        agent_id = agent_values[0]

        # Check if agent is already assigned
        if agent_values[2] != "Not Assigned":
            messagebox.showwarning("Assignment Error", f"Agent {agent_id} is already assigned to connection {agent_values[2]}")
            return

        # Perform assignment
        try:
            response = requests.post(f"http://127.0.0.1:8765/agents/{agent_id}/assign/{connection_id}")
            if response.status_code == 200:
                messagebox.showinfo("Success", f"Successfully assigned agent {agent_id} to connection {connection_id}")
                self.refresh_data()
            else:
                messagebox.showerror("Assignment Failed", f"Failed to assign: {response.text}")
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect to server: {e}")

    def unassign_selected(self):
        """Unassign selected agent from its connection"""
        # Get selected agent
        agent_selection = self.agents_tree.selection()
        if not agent_selection:
            messagebox.showwarning("Selection Required", "Please select an assigned agent to unassign")
            return

        agent_values = self.agents_tree.item(agent_selection[0])['values']
        agent_id = agent_values[0]
        connection_id = agent_values[2]

        if connection_id == "Not Assigned":
            messagebox.showwarning("Assignment Error", f"Agent {agent_id} is not currently assigned")
            return

        # Confirm unassignment
        if not messagebox.askyesno("Confirm Unassignment", f"Unassign agent {agent_id} from connection {connection_id}?"):
            return

        # Perform unassignment
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Clear connection from agent
                cursor.execute('''
                    UPDATE agents
                    SET connection_id = NULL, last_seen = CURRENT_TIMESTAMP
                    WHERE assigned_agent_id = ?
                ''', (agent_id,))

                # Update connection status
                cursor.execute('''
                    UPDATE connections
                    SET assigned_agent_id = NULL, status = 'pending'
                    WHERE connection_id = ?
                ''', (connection_id,))

                conn.commit()
                messagebox.showinfo("Success", f"Successfully unassigned agent {agent_id}")
                self.refresh_data()

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to unassign: {e}")

    def bulk_unassign(self):
        """Bulk unassign multiple agents"""
        # Get all assigned agents
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT assigned_agent_id, connection_id
                    FROM agents
                    WHERE connection_id IS NOT NULL AND is_active = 1
                ''')
                assigned_agents = cursor.fetchall()

            if not assigned_agents:
                messagebox.showinfo("No Assignments", "No agents are currently assigned to connections")
                return

            # Confirm bulk unassignment
            count = len(assigned_agents)
            if not messagebox.askyesno("Confirm Bulk Unassignment", f"Unassign all {count} assigned agents?"):
                return

            # Perform bulk unassignment
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Clear all assignments
                cursor.execute('''
                    UPDATE agents
                    SET connection_id = NULL, last_seen = CURRENT_TIMESTAMP
                    WHERE connection_id IS NOT NULL
                ''')

                cursor.execute('''
                    UPDATE connections
                    SET assigned_agent_id = NULL, status = 'pending'
                    WHERE assigned_agent_id IS NOT NULL
                ''')

                conn.commit()
                messagebox.showinfo("Success", f"Successfully unassigned {count} agents")
                self.refresh_data()

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to perform bulk unassignment: {e}")


def create_enhanced_gui_window():
    """Create the enhanced GUI window with data format instructions"""
    root = tk.Tk()
    root.title("Multi-Agent MCP Context Manager - Enhanced GUI")
    root.geometry("1200x800")

    # Create main notebook
    main_notebook = ttk.Notebook(root)
    main_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Data Format Instructions Tab
    instructions_frame = ttk.Frame(main_notebook)
    main_notebook.add(instructions_frame, text="📋 Data Format Instructions")

    instructions_widget = DataFormatInstructions(instructions_frame)
    instructions_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

    # Connection Assignment Tab
    assignment_frame = ttk.Frame(main_notebook)
    main_notebook.add(assignment_frame, text="🔗 Agent Assignment")

    assignment_widget = ConnectionAssignmentWidget(assignment_frame)
    assignment_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

    return root


if __name__ == "__main__":
    root = create_enhanced_gui_window()
    root.mainloop()