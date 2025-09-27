# Multi-Agent MCP GUI Controller - System Redesign Specification

## Executive Summary

This document provides comprehensive instructions for redesigning the Multi-Agent MCP GUI Controller system to implement a new agent registration and tool selection workflow. The redesign introduces a three-tool selection system (Register, Read, Write) and a structured MCP message schema.

## Current Architecture Analysis

### Existing Components

1. **Main Application (`main.py`)**
   - `PerformantMCPView`: Main GUI class with tabbed interface
   - `CachedMCPDataModel`: Database interface with caching
   - `ConnectionPool`: Database connection management
   - Notebook-based UI with Project View, Agent Management, Team Management tabs

2. **MCP Server (`mcp_server.py`)**
   - FastAPI-based WebSocket server
   - Simple agent announcement system via `{"type": "announce", "agent_id": "...", "name": "..."}`
   - REST endpoints for projects, sessions, agents
   - Basic message echoing and context retrieval

3. **Database Schema**
   - `projects`: id, name, description, timestamps, soft delete
   - `sessions`: id, name, project_id, description, timestamps, soft delete
   - `teams`: id, name, session_id, description, timestamps, soft delete
   - `agents`: id, name, session_id, team_id, status, last_active, timestamps, soft delete
   - **Missing**: `contexts` table (referenced in code but not created in current schema)

### Current Message Flow

1. Agents connect via WebSocket to `/ws/{client_id}`
2. Agents send `{"type": "announce", "agent_id": "...", "name": "..."}` messages
3. Server automatically creates/updates agent record in database
4. GUI displays agents in management interface
5. Human users manually assign agents to sessions/teams

## Required Changes Overview

### New Requirements

1. **Tool Selection System**: Agents must select from Register, Read, Write tools upon connection
2. **Agent Registration Process**: Separate registration step that creates pending agent entries
3. **Human Assignment Process**: GUI interface for humans to assign agent_ids to registered agents
4. **New Message Schema**: `[agent, action, data]` structure for MCP communication
5. **Database Schema Extensions**: Support for agent registration states and tool assignments

## Detailed Implementation Plan

### Phase 1: Database Schema Modifications

#### 1.1 Create Missing Tables

**Add `contexts` table** (currently missing but referenced):
```sql
CREATE TABLE IF NOT EXISTS contexts (
    id TEXT PRIMARY KEY,
    title TEXT,
    content TEXT,
    project_id TEXT,
    session_id TEXT,
    agent_id TEXT,
    sequence_number INTEGER,
    metadata TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);
```

#### 1.2 Modify `agents` table

**Add new columns for registration and tool management**:
```sql
-- Add columns to existing agents table
ALTER TABLE agents ADD COLUMN registration_status TEXT DEFAULT 'pending';
ALTER TABLE agents ADD COLUMN selected_tool TEXT;
ALTER TABLE agents ADD COLUMN assigned_agent_id TEXT;
ALTER TABLE agents ADD COLUMN connection_id TEXT;
ALTER TABLE agents ADD COLUMN capabilities TEXT; -- JSON string for agent capabilities

-- Add indexes for new columns
CREATE INDEX IF NOT EXISTS idx_agents_registration_status ON agents(registration_status);
CREATE INDEX IF NOT EXISTS idx_agents_assigned_agent_id ON agents(assigned_agent_id);
CREATE INDEX IF NOT EXISTS idx_agents_connection_id ON agents(connection_id);
```

**Registration Status Values**:
- `pending`: Agent registered but not yet assigned an agent_id
- `assigned`: Agent has been assigned an agent_id by human
- `active`: Agent is connected and working
- `inactive`: Agent assigned but not currently connected

#### 1.3 Create `agent_tools` table

**New table to manage available tools and permissions**:
```sql
CREATE TABLE IF NOT EXISTS agent_tools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    permissions TEXT, -- JSON string defining what this tool can access
    enabled BOOLEAN DEFAULT 1,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Insert default tools
INSERT INTO agent_tools (id, name, description, permissions) VALUES
('register', 'Register', 'Register as a new agent in the system', '{"read": ["agent_registration"], "write": ["agent_registration"]}'),
('read', 'Read', 'Read data from assigned contexts and sessions', '{"read": ["contexts", "sessions", "projects"], "write": []}'),
('write', 'Write', 'Read and write data to assigned contexts and sessions', '{"read": ["contexts", "sessions", "projects"], "write": ["contexts"]}');
```

#### 1.4 Update Database Initialization

**Modify `CachedMCPDataModel.init_database()` in `main.py`**:

Location: Around line 462 in `main.py`

Add the new table creation statements after the existing table creation code.

### Phase 2: MCP Server Message Schema Redesign

#### 2.1 New Message Schema Implementation

**File**: `mcp_server.py`

**Current schema**: Various message types with different structures

**New schema**: All messages follow `[agent, action, data]` format where:
- `agent`: String identifier for the agent (may be temporary connection_id or assigned agent_id)
- `action`: String action type (register, select_tool, read, write, etc.)
- `data`: Object containing action-specific data

#### 2.2 Update WebSocket Handler

**Replace the current message handling in `websocket_endpoint()` function**:

```python
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Enhanced MCP endpoint with tool selection and registration workflow

    Expected message format: [agent, action, data]

    Initial workflow:
    1. Agent connects and receives tool selection prompt
    2. Agent responds with tool selection
    3. If "register" selected, registration process begins
    4. If "read" or "write" selected, agent must provide assigned_agent_id
    """
    await manager.connect(client_id, websocket)

    # Send initial tool selection prompt
    await manager.send_json(client_id, {
        "type": "tool_selection_prompt",
        "available_tools": ["register", "read", "write"],
        "message": "Please select a tool to continue: register (new agent), read (read-only access), write (read-write access)"
    })

    try:
        while True:
            data = await websocket.receive_text()
            try:
                # Parse new message schema [agent, action, data]
                if data.startswith('[') and data.endswith(']'):
                    msg_array = json.loads(data)
                    if len(msg_array) == 3:
                        agent, action, msg_data = msg_array
                        msg = {"agent": agent, "action": action, "data": msg_data}
                    else:
                        raise ValueError("Invalid message format")
                else:
                    # Fallback for legacy messages
                    msg = json.loads(data)
                    # Convert to new format if possible
                    if "agent_id" in msg:
                        agent = msg.get("agent_id", client_id)
                        action = msg.get("type", "unknown")
                        msg = {"agent": agent, "action": action, "data": msg}
                    else:
                        msg = {"agent": client_id, "action": "legacy", "data": msg}
            except Exception:
                msg = {"agent": client_id, "action": "raw", "data": {"payload": data}}

            logger.info(f"Received from {client_id}: {msg}")

            # Handle tool selection
            if msg.get("action") == "select_tool":
                await handle_tool_selection(client_id, websocket, msg)
                continue

            # Handle registration process
            if msg.get("action") == "register":
                await handle_agent_registration(client_id, websocket, msg)
                continue

            # Handle read/write operations
            if msg.get("action") in ["read", "write"]:
                await handle_agent_operation(client_id, websocket, msg)
                continue

            # Echo for unhandled messages
            await manager.send_json(client_id, {"type": "echo", "original": msg})

    except WebSocketDisconnect:
        await handle_agent_disconnect(client_id)
    except Exception as e:
        logger.exception(f"WebSocket error for {client_id}: {e}")
        await manager.disconnect(client_id)
```

#### 2.3 Add New Handler Functions

**Add these new functions to `mcp_server.py`**:

```python
async def handle_tool_selection(client_id: str, websocket: WebSocket, msg: dict):
    """Handle agent tool selection"""
    selected_tool = msg.get("data", {}).get("tool")
    agent_name = msg.get("data", {}).get("name", f"Agent_{client_id}")

    if selected_tool not in ["register", "read", "write"]:
        await manager.send_json(client_id, {
            "type": "error",
            "message": "Invalid tool selection. Must be 'register', 'read', or 'write'"
        })
        return

    if selected_tool == "register":
        # Start registration process
        await handle_agent_registration(client_id, websocket, msg)
    else:
        # For read/write, require existing agent_id
        await manager.send_json(client_id, {
            "type": "agent_id_required",
            "message": f"To use '{selected_tool}' tool, provide your assigned agent_id",
            "expected_format": f'["{client_id}", "authenticate", {{"agent_id": "your_assigned_id"}}]'
        })

async def handle_agent_registration(client_id: str, websocket: WebSocket, msg: dict):
    """Handle new agent registration"""
    agent_name = msg.get("data", {}).get("name", f"Agent_{client_id}")
    capabilities = msg.get("data", {}).get("capabilities", {})

    def create_pending_agent(name: str, connection_id: str, caps: dict):
        with get_connection() as conn:
            cur = conn.cursor()
            agent_id = f"pending_{connection_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            cur.execute(
                """INSERT INTO agents
                   (id, name, connection_id, registration_status, selected_tool, capabilities, status, last_active)
                   VALUES (?, ?, ?, 'pending', 'register', ?, 'connected', ?)""",
                (agent_id, name, connection_id, json.dumps(caps), datetime.utcnow().isoformat())
            )
            conn.commit()
            return agent_id

    try:
        agent_id = await enqueue_write(create_pending_agent, agent_name, client_id, capabilities)
        await manager.send_json(client_id, {
            "type": "registration_success",
            "agent_id": agent_id,
            "status": "pending",
            "message": "Registration successful. Waiting for human assignment of permanent agent_id."
        })

        # Notify GUI of new pending agent
        await manager.broadcast({
            "type": "new_pending_agent",
            "agent_id": agent_id,
            "name": agent_name,
            "connection_id": client_id
        })

    except Exception as e:
        logger.exception(f"Registration failed for {client_id}: {e}")
        await manager.send_json(client_id, {
            "type": "error",
            "message": "Registration failed"
        })

async def handle_agent_operation(client_id: str, websocket: WebSocket, msg: dict):
    """Handle read/write operations from authenticated agents"""
    assigned_agent_id = msg.get("data", {}).get("agent_id")
    action = msg.get("action")

    if not assigned_agent_id:
        await manager.send_json(client_id, {
            "type": "error",
            "message": "agent_id required for read/write operations"
        })
        return

    # Verify agent exists and is assigned
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT registration_status, selected_tool FROM agents WHERE assigned_agent_id = ? AND deleted_at IS NULL",
            (assigned_agent_id,)
        )
        result = cur.fetchone()

        if not result:
            await manager.send_json(client_id, {
                "type": "error",
                "message": "Invalid agent_id or agent not found"
            })
            return

        if result[0] != "assigned":
            await manager.send_json(client_id, {
                "type": "error",
                "message": "Agent not yet assigned by human administrator"
            })
            return

    # Handle specific operations based on action
    if action == "read":
        await handle_read_operation(client_id, assigned_agent_id, msg.get("data", {}))
    elif action == "write":
        await handle_write_operation(client_id, assigned_agent_id, msg.get("data", {}))

async def handle_read_operation(client_id: str, agent_id: str, data: dict):
    """Handle read operations"""
    # Implementation for reading contexts, sessions, etc.
    # Based on agent permissions and assigned session
    resource_type = data.get("resource_type", "contexts")
    limit = data.get("limit", 10)

    with get_connection() as conn:
        cur = conn.cursor()
        if resource_type == "contexts":
            cur.execute(
                """SELECT c.id, c.title, c.content, c.created_at
                   FROM contexts c
                   JOIN agents a ON c.session_id = a.session_id
                   WHERE a.assigned_agent_id = ? AND c.deleted_at IS NULL
                   ORDER BY c.created_at DESC LIMIT ?""",
                (agent_id, limit)
            )
            results = [dict(r) for r in cur.fetchall()]
            await manager.send_json(client_id, {
                "type": "read_response",
                "resource_type": resource_type,
                "data": results
            })

async def handle_write_operation(client_id: str, agent_id: str, data: dict):
    """Handle write operations"""
    # Implementation for writing contexts
    resource_type = data.get("resource_type", "contexts")
    content = data.get("content", {})

    if resource_type == "contexts":
        def write_context():
            with get_connection() as conn:
                cur = conn.cursor()
                # Get agent's session
                cur.execute(
                    "SELECT session_id, project_id FROM agents a JOIN sessions s ON a.session_id = s.id WHERE a.assigned_agent_id = ?",
                    (agent_id,)
                )
                result = cur.fetchone()
                if not result:
                    raise ValueError("Agent not assigned to a session")

                session_id, project_id = result
                context_id = f"ctx_{session_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"

                cur.execute(
                    """INSERT INTO contexts (id, title, content, project_id, session_id, agent_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (context_id, content.get("title", ""), content.get("content", ""),
                     project_id, session_id, agent_id, datetime.utcnow().isoformat())
                )
                conn.commit()
                return context_id

        try:
            context_id = await enqueue_write(write_context)
            await manager.send_json(client_id, {
                "type": "write_response",
                "resource_type": resource_type,
                "context_id": context_id,
                "status": "success"
            })
        except Exception as e:
            await manager.send_json(client_id, {
                "type": "error",
                "message": f"Write operation failed: {str(e)}"
            })

async def handle_agent_disconnect(client_id: str):
    """Handle agent disconnection"""
    def update_agent_status():
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE agents SET status = 'disconnected', last_active = ? WHERE connection_id = ?",
                (datetime.utcnow().isoformat(), client_id)
            )
            conn.commit()

    try:
        await enqueue_write(update_agent_status)
    except Exception:
        logger.exception(f"Failed to update disconnect status for {client_id}")

    await manager.disconnect(client_id)
```

### Phase 3: GUI Modifications for Agent Assignment

#### 3.1 Add Agent Registration Management Tab

**In `main.py`, modify `setup_ui()` method around line 795**:

Add a new tab for agent registration management:

```python
def setup_ui(self):
    """Setup enhanced UI"""
    # Status bar
    self.status_var = tk.StringVar()
    self.status_var.set("Ready")
    status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
    status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # Main content
    notebook = ttk.Notebook(self.root)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    self.setup_project_view(notebook)
    self.setup_agent_management(notebook)
    self.setup_agent_registration(notebook)  # NEW TAB
    self.setup_team_management(notebook)
    self.setup_performance_monitor(notebook)
    self.setup_admin_tab(notebook)
```

#### 3.2 Implement Agent Registration Tab

**Add this new method to the `PerformantMCPView` class**:

```python
def setup_agent_registration(self, notebook):
    """Agent registration and assignment interface"""
    reg_frame = ttk.Frame(notebook)
    notebook.add(reg_frame, text="Agent Registration")

    # Pending agents section
    pending_frame = ttk.LabelFrame(reg_frame, text="Pending Agent Registrations", padding="10")
    pending_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Pending agents treeview
    self.pending_tree = ttk.Treeview(pending_frame, columns=('name', 'connection_id', 'registered_at', 'capabilities'),
                                   selectmode='single', height=10)
    self.pending_tree.heading('#0', text='Temp ID')
    self.pending_tree.heading('name', text='Agent Name')
    self.pending_tree.heading('connection_id', text='Connection ID')
    self.pending_tree.heading('registered_at', text='Registered At')
    self.pending_tree.heading('capabilities', text='Capabilities')

    # Column widths
    self.pending_tree.column('#0', width=150)
    for col in ('name', 'connection_id', 'registered_at', 'capabilities'):
        self.pending_tree.column(col, width=120)

    self.pending_tree.pack(fill=tk.BOTH, expand=True, pady=5)

    # Assignment interface
    assign_frame = ttk.LabelFrame(reg_frame, text="Assign Agent ID", padding="10")
    assign_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(assign_frame, text="Agent ID:").grid(row=0, column=0, sticky=tk.W, padx=5)
    self.agent_id_entry = ttk.Entry(assign_frame, width=30)
    self.agent_id_entry.grid(row=0, column=1, padx=5)

    ttk.Label(assign_frame, text="Session:").grid(row=0, column=2, sticky=tk.W, padx=(20,5))
    self.assign_session_combo = ttk.Combobox(assign_frame, width=20, state="readonly")
    self.assign_session_combo.grid(row=0, column=3, padx=5)

    ttk.Button(assign_frame, text="Assign Agent ID", command=self.assign_agent_id).grid(row=0, column=4, padx=10)
    ttk.Button(assign_frame, text="Reject Registration", command=self.reject_registration).grid(row=0, column=5, padx=5)

    # Auto-refresh for pending agents
    self.load_pending_agents()

def load_pending_agents(self):
    """Load pending agent registrations"""
    try:
        # Clear existing items
        for item in self.pending_tree.get_children():
            self.pending_tree.delete(item)

        # Load pending agents
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, connection_id, last_active, capabilities
                FROM agents
                WHERE registration_status = 'pending' AND deleted_at IS NULL
                ORDER BY last_active DESC
            ''')

            pending_agents = cursor.fetchall()

            for agent in pending_agents:
                agent_id, name, conn_id, registered_at, capabilities = agent
                caps_display = json.loads(capabilities or '{}')
                caps_str = ', '.join(caps_display.keys()) if caps_display else 'None'

                self.pending_tree.insert('', tk.END, text=agent_id,
                                       values=(name, conn_id, registered_at, caps_str))

        # Load available sessions for assignment
        sessions = self.model.get_sessions()
        session_options = [f"{s['name']} ({s['project_id']})" for s in sessions.values()]
        self.assign_session_combo['values'] = session_options

    except Exception as e:
        logger.error(f"Failed to load pending agents: {e}")

def assign_agent_id(self):
    """Assign permanent agent ID to selected pending agent"""
    selected = self.pending_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a pending agent")
        return

    temp_id = self.pending_tree.item(selected[0])['text']
    new_agent_id = self.agent_id_entry.get().strip()
    selected_session = self.assign_session_combo.get()

    if not new_agent_id:
        messagebox.showwarning("Warning", "Please enter an agent ID")
        return

    if not selected_session:
        messagebox.showwarning("Warning", "Please select a session")
        return

    # Extract session ID from selection
    session_name = selected_session.split(' (')[0]
    sessions = self.model.get_sessions()
    session_id = None
    for sid, session in sessions.items():
        if session['name'] == session_name:
            session_id = sid
            break

    if not session_id:
        messagebox.showerror("Error", "Invalid session selection")
        return

    try:
        with self.model.pool.get_connection() as conn:
            cursor = conn.cursor()

            # Check if agent ID already exists
            cursor.execute("SELECT id FROM agents WHERE assigned_agent_id = ? AND deleted_at IS NULL", (new_agent_id,))
            if cursor.fetchone():
                messagebox.showerror("Error", f"Agent ID '{new_agent_id}' already exists")
                return

            # Update the pending agent
            cursor.execute('''
                UPDATE agents
                SET assigned_agent_id = ?, registration_status = 'assigned', session_id = ?, updated_at = ?
                WHERE id = ?
            ''', (new_agent_id, session_id, datetime.now().isoformat(), temp_id))

            conn.commit()

            # Add to allowlist if enabled
            self.ensure_agent_allowlisted(new_agent_id)

            messagebox.showinfo("Success", f"Agent ID '{new_agent_id}' assigned successfully")

            # Refresh displays
            self.load_pending_agents()
            self.load_agent_data()

            # Notify the agent via WebSocket if server is available
            self.notify_agent_assignment(temp_id, new_agent_id)

    except Exception as e:
        logger.error(f"Failed to assign agent ID: {e}")
        messagebox.showerror("Error", f"Failed to assign agent ID: {e}")

def reject_registration(self):
    """Reject pending agent registration"""
    selected = self.pending_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a pending agent")
        return

    temp_id = self.pending_tree.item(selected[0])['text']

    if messagebox.askyesno("Confirm", "Are you sure you want to reject this registration?"):
        try:
            with self.model.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE agents SET deleted_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), temp_id)
                )
                conn.commit()

            messagebox.showinfo("Success", "Registration rejected")
            self.load_pending_agents()

        except Exception as e:
            logger.error(f"Failed to reject registration: {e}")
            messagebox.showerror("Error", f"Failed to reject registration: {e}")

def notify_agent_assignment(self, temp_id: str, assigned_agent_id: str):
    """Notify agent of successful assignment via WebSocket"""
    try:
        if self.server_subscriber and hasattr(self.server_subscriber, 'send_message'):
            # This would require implementing a way to send messages back to the server
            # For now, this is a placeholder for future implementation
            pass
    except Exception:
        logger.debug("Could not notify agent of assignment (normal if server not accessible)")
```

#### 3.3 Update Agent Management Tab

**Modify the existing `setup_agent_management()` method to show registration status**:

Around line 886 in the agent_tree setup:

```python
# Agent treeview with registration status
self.agent_tree = ttk.Treeview(list_frame, columns=('name', 'assigned_id', 'registration_status', 'session', 'team', 'status'),
                              selectmode='extended', height=15)
self.agent_tree.heading('#0', text='Temp ID')
self.agent_tree.heading('name', text='Name')
self.agent_tree.heading('assigned_id', text='Assigned ID')
self.agent_tree.heading('registration_status', text='Registration')
self.agent_tree.heading('session', text='Session')
self.agent_tree.heading('team', text='Team')
self.agent_tree.heading('status', text='Status')

# Column widths
self.agent_tree.column('#0', width=120)
for col in ('name', 'assigned_id', 'registration_status', 'session', 'team', 'status'):
    self.agent_tree.column(col, width=100)
```

#### 3.4 Update Data Loading Methods

**Modify `load_agent_data()` method to include new fields**:

```python
def load_agent_data(self):
    """Load agent data with registration information"""
    try:
        # Clear existing items
        for item in self.agent_tree.get_children():
            self.agent_tree.delete(item)

        agents = self.model.get_agents()
        for agent_id, agent in agents.items():
            # Get session and team names
            session_name = "None"
            team_name = "None"

            if agent.get('session_id'):
                sessions = self.model.get_sessions()
                session = sessions.get(agent['session_id'], {})
                session_name = session.get('name', 'Unknown')

            if agent.get('team_id'):
                teams = self.model.get_teams()
                team = teams.get(agent['team_id'], {})
                team_name = team.get('name', 'Unknown')

            self.agent_tree.insert('', tk.END, text=agent_id,
                                 values=(
                                     agent.get('name', ''),
                                     agent.get('assigned_agent_id', 'N/A'),
                                     agent.get('registration_status', 'unknown'),
                                     session_name,
                                     team_name,
                                     agent.get('status', 'unknown')
                                 ))

        # Update status
        agent_count = len(agents)
        self.status_var.set(f"Loaded {agent_count} agents")

    except Exception as e:
        logger.error(f"Failed to load agent data: {e}")
        self.status_var.set(f"Error loading agents: {e}")
```

### Phase 4: Migration Strategy

#### 4.1 Database Migration Script

**Create `migrate_database.py`**:

```python
"""Database migration script for agent registration redesign"""
import sqlite3
import json
from datetime import datetime

def migrate_database(db_path: str = "multi-agent_mcp_context_manager.db"):
    """Migrate existing database to support new agent registration system"""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Add new columns to agents table
        new_columns = [
            ("registration_status", "TEXT DEFAULT 'assigned'"),  # Existing agents are considered assigned
            ("selected_tool", "TEXT DEFAULT 'write'"),  # Existing agents get write access
            ("assigned_agent_id", "TEXT"),
            ("connection_id", "TEXT"),
            ("capabilities", "TEXT DEFAULT '{}'")
        ]

        for column_name, column_def in new_columns:
            try:
                cursor.execute(f"ALTER TABLE agents ADD COLUMN {column_name} {column_def}")
                print(f"Added column {column_name} to agents table")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"Column {column_name} already exists")
                else:
                    raise

        # For existing agents, set assigned_agent_id to their current id
        cursor.execute("UPDATE agents SET assigned_agent_id = id WHERE assigned_agent_id IS NULL")
        print("Updated existing agents with assigned_agent_id")

        # Create contexts table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contexts (
                id TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                project_id TEXT,
                session_id TEXT,
                agent_id TEXT,
                sequence_number INTEGER,
                metadata TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                deleted_at TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            )
        ''')
        print("Created contexts table")

        # Create agent_tools table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_tools (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                permissions TEXT,
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')

        # Insert default tools
        tools = [
            ('register', 'Register', 'Register as a new agent in the system',
             '{"read": ["agent_registration"], "write": ["agent_registration"]}'),
            ('read', 'Read', 'Read data from assigned contexts and sessions',
             '{"read": ["contexts", "sessions", "projects"], "write": []}'),
            ('write', 'Write', 'Read and write data to assigned contexts and sessions',
             '{"read": ["contexts", "sessions", "projects"], "write": ["contexts"]}')
        ]

        now = datetime.utcnow().isoformat()
        for tool_id, name, desc, perms in tools:
            cursor.execute('''
                INSERT OR REPLACE INTO agent_tools (id, name, description, permissions, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (tool_id, name, desc, perms, now, now))

        print("Created agent_tools table and inserted default tools")

        # Create new indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_agents_registration_status ON agents(registration_status)",
            "CREATE INDEX IF NOT EXISTS idx_agents_assigned_agent_id ON agents(assigned_agent_id)",
            "CREATE INDEX IF NOT EXISTS idx_agents_connection_id ON agents(connection_id)",
            "CREATE INDEX IF NOT EXISTS idx_contexts_agent_recent ON contexts(agent_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_contexts_session_recent ON contexts(session_id, created_at DESC)"
        ]

        for index_sql in indexes:
            cursor.execute(index_sql)

        print("Created new indexes")

        conn.commit()
        print("Migration completed successfully")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
```

#### 4.2 Backward Compatibility

**For the transition period, support both old and new message formats**:

1. Keep legacy message handling in WebSocket endpoint
2. Automatically convert old `{"type": "announce", "agent_id": "..."}` to new format
3. Existing agents continue to work with `assigned_agent_id` set to their current `id`

### Phase 5: Testing and Validation

#### 5.1 Create Test Scripts

**Create `test_new_workflow.py`**:

```python
"""Test script for new agent registration workflow"""
import asyncio
import websockets
import json

async def test_agent_registration():
    """Test the full agent registration workflow"""

    uri = "ws://localhost:8765/ws/test_client_1"

    async with websockets.connect(uri) as websocket:
        # Should receive tool selection prompt
        response = await websocket.recv()
        prompt = json.loads(response)
        print(f"Received prompt: {prompt}")

        # Select register tool
        register_msg = ["test_client_1", "select_tool", {"tool": "register", "name": "Test Agent", "capabilities": {"nlp": True, "vision": False}}]
        await websocket.send(json.dumps(register_msg))

        # Should receive registration success
        response = await websocket.recv()
        result = json.loads(response)
        print(f"Registration result: {result}")

async def test_agent_read_write():
    """Test read/write operations with assigned agent"""

    uri = "ws://localhost:8765/ws/test_client_2"

    async with websockets.connect(uri) as websocket:
        # Should receive tool selection prompt
        await websocket.recv()

        # Select write tool
        select_msg = ["test_client_2", "select_tool", {"tool": "write"}]
        await websocket.send(json.dumps(select_msg))

        # Should receive agent_id required message
        response = await websocket.recv()
        print(f"Tool selection response: {json.loads(response)}")

        # Authenticate with assigned agent_id
        auth_msg = ["test_client_2", "authenticate", {"agent_id": "assigned_agent_123"}]
        await websocket.send(json.dumps(auth_msg))

        # Try to write a context
        write_msg = ["assigned_agent_123", "write", {
            "resource_type": "contexts",
            "content": {
                "title": "Test Context",
                "content": "This is a test context created by the agent"
            }
        }]
        await websocket.send(json.dumps(write_msg))

        response = await websocket.recv()
        print(f"Write response: {json.loads(response)}")

if __name__ == "__main__":
    asyncio.run(test_agent_registration())
    asyncio.run(test_agent_read_write())
```

#### 5.2 GUI Testing Checklist

1. **Agent Registration Tab**:
   - [ ] Pending agents display correctly
   - [ ] Agent ID assignment works
   - [ ] Session selection populates correctly
   - [ ] Registration rejection works
   - [ ] Real-time updates from WebSocket

2. **Agent Management Tab**:
   - [ ] New columns display correctly
   - [ ] Registration status shows properly
   - [ ] Existing functionality still works

3. **WebSocket Communication**:
   - [ ] Tool selection prompt sent on connection
   - [ ] New message schema [agent, action, data] parsed correctly
   - [ ] Legacy message format still supported
   - [ ] Error handling for invalid messages

### Phase 6: Deployment Steps

#### 6.1 Pre-deployment

1. **Backup existing database**:
   ```bash
   cp multi-agent_mcp_context_manager.db multi-agent_mcp_context_manager.db.backup
   ```

2. **Run migration script**:
   ```bash
   python migrate_database.py
   ```

3. **Test with backup data**:
   - Verify existing agents still work
   - Test GUI displays correctly
   - Test WebSocket connections

#### 6.2 Deployment

1. **Update application files**:
   - Replace `main.py` with updated version
   - Replace `mcp_server.py` with updated version
   - Add new test scripts

2. **Restart services**:
   - Stop any running MCP server instances
   - Restart the main application
   - Verify server auto-starts correctly

3. **Validation**:
   - Test agent registration workflow
   - Verify existing agents continue to work
   - Test GUI functionality

### Phase 7: Documentation Updates

#### 7.1 User Documentation

**Update README.md** with new workflow:

```markdown
## Agent Connection Workflow

### For New Agents

1. Connect to WebSocket endpoint: `ws://localhost:8765/ws/{client_id}`
2. Receive tool selection prompt
3. Send tool selection: `["{client_id}", "select_tool", {"tool": "register", "name": "Agent Name", "capabilities": {...}}]`
4. Wait for human administrator to assign permanent agent_id
5. Receive assignment notification

### For Existing Agents

1. Connect to WebSocket endpoint: `ws://localhost:8765/ws/{client_id}`
2. Receive tool selection prompt
3. Send tool selection: `["{client_id}", "select_tool", {"tool": "read|write"}]`
4. Authenticate: `["{client_id}", "authenticate", {"agent_id": "your_assigned_id"}]`
5. Begin operations

### Message Schema

All messages follow the format: `[agent, action, data]`

- `agent`: String identifier (connection_id or assigned_agent_id)
- `action`: String action type
- `data`: Object with action-specific data
```

#### 7.2 API Documentation

Document the new WebSocket API endpoints and message types for agent developers.

## Summary

This redesign introduces a structured agent registration and tool selection system while maintaining backward compatibility. The key changes are:

1. **Three-tool selection system**: Register, Read, Write
2. **Structured registration process**: Agents register → humans assign IDs → agents operate
3. **New message schema**: `[agent, action, data]` format
4. **Enhanced GUI**: New registration management tab
5. **Database extensions**: Support for registration states and tool permissions

The implementation maintains existing functionality while adding the new workflow, ensuring a smooth transition for existing users and agents.
