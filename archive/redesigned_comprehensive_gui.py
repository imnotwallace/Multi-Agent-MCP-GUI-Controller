#!/usr/bin/env python3
"""
Redesigned Comprehensive GUI for Multi-Agent MCP Context Manager
Implements specifications from .claude/Instructions/20250928_0159_instructions.md

Features:
1. Redesigned Connection Assignment screen (left: connections, right: agents)
2. Enhanced Agent Management with bulk operations and file import
3. New Contexts screen with full CRUD operations
4. Teams TreeView management
5. Status bar with live counts and server info
6. No allowlist functionality (removed as per requirements)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
import json
import sqlite3
import requests
import os
import csv
from datetime import datetime
from typing import Dict, List, Optional, Set
import threading
import time
import queue

class ValidationManager:
    """Centralized validation for database operations"""

    def __init__(self, db_manager):
        self.db_manager = db_manager

    def validate_project_name(self, name, exclude_id=None):
        """Validate project name for duplicates and constraints"""
        if not name or not name.strip():
            return False, "Project name cannot be empty"

        name = name.strip()
        if len(name) > 100:
            return False, "Project name cannot exceed 100 characters"

        # Check for duplicates across entire database
        query = "SELECT id, name FROM projects WHERE LOWER(name) = LOWER(?)"
        params = [name]

        if exclude_id:
            query += " AND id != ?"
            params.append(exclude_id)

        existing = self.db_manager.execute_query(query, params)
        if existing:
            return False, f"Project '{name}' already exists (ID: {existing[0][0]})"

        return True, ""

    def validate_session_name(self, name, project_id=None, exclude_id=None):
        """Validate session name for duplicates and constraints"""
        if not name or not name.strip():
            return False, "Session name cannot be empty"

        name = name.strip()
        if len(name) > 100:
            return False, "Session name cannot exceed 100 characters"

        # Check for duplicates across entire database, not just within project
        query = "SELECT s.id, s.name, p.name FROM sessions s JOIN projects p ON s.project_id = p.id WHERE LOWER(s.name) = LOWER(?)"
        params = [name]

        if exclude_id:
            query += " AND s.id != ?"
            params.append(exclude_id)

        existing = self.db_manager.execute_query(query, params)
        if existing:
            return False, f"Session '{name}' already exists in project '{existing[0][2]}' (ID: {existing[0][0]})"

        return True, ""

    def validate_agent_name(self, name, exclude_id=None):
        """Validate agent name for duplicates and constraints"""
        if not name or not name.strip():
            return False, "Agent name cannot be empty"

        name = name.strip()
        if len(name) > 50:
            return False, "Agent name cannot exceed 50 characters"

        # Check for duplicates
        query = "SELECT agent_id, name FROM agents WHERE LOWER(name) = LOWER(?)"
        params = [name]

        if exclude_id:
            query += " AND agent_id != ?"
            params.append(exclude_id)

        existing = self.db_manager.execute_query(query, params)
        if existing:
            return False, f"Agent name '{name}' already exists (ID: {existing[0][0]})"

        return True, ""

class DatabaseManager:
    """Handles all database operations for the redesigned system with connection pooling"""

    def __init__(self, db_path="multi-agent_mcp_context_manager.db", pool_size=5):
        self.db_path = db_path
        self.pool_size = pool_size
        self.connection_pool = queue.Queue(maxsize=pool_size)
        self.pool_lock = threading.Lock()

        # Initialize connection pool
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize the connection pool"""
        for _ in range(self.pool_size):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL mode for better concurrency
            conn.execute("PRAGMA synchronous=NORMAL")  # Better performance
            conn.execute("PRAGMA cache_size=1000")  # Increase cache size
            conn.execute("PRAGMA temp_store=memory")  # Store temp tables in memory
            self.connection_pool.put(conn)

    def get_connection(self):
        """Get a connection from the pool"""
        try:
            conn = self.connection_pool.get(timeout=5)
            return conn
        except queue.Empty:
            # If pool is empty, create a new connection
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=1000")
            conn.execute("PRAGMA temp_store=memory")
            return conn

    def return_connection(self, conn):
        """Return a connection to the pool"""
        try:
            self.connection_pool.put_nowait(conn)
        except queue.Full:
            # Pool is full, close the connection
            conn.close()

    def close_pool(self):
        """Close all connections in the pool"""
        with self.pool_lock:
            while not self.connection_pool.empty():
                try:
                    conn = self.connection_pool.get_nowait()
                    conn.close()
                except queue.Empty:
                    break

    def execute_query(self, query, params=None):
        """Execute a query and return results using connection pool"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            result = cursor.fetchall()
            return result
        except Exception as e:
            # Log error but don't crash the application
            print(f"Database query error: {e}")
            raise
        finally:
            self.return_connection(conn)

    def execute_update(self, query, params=None):
        """Execute an update/insert/delete query using connection pool"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            conn.rollback()
            print(f"Database update error: {e}")
            raise
        finally:
            self.return_connection(conn)

class ServerStatusMonitor:
    """Monitors server status and connection counts"""

    def __init__(self, status_callback):
        self.status_callback = status_callback
        self.server_url = "http://127.0.0.1:8765"
        self.running = False
        self.thread = None

    def start_monitoring(self):
        """Start monitoring server status"""
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def stop_monitoring(self):
        """Stop monitoring server status"""
        self.running = False

    def _monitor_loop(self):
        """Continuous monitoring loop"""
        while self.running:
            try:
                # Get server status
                response = requests.get(f"{self.server_url}/status", timeout=2)
                if response.status_code == 200:
                    status_data = response.json()

                    # Get additional counts
                    agents_response = requests.get(f"{self.server_url}/agents", timeout=2)
                    agents_count = len(agents_response.json().get("agents", [])) if agents_response.status_code == 200 else 0

                    self.status_callback({
                        "server_status": "running",
                        "active_connections": status_data.get("active_connections", 0),
                        "registered_agents": agents_count,
                        "database_status": status_data.get("database", "unknown"),
                        "server_address": "127.0.0.1:8765"
                    })
                else:
                    self.status_callback({
                        "server_status": "error",
                        "active_connections": 0,
                        "registered_agents": 0,
                        "database_status": "unknown",
                        "server_address": "127.0.0.1:8765"
                    })
            except requests.RequestException:
                self.status_callback({
                    "server_status": "stopped",
                    "active_connections": 0,
                    "registered_agents": 0,
                    "database_status": "disconnected",
                    "server_address": "127.0.0.1:8765"
                })

            time.sleep(5)  # Update every 5 seconds

class ConnectionAssignmentTab:
    """Redesigned Connection Assignment screen as per requirements"""

    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db_manager = db_manager
        self.frame = ttk.Frame(parent)

    def create_widgets(self):
        """Create the redesigned connection assignment interface"""
        # Title
        title_label = ttk.Label(
            self.frame,
            text="🔗 Connection Assignment",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(10, 20))

        # Main container with left and right panels
        main_container = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # LEFT SIDE - Active Connections
        self.create_connections_panel(main_container)

        # RIGHT SIDE - Registered Agents
        self.create_agents_panel(main_container)

        return self.frame

    def create_connections_panel(self, parent):
        """Create left panel for active connections"""
        left_frame = ttk.LabelFrame(parent, text="Active Connections", padding=10)
        parent.add(left_frame, weight=1)

        # Search/Filter box
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text="Filter:").pack(side=tk.LEFT)
        self.connection_filter_var = tk.StringVar()
        self.connection_filter_var.trace("w", self.filter_connections)
        filter_entry = ttk.Entry(search_frame, textvariable=self.connection_filter_var, width=20)
        filter_entry.pack(side=tk.LEFT, padx=(5, 10))

        # Refresh button
        ttk.Button(search_frame, text="🔄 Refresh", command=self.refresh_connections).pack(side=tk.RIGHT)

        # Connections tree
        columns = ('connection_id', 'ip_address', 'timestamp', 'status')
        self.connections_tree = ttk.Treeview(
            left_frame,
            columns=columns,
            show='tree headings',
            height=18
        )

        # Configure columns
        self.connections_tree.heading('#0', text='#')
        self.connections_tree.heading('connection_id', text='Connection ID')
        self.connections_tree.heading('ip_address', text='IP Address')
        self.connections_tree.heading('timestamp', text='Connected')
        self.connections_tree.heading('status', text='Status')

        # Set column widths
        self.connections_tree.column('#0', width=30)
        self.connections_tree.column('connection_id', width=150)
        self.connections_tree.column('ip_address', width=100)
        self.connections_tree.column('timestamp', width=120)
        self.connections_tree.column('status', width=80)

        # Make columns sortable
        for col in columns:
            self.connections_tree.heading(col, command=lambda c=col: self.sort_connections(c))

        # Add scrollbar
        conn_scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.connections_tree.yview)
        self.connections_tree.configure(yscrollcommand=conn_scrollbar.set)

        # Pack tree and scrollbar
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.connections_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        conn_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Connection control buttons
        conn_buttons = ttk.Frame(left_frame)
        conn_buttons.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(conn_buttons, text="🚫 Disconnect", command=self.disconnect_connection).pack(side=tk.LEFT, padx=(0, 5))

        # Load initial data
        self.refresh_connections()

    def create_agents_panel(self, parent):
        """Create right panel for registered agents"""
        right_frame = ttk.LabelFrame(parent, text="Registered Agents", padding=10)
        parent.add(right_frame, weight=1)

        # Search/Filter box
        search_frame = ttk.Frame(right_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text="Filter:").pack(side=tk.LEFT)
        self.agent_filter_var = tk.StringVar()
        self.agent_filter_var.trace("w", self.filter_agents)
        filter_entry = ttk.Entry(search_frame, textvariable=self.agent_filter_var, width=20)
        filter_entry.pack(side=tk.LEFT, padx=(5, 10))

        # Refresh button
        ttk.Button(search_frame, text="🔄 Refresh", command=self.refresh_agents).pack(side=tk.RIGHT)

        # Agents tree
        columns = ('agent_id', 'permission_level', 'teams', 'connection_id')
        self.agents_tree = ttk.Treeview(
            right_frame,
            columns=columns,
            show='tree headings',
            height=18
        )

        # Configure columns
        self.agents_tree.heading('#0', text='#')
        self.agents_tree.heading('agent_id', text='Agent ID')
        self.agents_tree.heading('permission_level', text='Permission')
        self.agents_tree.heading('teams', text='Teams')
        self.agents_tree.heading('connection_id', text='Connection')

        # Set column widths
        self.agents_tree.column('#0', width=30)
        self.agents_tree.column('agent_id', width=120)
        self.agents_tree.column('permission_level', width=80)
        self.agents_tree.column('teams', width=100)
        self.agents_tree.column('connection_id', width=120)

        # Make columns sortable
        for col in columns:
            self.agents_tree.heading(col, command=lambda c=col: self.sort_agents(c))

        # Add scrollbar
        agent_scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.agents_tree.yview)
        self.agents_tree.configure(yscrollcommand=agent_scrollbar.set)

        # Pack tree and scrollbar
        tree_frame = ttk.Frame(right_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.agents_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        agent_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load initial data
        self.refresh_agents()

    def refresh_connections(self):
        """Refresh connections display"""
        try:
            response = requests.get("http://127.0.0.1:8765/connections", timeout=5)
            if response.status_code == 200:
                connections = response.json().get("connections", [])
                self.populate_connections_tree(connections)
            else:
                # Fallback to database
                connections = self.db_manager.execute_query('''
                    SELECT connection_id, ip_address, assigned_agent_id, status, first_seen, last_seen
                    FROM connections
                    ORDER BY first_seen DESC
                ''')
                formatted_connections = [
                    {
                        "connection_id": row[0],
                        "ip_address": row[1] or "Unknown",
                        "assigned_agent_id": row[2],
                        "status": row[3],
                        "first_seen": row[4],
                        "last_seen": row[5]
                    }
                    for row in connections
                ]
                self.populate_connections_tree(formatted_connections)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load connections: {e}")

    def populate_connections_tree(self, connections):
        """Populate connections tree with data"""
        # Clear existing items
        for item in self.connections_tree.get_children():
            self.connections_tree.delete(item)

        for i, conn in enumerate(connections, 1):
            status_icon = "🟢" if conn.get("status") == "assigned" else "🔴"
            self.connections_tree.insert(
                '',
                'end',
                text=str(i),
                values=(
                    conn.get("connection_id"),
                    conn.get("ip_address", "Unknown"),
                    conn.get("first_seen", "Unknown"),
                    f"{status_icon} {conn.get('status', 'pending')}"
                )
            )

    def refresh_agents(self):
        """Refresh agents display"""
        try:
            response = requests.get("http://127.0.0.1:8765/agents", timeout=5)
            if response.status_code == 200:
                agents = response.json().get("agents", [])
                self.populate_agents_tree(agents)
            else:
                # Fallback to database
                agents = self.db_manager.execute_query('''
                    SELECT agent_id, name, permission_level, teams, connection_id, is_active
                    FROM agents
                    ORDER BY agent_id
                ''')
                formatted_agents = [
                    {
                        "agent_id": row[0],
                        "name": row[1],
                        "permission_level": row[2],
                        "teams": json.loads(row[3]) if row[3] else [],
                        "connection_id": row[4],
                        "is_active": row[5]
                    }
                    for row in agents
                ]
                self.populate_agents_tree(formatted_agents)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load agents: {e}")

    def populate_agents_tree(self, agents):
        """Populate agents tree with data"""
        # Clear existing items
        for item in self.agents_tree.get_children():
            self.agents_tree.delete(item)

        for i, agent in enumerate(agents, 1):
            status_icon = "🟢" if agent.get("connection_id") else "🔴"
            teams_str = ", ".join(agent.get("teams", []))
            self.agents_tree.insert(
                '',
                'end',
                text=str(i),
                values=(
                    agent.get("agent_id"),
                    agent.get("permission_level", "self"),
                    teams_str,
                    f"{status_icon} {agent.get('connection_id', 'Not Connected')}"
                )
            )

    def filter_connections(self, *args):
        """Filter connections based on search text"""
        filter_text = self.connection_filter_var.get().lower()
        self.refresh_connections()  # For now, just refresh - could implement actual filtering

    def filter_agents(self, *args):
        """Filter agents based on search text"""
        filter_text = self.agent_filter_var.get().lower()
        self.refresh_agents()  # For now, just refresh - could implement actual filtering

    def sort_connections(self, column):
        """Sort connections by column"""
        # Get current items from tree
        items = [(self.connections_tree.set(child, column), child) for child in self.connections_tree.get_children('')]

        # Sort items
        items.sort(reverse=getattr(self, f'_reverse_connections_{column}', False))

        # Rearrange items in sorted order
        for index, (val, child) in enumerate(items):
            self.connections_tree.move(child, '', index)

        # Toggle sort direction for next click
        setattr(self, f'_reverse_connections_{column}', not getattr(self, f'_reverse_connections_{column}', False))

    def sort_agents(self, column):
        """Sort agents by column"""
        # Get current items from tree
        items = [(self.agents_tree.set(child, column), child) for child in self.agents_tree.get_children('')]

        # Sort items
        items.sort(reverse=getattr(self, f'_reverse_agents_{column}', False))

        # Rearrange items in sorted order
        for index, (val, child) in enumerate(items):
            self.agents_tree.move(child, '', index)

        # Toggle sort direction for next click
        setattr(self, f'_reverse_agents_{column}', not getattr(self, f'_reverse_agents_{column}', False))

    def disconnect_connection(self):
        """Disconnect selected connection"""
        selection = self.connections_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a connection to disconnect")
            return

        connection_id = self.connections_tree.item(selection[0])['values'][0]
        if messagebox.askyesno("Confirm", f"Disconnect connection {connection_id}?"):
            try:
                # Update connection status in database
                self.db_manager.execute_update(
                    "UPDATE connections SET status = 'disconnected', assigned_agent_id = NULL WHERE connection_id = ?",
                    (connection_id,)
                )
                self.refresh_connections()
                messagebox.showinfo("Success", f"Connection {connection_id} disconnected")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to disconnect: {e}")

class AgentManagementTab:
    """Enhanced Agent Management with all specified functionality"""

    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db_manager = db_manager
        self.frame = ttk.Frame(parent)

    def create_widgets(self):
        """Create enhanced agent management interface"""
        # Title
        title_label = ttk.Label(
            self.frame,
            text="👥 Agent Management",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(10, 20))

        # Create notebook for subtabs
        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Agent List Tab
        self.create_agent_list_tab()

        # Teams Tab
        self.create_teams_tab()

        return self.frame

    def create_agent_list_tab(self):
        """Create agent list tab with enhanced functionality"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="🏷️ Agent List")

        # Button panel - placed above grid for full width
        self.create_agent_buttons(frame)

        # Agent grid - full width
        self.create_agent_grid(frame)

    def create_agent_buttons(self, parent):
        """Create agent management buttons"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        # Row 1 - Basic operations
        row1 = ttk.Frame(button_frame)
        row1.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(row1, text="➕ Add Agent", command=self.add_agent).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row1, text="🗑️ Delete Selected", command=self.delete_agents).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row1, text="✏️ Change Permission", command=self.change_permission).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row1, text="🔄 Refresh", command=self.refresh_agent_list).pack(side=tk.RIGHT)

        # Row 2 - Team operations
        row2 = ttk.Frame(button_frame)
        row2.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(row2, text="👥 Assign to Team", command=self.assign_to_team).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row2, text="👥 Remove from Team", command=self.remove_from_team).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row2, text="📊 Export CSV", command=self.export_csv).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row2, text="📁 Import from MD", command=self.import_from_markdown).pack(side=tk.LEFT, padx=(0, 5))

        # Search frame
        search_frame = ttk.Frame(button_frame)
        search_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(search_frame, text="Search/Filter:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.filter_agents)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(5, 10))

    def create_agent_grid(self, parent):
        """Create agent grid with full functionality"""
        # Grid frame
        grid_frame = ttk.Frame(parent)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Agent tree - full width
        columns = ('agent_id', 'permission_level', 'teams', 'connection_id')
        self.agent_tree = ttk.Treeview(
            grid_frame,
            columns=columns,
            show='tree headings',
            selectmode='extended'  # Allow multiple selection
        )

        # Configure columns
        self.agent_tree.heading('#0', text='#')
        self.agent_tree.heading('agent_id', text='Agent ID')
        self.agent_tree.heading('permission_level', text='Permission Level')
        self.agent_tree.heading('teams', text='Teams')
        self.agent_tree.heading('connection_id', text='Connection ID')

        # Set column widths for full width
        self.agent_tree.column('#0', width=50)
        self.agent_tree.column('agent_id', width=200)
        self.agent_tree.column('permission_level', width=150)
        self.agent_tree.column('teams', width=200)
        self.agent_tree.column('connection_id', width=200)

        # Make columns sortable
        for col in columns:
            self.agent_tree.heading(col, command=lambda c=col: self.sort_agent_column(c))

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL, command=self.agent_tree.yview)
        h_scrollbar = ttk.Scrollbar(grid_frame, orient=tk.HORIZONTAL, command=self.agent_tree.xview)
        self.agent_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack grid and scrollbars
        self.agent_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        # Configure grid weights
        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(0, weight=1)

        # Load initial data
        self.refresh_agent_list()

    def create_teams_tab(self):
        """Create teams tab with TreeView"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="👥 Teams")

        # Team management buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="➕ Add Team", command=self.add_team).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🗑️ Delete Team", command=self.delete_team).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="✏️ Rename Team", command=self.rename_team).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="👥 Add Agent to Team", command=self.add_agent_to_team).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🔄 Refresh", command=self.refresh_teams).pack(side=tk.RIGHT)

        # Search frame
        search_frame = ttk.Frame(frame)
        search_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(search_frame, text="Search Teams/Agents:").pack(side=tk.LEFT)
        self.team_search_var = tk.StringVar()
        self.team_search_var.trace("w", self.filter_teams)
        search_entry = ttk.Entry(search_frame, textvariable=self.team_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(5, 10))

        ttk.Button(search_frame, text="📊 Export Teams CSV", command=self.export_teams_csv).pack(side=tk.RIGHT)

        # Teams TreeView
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.teams_tree = ttk.Treeview(tree_frame, show='tree')
        self.teams_tree.heading('#0', text='Teams and Agents')

        # Add scrollbar
        team_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.teams_tree.yview)
        self.teams_tree.configure(yscrollcommand=team_scrollbar.set)

        # Pack tree and scrollbar
        self.teams_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        team_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load initial teams data
        self.refresh_teams()

    # Agent List Tab Methods
    def refresh_agent_list(self):
        """Refresh the agent list"""
        # Clear existing items
        for item in self.agent_tree.get_children():
            self.agent_tree.delete(item)

        try:
            agents = self.db_manager.execute_query('''
                SELECT agent_id, name, permission_level, teams, connection_id, is_active
                FROM agents
                WHERE is_active = 1
                ORDER BY agent_id
            ''')

            for i, agent in enumerate(agents, 1):
                agent_id, name, permission_level, teams_json, connection_id, is_active = agent

                # Parse teams
                teams = []
                if teams_json:
                    try:
                        teams = json.loads(teams_json)
                    except json.JSONDecodeError:
                        teams = []

                teams_str = ", ".join(teams) if teams else "None"
                connection_str = connection_id if connection_id else "Not Connected"

                self.agent_tree.insert(
                    '',
                    'end',
                    text=str(i),
                    values=(agent_id, permission_level, teams_str, connection_str)
                )

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load agents: {e}")

    def add_agent(self):
        """Add a new agent with permission level and teams"""
        dialog = AgentCreateDialog(self.frame, self.db_manager)
        result = dialog.show()

        if result:
            agent_id, permission_level, teams = result
            try:
                teams_json = json.dumps(teams) if teams else None
                self.db_manager.execute_update('''
                    INSERT INTO agents (agent_id, name, permission_level, teams, is_active)
                    VALUES (?, ?, ?, ?, 1)
                ''', (agent_id, agent_id, permission_level, teams_json))

                self.refresh_agent_list()
                messagebox.showinfo("Success", f"Agent {agent_id} added successfully")
            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to add agent: {e}")

    def delete_agents(self):
        """Delete selected agents with confirmation"""
        selection = self.agent_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select agents to delete")
            return

        agent_ids = [self.agent_tree.item(item)['values'][0] for item in selection]
        count = len(agent_ids)

        if messagebox.askyesno("Confirm Deletion",
                              f"Delete {count} agent(s)?\nThis will also delete all associated contexts."):
            try:
                for agent_id in agent_ids:
                    # Delete contexts first
                    self.db_manager.execute_update(
                        "DELETE FROM contexts WHERE agent_id = ?", (agent_id,)
                    )
                    # Delete agent
                    self.db_manager.execute_update(
                        "DELETE FROM agents WHERE agent_id = ?", (agent_id,)
                    )

                self.refresh_agent_list()
                messagebox.showinfo("Success", f"Deleted {count} agent(s)")
            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to delete agents: {e}")

    def change_permission(self):
        """Change permission level for selected agents"""
        selection = self.agent_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select agents to update")
            return

        dialog = PermissionChangeDialog(self.frame)
        permission = dialog.show()

        if permission:
            agent_ids = [self.agent_tree.item(item)['values'][0] for item in selection]
            try:
                for agent_id in agent_ids:
                    self.db_manager.execute_update(
                        "UPDATE agents SET permission_level = ? WHERE agent_id = ?",
                        (permission, agent_id)
                    )

                self.refresh_agent_list()
                messagebox.showinfo("Success", f"Updated permission for {len(agent_ids)} agent(s)")
            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to update permissions: {e}")

    def assign_to_team(self):
        """Assign selected agents to a team"""
        selection = self.agent_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select agents to assign")
            return

        # Get available teams
        teams = self.db_manager.execute_query("SELECT team_id, name FROM teams ORDER BY name")
        if not teams:
            messagebox.showwarning("Warning", "No teams available. Create a team first.")
            return

        dialog = TeamSelectionDialog(self.frame, teams)
        team_id = dialog.show()

        if team_id:
                agent_ids = [self.agent_tree.item(item)['values'][0] for item in selection]
                try:
                    for agent_id in agent_ids:
                        # Get current teams
                        current_teams_result = self.db_manager.execute_query(
                            "SELECT teams FROM agents WHERE agent_id = ?", (agent_id,)
                        )
                        current_teams = []
                        if current_teams_result and current_teams_result[0][0]:
                            try:
                                current_teams = json.loads(current_teams_result[0][0])
                            except json.JSONDecodeError:
                                current_teams = []

                        # Add team if not already assigned
                        if team_id not in current_teams:
                            current_teams.append(team_id)
                            self.db_manager.execute_update(
                                "UPDATE agents SET teams = ? WHERE agent_id = ?",
                                (json.dumps(current_teams), agent_id)
                            )

                    self.refresh_agent_list()
                    messagebox.showinfo("Success", f"Assigned {len(agent_ids)} agent(s) to team {team_id}")
                except Exception as e:
                    messagebox.showerror("Database Error", f"Failed to assign to team: {e}")

    def remove_from_team(self):
        """Remove selected agents from all teams"""
        selection = self.agent_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select agents to remove from teams")
            return

        agent_ids = [self.agent_tree.item(item)['values'][0] for item in selection]
        count = len(agent_ids)

        if messagebox.askyesno("Confirm Team Removal",
                              f"Remove {count} agent(s) from all teams?\nThis will clear all team assignments for the selected agents."):
            try:
                for agent_id in agent_ids:
                    self.db_manager.execute_update(
                        "UPDATE agents SET teams = NULL WHERE agent_id = ?",
                        (agent_id,)
                    )

                self.refresh_agent_list()
                messagebox.showinfo("Success", f"Removed {count} agent(s) from all teams")
            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to remove from teams: {e}")

    def export_csv(self):
        """Export agent list to CSV"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if filename:
            try:
                agents = self.db_manager.execute_query('''
                    SELECT agent_id, name, permission_level, teams, connection_id, is_active, created_at
                    FROM agents
                    ORDER BY agent_id
                ''')

                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Agent ID', 'Name', 'Permission Level', 'Teams', 'Connection ID', 'Active', 'Created'])

                    for agent in agents:
                        teams = json.loads(agent[3]) if agent[3] else []
                        teams_str = ", ".join(teams)
                        writer.writerow([
                            agent[0], agent[1], agent[2], teams_str,
                            agent[4] or '', 'Yes' if agent[5] else 'No', agent[6]
                        ])

                messagebox.showinfo("Success", f"Exported {len(agents)} agents to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {e}")

    def import_from_markdown(self):
        """Import agents from markdown files"""
        filenames = filedialog.askopenfilenames(
            title="Select Markdown Files",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
        )

        if filenames:
            imported_count = 0
            for filename in filenames:
                try:
                    # Extract agent_id from filename (without extension, spaces replaced with underscores)
                    base_name = os.path.splitext(os.path.basename(filename))[0]
                    agent_id = base_name.replace(' ', '_')

                    # Check if agent already exists
                    existing = self.db_manager.execute_query(
                        "SELECT agent_id FROM agents WHERE agent_id = ?", (agent_id,)
                    )

                    if not existing:
                        self.db_manager.execute_update('''
                            INSERT INTO agents (agent_id, name, permission_level, teams, is_active)
                            VALUES (?, ?, 'team', NULL, 1)
                        ''', (agent_id, agent_id))
                        imported_count += 1

                except Exception as e:
                    messagebox.showerror("Import Error", f"Failed to import {filename}: {e}")

            if imported_count > 0:
                self.refresh_agent_list()
                messagebox.showinfo("Success", f"Imported {imported_count} new agents")

    def filter_agents(self, *args):
        """Filter agents based on search text"""
        search_text = self.search_var.get().lower()

        # Clear and repopulate with filtered results
        for item in self.agent_tree.get_children():
            self.agent_tree.delete(item)

        try:
            agents = self.db_manager.execute_query('''
                SELECT agent_id, name, permission_level, teams, connection_id, is_active
                FROM agents
                WHERE is_active = 1 AND (
                    LOWER(agent_id) LIKE ? OR
                    LOWER(permission_level) LIKE ? OR
                    LOWER(teams) LIKE ?
                )
                ORDER BY agent_id
            ''', (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%'))

            for i, agent in enumerate(agents, 1):
                agent_id, name, permission_level, teams_json, connection_id, is_active = agent

                # Parse teams
                teams = []
                if teams_json:
                    try:
                        teams = json.loads(teams_json)
                    except json.JSONDecodeError:
                        teams = []

                teams_str = ", ".join(teams) if teams else "None"
                connection_str = connection_id if connection_id else "Not Connected"

                self.agent_tree.insert(
                    '',
                    'end',
                    text=str(i),
                    values=(agent_id, permission_level, teams_str, connection_str)
                )

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to filter agents: {e}")

    def sort_agent_column(self, column):
        """Sort agents by column"""
        # Get current items from tree
        items = [(self.agent_tree.set(child, column), child) for child in self.agent_tree.get_children('')]

        # Sort items
        items.sort(reverse=getattr(self, f'_reverse_agent_{column}', False))

        # Rearrange items in sorted order
        for index, (val, child) in enumerate(items):
            self.agent_tree.move(child, '', index)

        # Toggle sort direction for next click
        setattr(self, f'_reverse_agent_{column}', not getattr(self, f'_reverse_agent_{column}', False))

    # Teams Tab Methods
    def refresh_teams(self):
        """Refresh the teams TreeView"""
        # Clear existing items
        for item in self.teams_tree.get_children():
            self.teams_tree.delete(item)

        try:
            # Get all teams
            teams = self.db_manager.execute_query('''
                SELECT team_id, name, description
                FROM teams
                ORDER BY name
            ''')

            for team in teams:
                team_id, team_name, description = team

                # Insert team node
                team_node = self.teams_tree.insert(
                    '',
                    'end',
                    text=f"📁 {team_name} ({team_id})",
                    values=(team_id,)
                )

                # Get agents in this team
                agents = self.db_manager.execute_query('''
                    SELECT agent_id, name, permission_level
                    FROM agents
                    WHERE teams LIKE ? AND is_active = 1
                    ORDER BY agent_id
                ''', (f'%"{team_id}"%',))

                for agent in agents:
                    agent_id, agent_name, permission = agent
                    self.teams_tree.insert(
                        team_node,
                        'end',
                        text=f"👤 {agent_id} ({permission})"
                    )

            # Expand all team nodes
            for item in self.teams_tree.get_children():
                self.teams_tree.item(item, open=True)

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load teams: {e}")

    def add_team(self):
        """Add a new team"""
        dialog = TeamCreateDialog(self.frame)
        result = dialog.show()

        if result:
            team_name, description = result
            # Generate team_id from team_name (lowercase, replace spaces with underscores)
            team_id = team_name.lower().replace(' ', '_').replace('-', '_')

            try:
                self.db_manager.execute_update('''
                    INSERT INTO teams (team_id, name, description)
                    VALUES (?, ?, ?)
                ''', (team_id, team_name, description or ''))

                self.refresh_teams()
                messagebox.showinfo("Success", f"Team '{team_name}' created successfully")
            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to create team: {e}")

    def delete_team(self):
        """Delete selected team"""
        selection = self.teams_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a team to delete")
            return

        try:
            self.db_manager.execute_update("DELETE FROM teams WHERE team_id = ?", (team_id,))
            self.refresh_teams()
            messagebox.showinfo("Success", f"Team '{team_id}' deleted successfully")
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to delete team: {e}")

    def rename_team(self):
        """Rename selected team"""
        selection = self.teams_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a team to rename")
            return

        team_id = self.teams_tree.item(selection[0])['text'].split()[1]  # Extract team_id
        new_name = simpledialog.askstring("Rename Team", f"Enter new name for team {team_id}:")

        if new_name:
            try:
                self.db_manager.execute_update("UPDATE teams SET name = ? WHERE team_id = ?", (new_name, team_id))
                self.refresh_teams()
                messagebox.showinfo("Success", f"Team renamed to '{new_name}'")
            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to rename team: {e}")

    def add_agent_to_team(self):
        """Add agent to selected team"""
        # This functionality is already available through the main agent assignment
        messagebox.showinfo("Info", "Use the Agent Management tab to assign agents to teams")

    def filter_teams(self, *args):
        """Filter teams based on search text"""
        # For now, just refresh - filtering could be implemented
        self.refresh_teams()

    def export_teams_csv(self):
        """Export teams to CSV"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if filename:
            try:
                teams = self.db_manager.execute_query("SELECT team_id, name, description FROM teams ORDER BY name")
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Team ID', 'Name', 'Description'])
                    writer.writerows(teams)
                messagebox.showinfo("Success", f"Teams exported to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export teams: {e}")

class ContextsTab:
    """New Contexts screen with full CRUD operations"""

    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db_manager = db_manager
        self.frame = ttk.Frame(parent)

    def create_widgets(self):
        """Create contexts management interface"""
        # Title
        title_label = ttk.Label(
            self.frame,
            text="📄 Contexts Management",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(10, 20))

        # Control buttons
        self.create_context_buttons()

        # Contexts grid
        self.create_contexts_grid()

        return self.frame

    def create_context_buttons(self):
        """Create context management buttons"""
        button_frame = ttk.Frame(self.frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        # Row 1 - Main operations
        row1 = ttk.Frame(button_frame)
        row1.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(row1, text="👁️ View Context", command=self.view_context).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row1, text="✏️ Edit Context", command=self.edit_context).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row1, text="🗑️ Delete Selected", command=self.delete_contexts).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row1, text="🔄 Refresh", command=self.refresh_contexts).pack(side=tk.RIGHT)

        # Row 2 - Export and search
        row2 = ttk.Frame(button_frame)
        row2.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(row2, text="📊 Export CSV", command=self.export_contexts_csv).pack(side=tk.LEFT, padx=(0, 5))

        # Search frame
        search_frame = ttk.Frame(button_frame)
        search_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(search_frame, text="Search/Filter:").pack(side=tk.LEFT)
        self.context_search_var = tk.StringVar()
        self.context_search_var.trace("w", self.filter_contexts)
        search_entry = ttk.Entry(search_frame, textvariable=self.context_search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=(5, 10))

    def create_contexts_grid(self):
        """Create contexts grid"""
        # Grid frame
        grid_frame = ttk.Frame(self.frame)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Contexts tree
        columns = ('timestamp', 'project_session', 'agent_id', 'context_snippet')
        self.contexts_tree = ttk.Treeview(
            grid_frame,
            columns=columns,
            show='tree headings',
            selectmode='extended'
        )

        # Configure columns
        self.contexts_tree.heading('#0', text='ID')
        self.contexts_tree.heading('timestamp', text='Timestamp')
        self.contexts_tree.heading('project_session', text='Project → Session')
        self.contexts_tree.heading('agent_id', text='Agent ID')
        self.contexts_tree.heading('context_snippet', text='Context (first 100 chars)')

        # Set column widths
        self.contexts_tree.column('#0', width=50)
        self.contexts_tree.column('timestamp', width=150)
        self.contexts_tree.column('project_session', width=200)
        self.contexts_tree.column('agent_id', width=120)
        self.contexts_tree.column('context_snippet', width=300)

        # Make columns sortable
        for col in columns:
            self.contexts_tree.heading(col, command=lambda c=col: self.sort_contexts_column(c))

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL, command=self.contexts_tree.yview)
        h_scrollbar = ttk.Scrollbar(grid_frame, orient=tk.HORIZONTAL, command=self.contexts_tree.xview)
        self.contexts_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack grid and scrollbars
        self.contexts_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        # Configure grid weights
        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(0, weight=1)

        # Load initial data
        self.refresh_contexts()

    def refresh_contexts(self):
        """Refresh contexts display"""
        # Clear existing items
        for item in self.contexts_tree.get_children():
            self.contexts_tree.delete(item)

        try:
            contexts = self.db_manager.execute_query('''
                SELECT context_id, timestamp, project, session, agent_id, context
                FROM contexts
                ORDER BY timestamp DESC
            ''')

            for context in contexts:
                context_id, timestamp, project, session, agent_id, full_context = context

                # Create snippet
                context_snippet = full_context[:100] + "..." if len(full_context) > 100 else full_context
                project_session = f"{project or 'Unknown'} → {session or 'Unknown'}"

                self.contexts_tree.insert(
                    '',
                    'end',
                    text=str(context_id),
                    values=(timestamp, project_session, agent_id, context_snippet)
                )

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load contexts: {e}")

    def view_context(self):
        """View full context in popup"""
        selection = self.contexts_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a context to view")
            return

        context_id = self.contexts_tree.item(selection[0])['text']
        try:
            result = self.db_manager.execute_query(
                "SELECT context, agent_id, timestamp FROM contexts WHERE context_id = ?",
                (context_id,)
            )

            if result:
                context, agent_id, timestamp = result[0]
                ViewContextDialog(self.frame, context_id, context, agent_id, timestamp)
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load context: {e}")

    def edit_context(self):
        """Edit context in popup"""
        selection = self.contexts_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a context to edit")
            return

        context_id = self.contexts_tree.item(selection[0])['text']
        try:
            result = self.db_manager.execute_query(
                "SELECT context, agent_id, timestamp FROM contexts WHERE context_id = ?",
                (context_id,)
            )

            if result:
                context, agent_id, timestamp = result[0]
                dialog = EditContextDialog(self.frame, context_id, context, agent_id, timestamp)
                new_context = dialog.show()

                if new_context:
                    self.db_manager.execute_update(
                        "UPDATE contexts SET context = ? WHERE context_id = ?",
                        (new_context, context_id)
                    )
                    self.refresh_contexts()
                    messagebox.showinfo("Success", "Context updated successfully")
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to edit context: {e}")

    def delete_contexts(self):
        """Delete selected contexts with confirmation"""
        selection = self.contexts_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select contexts to delete")
            return

        context_ids = [self.contexts_tree.item(item)['text'] for item in selection]
        count = len(context_ids)

        if messagebox.askyesno("Confirm Deletion", f"Delete {count} context(s)?"):
            try:
                for context_id in context_ids:
                    self.db_manager.execute_update(
                        "DELETE FROM contexts WHERE context_id = ?", (context_id,)
                    )

                self.refresh_contexts()
                messagebox.showinfo("Success", f"Deleted {count} context(s)")
            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to delete contexts: {e}")

    def export_contexts_csv(self):
        """Export contexts to CSV"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if filename:
            try:
                contexts = self.db_manager.execute_query('''
                    SELECT context_id, timestamp, project, session, agent_id, context
                    FROM contexts
                    ORDER BY timestamp DESC
                ''')

                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Context ID', 'Timestamp', 'Project', 'Session', 'Agent ID', 'Context'])

                    for context in contexts:
                        writer.writerow(context)

                messagebox.showinfo("Success", f"Exported {len(contexts)} contexts to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {e}")

    def filter_contexts(self, *args):
        """Filter contexts based on search text"""
        search_text = self.context_search_var.get().lower()

        # Clear and repopulate with filtered results
        for item in self.contexts_tree.get_children():
            self.contexts_tree.delete(item)

        try:
            contexts = self.db_manager.execute_query('''
                SELECT context_id, timestamp, project, session, agent_id, context
                FROM contexts
                WHERE LOWER(agent_id) LIKE ? OR LOWER(context) LIKE ?
                ORDER BY timestamp DESC
            ''', (f'%{search_text}%', f'%{search_text}%'))

            for context in contexts:
                context_id, timestamp, project, session, agent_id, full_context = context

                # Create snippet
                context_snippet = full_context[:100] + "..." if len(full_context) > 100 else full_context
                project_session = f"{project or 'Unknown'} → {session or 'Unknown'}"

                self.contexts_tree.insert(
                    '',
                    'end',
                    text=str(context_id),
                    values=(timestamp, project_session, agent_id, context_snippet)
                )

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to filter contexts: {e}")

    def sort_contexts_column(self, column):
        """Sort contexts by column"""
        # Get current items from tree
        items = [(self.contexts_tree.set(child, column), child) for child in self.contexts_tree.get_children('')]

        # Sort items (special handling for numeric context_id and dates)
        if column == 'context_id':
            items.sort(key=lambda x: int(x[0]) if x[0].isdigit() else 0, reverse=getattr(self, f'_reverse_context_{column}', False))
        elif column == 'timestamp':
            items.sort(key=lambda x: x[0], reverse=getattr(self, f'_reverse_context_{column}', False))
        else:
            items.sort(reverse=getattr(self, f'_reverse_context_{column}', False))

        # Rearrange items in sorted order
        for index, (val, child) in enumerate(items):
            self.contexts_tree.move(child, '', index)

        # Toggle sort direction for next click
        setattr(self, f'_reverse_context_{column}', not getattr(self, f'_reverse_context_{column}', False))

class StatusBar:
    """Status bar with live server and database information"""

    def __init__(self, parent):
        self.parent = parent
        self.frame = ttk.Frame(parent, relief=tk.SUNKEN, borderwidth=1)

        # Status variables
        self.active_connections = tk.StringVar(value="Connections: 0")
        self.registered_agents = tk.StringVar(value="Agents: 0")
        self.database_status = tk.StringVar(value="DB: Unknown")
        self.server_status = tk.StringVar(value="Server: Unknown")
        self.server_address = tk.StringVar(value="Address: Unknown")

        self.create_widgets()

    def create_widgets(self):
        """Create status bar widgets"""
        # Connection count
        ttk.Label(self.frame, textvariable=self.active_connections).pack(side=tk.LEFT, padx=(5, 10))

        # Separator
        ttk.Separator(self.frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Agent count
        ttk.Label(self.frame, textvariable=self.registered_agents).pack(side=tk.LEFT, padx=(0, 10))

        # Separator
        ttk.Separator(self.frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Database status
        ttk.Label(self.frame, textvariable=self.database_status).pack(side=tk.LEFT, padx=(0, 10))

        # Separator
        ttk.Separator(self.frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Server status
        ttk.Label(self.frame, textvariable=self.server_status).pack(side=tk.LEFT, padx=(0, 10))

        # Separator
        ttk.Separator(self.frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Server address
        ttk.Label(self.frame, textvariable=self.server_address).pack(side=tk.RIGHT, padx=(10, 5))

    def update_status(self, status_data):
        """Update status bar with new data"""
        self.active_connections.set(f"Connections: {status_data.get('active_connections', 0)}")
        self.registered_agents.set(f"Agents: {status_data.get('registered_agents', 0)}")

        db_status = status_data.get('database_status', 'unknown')
        db_icon = "🟢" if db_status == "connected" else "🔴"
        self.database_status.set(f"DB: {db_icon} {db_status}")

        server_status = status_data.get('server_status', 'unknown')
        server_icon = "🟢" if server_status == "running" else "🔴"
        self.server_status.set(f"Server: {server_icon} {server_status}")

        self.server_address.set(f"Address: {status_data.get('server_address', 'Unknown')}")

    def pack(self, **kwargs):
        """Pack the status bar frame"""
        return self.frame.pack(**kwargs)

# Dialog classes
class AgentCreateDialog:
    """Dialog for creating new agents with permission and teams"""

    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db_manager = db_manager
        self.result = None

    def show(self):
        """Show the dialog and return result"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Create New Agent")
        self.dialog.geometry("450x350")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Center dialog
        self.dialog.geometry("+%d+%d" % (
            self.parent.winfo_rootx() + 50,
            self.parent.winfo_rooty() + 50
        ))

        self.create_dialog_widgets()

        # Wait for dialog to close
        self.parent.wait_window(self.dialog)
        return self.result

    def create_dialog_widgets(self):
        """Create dialog widgets"""
        # Agent ID
        ttk.Label(self.dialog, text="Agent ID:").pack(pady=5)
        self.agent_id_var = tk.StringVar()
        ttk.Entry(self.dialog, textvariable=self.agent_id_var, width=25).pack(pady=5)

        # Permission Level
        ttk.Label(self.dialog, text="Permission Level:").pack(pady=5)
        self.permission_var = tk.StringVar(value="team")
        permission_combo = ttk.Combobox(
            self.dialog,
            textvariable=self.permission_var,
            values=["all", "team", "self"],
            state="readonly",
            width=22
        )
        permission_combo.pack(pady=5)

        # Teams
        ttk.Label(self.dialog, text="Team Assignment:").pack(pady=5)
        self.teams_var = tk.StringVar()

        # Get available teams
        try:
            teams = self.db_manager.execute_query("SELECT team_id, name FROM teams ORDER BY name")
            team_choices = ["None"] + [f"{team[1]} ({team[0]})" for team in teams]
        except:
            team_choices = ["None"]

        teams_combo = ttk.Combobox(
            self.dialog,
            textvariable=self.teams_var,
            values=team_choices,
            state="readonly",
            width=22
        )
        teams_combo.pack(pady=5)
        teams_combo.set("None")  # Default to no team

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Create", command=self.on_create).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.LEFT, padx=5)

    def on_create(self):
        """Handle create button"""
        agent_id = self.agent_id_var.get().strip()
        if not agent_id:
            messagebox.showerror("Error", "Agent ID is required")
            return

        permission_level = self.permission_var.get()
        team_selection = self.teams_var.get().strip()

        # Parse team selection
        teams = []
        if team_selection and team_selection != "None":
            # Extract team_id from selection (format: "Team Name (team_id)")
            team_id = team_selection.split('(')[-1].rstrip(')')
            teams = [team_id]

        self.result = (agent_id, permission_level, teams)
        self.dialog.destroy()

    def on_cancel(self):
        """Handle cancel button"""
        self.dialog.destroy()


class PermissionChangeDialog:
    """Dialog for changing agent permissions with dropdown"""

    def __init__(self, parent):
        self.parent = parent
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Change Permission Level")
        self.dialog.geometry("380x180")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Center dialog
        self.dialog.geometry("+%d+%d" % (
            self.parent.winfo_rootx() + 150,
            self.parent.winfo_rooty() + 150
        ))

        # Permission Level
        ttk.Label(self.dialog, text="Select Permission Level:", font=('Arial', 14)).pack(pady=10)
        self.permission_var = tk.StringVar(value="team")
        permission_combo = ttk.Combobox(
            self.dialog,
            textvariable=self.permission_var,
            values=["all", "team", "self"],
            state="readonly",
            width=18,
            font=('Arial', 14)
        )
        permission_combo.pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="OK", command=self.on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.LEFT, padx=5)

    def show(self):
        """Show dialog and return result"""
        self.dialog.wait_window()
        return self.result

    def on_ok(self):
        """Handle OK button"""
        self.result = self.permission_var.get()
        self.dialog.destroy()

    def on_cancel(self):
        """Handle cancel button"""
        self.dialog.destroy()


class TeamCreateDialog:
    """Dialog for creating teams with name and description"""

    def __init__(self, parent):
        self.parent = parent
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create New Team")
        self.dialog.geometry("450x240")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Center dialog
        self.dialog.geometry("+%d+%d" % (
            self.parent.winfo_rootx() + 100,
            self.parent.winfo_rooty() + 100
        ))

        # Team Name
        ttk.Label(self.dialog, text="Team Name:", font=('Arial', 14)).pack(pady=5)
        self.team_name_var = tk.StringVar()
        ttk.Entry(self.dialog, textvariable=self.team_name_var, width=35, font=('Arial', 14)).pack(pady=5)

        # Team Description
        ttk.Label(self.dialog, text="Description (optional):", font=('Arial', 14)).pack(pady=5)
        self.description_var = tk.StringVar()
        ttk.Entry(self.dialog, textvariable=self.description_var, width=35, font=('Arial', 14)).pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=15)

        ttk.Button(button_frame, text="Create", command=self.on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.LEFT, padx=5)

    def show(self):
        """Show dialog and return result"""
        self.dialog.wait_window()
        return self.result

    def on_ok(self):
        """Handle OK button"""
        team_name = self.team_name_var.get().strip()
        if not team_name:
            messagebox.showwarning("Validation Error", "Team name is required")
            return

        description = self.description_var.get().strip()
        self.result = (team_name, description)
        self.dialog.destroy()

    def on_cancel(self):
        """Handle cancel button"""
        self.dialog.destroy()


class TeamSelectionDialog:
    """Dialog for selecting a team from available teams"""

    def __init__(self, parent, teams):
        self.parent = parent
        self.teams = teams
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Team")
        self.dialog.geometry("420x180")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Center dialog
        self.dialog.geometry("+%d+%d" % (
            self.parent.winfo_rootx() + 150,
            self.parent.winfo_rooty() + 150
        ))

        # Team Selection
        ttk.Label(self.dialog, text="Select Team:", font=('Arial', 14)).pack(pady=10)
        self.team_var = tk.StringVar()

        # Create dropdown with team names
        team_choices = [f"{team[1]} ({team[0]})" for team in teams]
        team_combo = ttk.Combobox(
            self.dialog,
            textvariable=self.team_var,
            values=team_choices,
            state="readonly",
            width=25,
            font=('Arial', 14)
        )
        team_combo.pack(pady=5)

        if team_choices:
            team_combo.set(team_choices[0])  # Set default selection

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=15)

        ttk.Button(button_frame, text="OK", command=self.on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.LEFT, padx=5)

    def show(self):
        """Show dialog and return result"""
        self.dialog.wait_window()
        return self.result

    def on_ok(self):
        """Handle OK button"""
        selection = self.team_var.get()
        if selection:
            # Extract team_id from selection (format: "Team Name (team_id)")
            team_id = selection.split('(')[-1].rstrip(')')
            self.result = team_id
        self.dialog.destroy()

    def on_cancel(self):
        """Handle cancel button"""
        self.dialog.destroy()


class ViewContextDialog:
    """Dialog for viewing full context"""

    def __init__(self, parent, context_id, context, agent_id, timestamp):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"View Context {context_id}")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)

        # Info frame
        info_frame = ttk.Frame(self.dialog)
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text=f"Context ID: {context_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Agent ID: {agent_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Timestamp: {timestamp}").pack(anchor=tk.W)

        # Context display
        text_frame = ttk.Frame(self.dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.text_widget = tk.Text(text_frame, wrap=tk.WORD, state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)

        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Insert context
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.insert('1.0', context)
        self.text_widget.config(state=tk.DISABLED)

        # Close button
        ttk.Button(self.dialog, text="Close", command=self.dialog.destroy).pack(pady=10)

class EditContextDialog:
    """Dialog for editing context"""

    def __init__(self, parent, context_id, context, agent_id, timestamp):
        self.parent = parent
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Edit Context {context_id}")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Info frame
        info_frame = ttk.Frame(self.dialog)
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text=f"Context ID: {context_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Agent ID: {agent_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Timestamp: {timestamp}").pack(anchor=tk.W)

        # Context editor
        text_frame = ttk.Frame(self.dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.text_widget = tk.Text(text_frame, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)

        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Insert context
        self.text_widget.insert('1.0', context)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Save", command=self.on_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.LEFT, padx=5)

    def show(self):
        """Show dialog and return result"""
        self.parent.wait_window(self.dialog)
        return self.result

    def on_save(self):
        """Handle save button"""
        self.result = self.text_widget.get('1.0', tk.END).strip()
        self.dialog.destroy()

    def on_cancel(self):
        """Handle cancel button"""
        self.dialog.destroy()

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
   - team: Returns contexts from agents in the same team
   - all: Returns all contexts in the current session

Permission Levels:
- self: Maximum security, agent isolation
- team: Team collaboration
- all: Full session access

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
                    print(f"- {ctx['timestamp']}: {ctx['context']}")
        else:
            print("Write failed:", write_result.get("prompt", "Unknown error"))

# asyncio.run(mcp_client_example())

SUMMARY OF CHANGES:
- ReadDB success responses now only contain "contexts" array
- WriteDB success responses contain "status", "agent", and "prompt"
- Error responses are standardized with "status" and "prompt"
- All responses are simplified - no extra metadata unless error
- Instructions in prompts guide next actions for the client
"""

        text_widget.insert('1.0', examples)
        text_widget.config(state='disabled')

class ProjectSessionTab:
    """Project and session management tab reimplemented from comprehensive_enhanced_gui.py"""

    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db_manager = db_manager
        self.validator = ValidationManager(db_manager)
        self.frame = ttk.Frame(parent)

    def create_widgets(self):
        """Create project/session management widgets with full functionality"""
        # Title
        title_label = ttk.Label(
            self.frame,
            text="📁 Project & Session Management",
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Main container with two panels
        main_container = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel - Tree structure
        left_frame = ttk.LabelFrame(main_container, text="Project Structure", padding=10)
        main_container.add(left_frame, weight=1)

        # Tree view
        self.project_tree = ttk.Treeview(left_frame, height=15)
        self.project_tree.heading('#0', text='Project Structure')
        self.project_tree.column('#0', width=350)
        self.project_tree.pack(fill=tk.BOTH, expand=True)
        self.project_tree.bind('<<TreeviewSelect>>', self.on_tree_select)

        # Drag and drop bindings
        self.project_tree.bind('<Button-1>', self.on_drag_start)
        self.project_tree.bind('<B1-Motion>', self.on_drag_motion)
        self.project_tree.bind('<ButtonRelease-1>', self.on_drag_release)

        # Drag state variables
        self.drag_data = {"item": None, "x": 0, "y": 0}

        # Search/Filter box for projects
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.project_search_var = tk.StringVar()
        self.project_search_var.trace("w", self.filter_projects)
        search_entry = ttk.Entry(search_frame, textvariable=self.project_search_var, width=25)
        search_entry.pack(side=tk.LEFT, padx=(5, 10))

        # Sort options
        ttk.Label(search_frame, text="Sort:").pack(side=tk.LEFT, padx=(10, 5))
        self.sort_var = tk.StringVar(value="name")
        sort_combo = ttk.Combobox(
            search_frame,
            textvariable=self.sort_var,
            values=["name", "created_date", "agent_count"],
            state="readonly",
            width=12
        )
        sort_combo.pack(side=tk.LEFT)
        sort_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_tree())

        # Control buttons
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="➕ New Project", command=self.new_project).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="➕ New Session", command=self.new_session).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="✏️ Rename", command=self.rename_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🔄 Refresh", command=self.refresh_tree).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🗑️ Delete", command=self.delete_selected).pack(side=tk.RIGHT, padx=2)

        # Right panel - Details and assignment
        right_frame = ttk.LabelFrame(main_container, text="Details & Management", padding=10)
        main_container.add(right_frame, weight=1)

        # Details section with editing capability
        details_frame = ttk.LabelFrame(right_frame, text="Selection Details", padding=5)
        details_frame.pack(fill=tk.X, pady=(0, 10))

        # Create a notebook for details and editing
        details_notebook = ttk.Notebook(details_frame)
        details_notebook.pack(fill=tk.BOTH, expand=True)

        # Details view tab
        details_tab = ttk.Frame(details_notebook)
        details_notebook.add(details_tab, text="📄 Details")

        self.details_text = tk.Text(details_tab, height=6, wrap=tk.WORD, state=tk.DISABLED)
        details_scroll = ttk.Scrollbar(details_tab, orient=tk.VERTICAL, command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=details_scroll.set)
        self.details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        details_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Edit tab for descriptions
        edit_tab = ttk.Frame(details_notebook)
        details_notebook.add(edit_tab, text="✏️ Edit")

        # Edit form
        edit_form = ttk.Frame(edit_tab)
        edit_form.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Name field
        ttk.Label(edit_form, text="Name:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.edit_name_var = tk.StringVar()
        self.edit_name_entry = ttk.Entry(edit_form, textvariable=self.edit_name_var, width=30)
        self.edit_name_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))

        # Description field
        ttk.Label(edit_form, text="Description:").grid(row=1, column=0, sticky="nw", padx=(0, 5), pady=(5, 0))
        self.edit_desc_text = tk.Text(edit_form, height=4, width=30, wrap=tk.WORD)
        self.edit_desc_text.grid(row=1, column=1, sticky="ew", padx=(0, 5), pady=(5, 0))

        # Buttons
        button_frame = ttk.Frame(edit_form)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))

        ttk.Button(button_frame, text="💾 Save Changes", command=self.save_details).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🔄 Load Current", command=self.load_current_details).pack(side=tk.LEFT)

        # Configure grid weights
        edit_form.grid_columnconfigure(1, weight=1)

        # Store current selection for editing
        self.current_selection = None

        # Assignment section
        assign_frame = ttk.LabelFrame(right_frame, text="Agent Assignment", padding=5)
        assign_frame.pack(fill=tk.BOTH, expand=True)

        # Assignment controls
        assign_controls = ttk.Frame(assign_frame)
        assign_controls.pack(fill=tk.X, pady=(0, 10))

        # Session selection
        ttk.Label(assign_controls, text="Assign to session:").pack(side=tk.LEFT)
        self.assign_session_var = tk.StringVar()
        self.assign_session_combo = ttk.Combobox(
            assign_controls,
            textvariable=self.assign_session_var,
            width=25,
            state="readonly"
        )
        self.assign_session_combo.pack(side=tk.LEFT, padx=(5, 10))

        # Assignment buttons
        ttk.Button(assign_controls, text="Assign Selected", command=self.assign_agents).pack(side=tk.LEFT, padx=2)
        ttk.Button(assign_controls, text="Unassign", command=self.unassign_agents).pack(side=tk.LEFT, padx=2)

        # Validation display
        self.validation_frame = ttk.Frame(assign_frame)
        self.validation_frame.pack(fill=tk.X, pady=(0, 5))

        self.validation_label = ttk.Label(
            self.validation_frame,
            text="📋 Assignment validation will appear here",
            foreground="blue"
        )
        self.validation_label.pack(side=tk.LEFT)

        # Agent filter
        filter_frame = ttk.Frame(assign_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(filter_frame, text="Filter agents:").pack(side=tk.LEFT)
        self.agent_filter_var = tk.StringVar()
        self.agent_filter_var.trace("w", self.filter_assignment_agents)
        agent_filter_entry = ttk.Entry(filter_frame, textvariable=self.agent_filter_var, width=20)
        agent_filter_entry.pack(side=tk.LEFT, padx=(5, 10))

        # Show only unassigned checkbox
        self.show_unassigned_var = tk.BooleanVar()
        self.show_unassigned_check = ttk.Checkbutton(
            filter_frame,
            text="Show only unassigned",
            variable=self.show_unassigned_var,
            command=self.refresh_agents
        )
        self.show_unassigned_check.pack(side=tk.LEFT, padx=(10, 0))

        # Available agents tree
        agents_frame = ttk.Frame(assign_frame)
        agents_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(agents_frame, text="Available Agents:").pack(anchor=tk.W)

        self.agents_tree = ttk.Treeview(
            agents_frame,
            columns=('name', 'current_session', 'team_id'),
            show='tree headings',
            selectmode='extended'
        )
        self.agents_tree.heading('#0', text='Agent ID')
        self.agents_tree.heading('name', text='Name')
        self.agents_tree.heading('current_session', text='Current Session')
        self.agents_tree.heading('team_id', text='Team')

        self.agents_tree.column('#0', width=120)
        self.agents_tree.column('name', width=120)
        self.agents_tree.column('current_session', width=120)
        self.agents_tree.column('team_id', width=80)

        self.agents_tree.pack(fill=tk.BOTH, expand=True)

        # Bind events for validation updates
        self.agents_tree.bind('<<TreeviewSelect>>', lambda e: self.update_assignment_validation())
        self.assign_session_combo.bind('<<ComboboxSelected>>', lambda e: self.update_assignment_validation())

        # Load initial data
        self.refresh_tree()
        self.refresh_agents()
        self.refresh_session_combo()

        return self.frame

    def filter_projects(self, *args):
        """Filter projects based on search text"""
        search_text = self.project_search_var.get().lower()

        # Clear existing items
        self.project_tree.delete(*self.project_tree.get_children())

        if not search_text:
            # If no search text, show all
            self.refresh_tree()
            return

        try:
            # Get filtered data
            projects = self.get_projects()
            sessions = self.get_sessions()
            agents = self.get_agents()

            # Filter projects by name or description
            filtered_projects = {}
            for project_id, project in projects.items():
                if (search_text in project['name'].lower() or
                    (project['description'] and search_text in project['description'].lower())):
                    filtered_projects[project_id] = project

            # Also include projects that have sessions matching the search
            for session_id, session in sessions.items():
                if search_text in session['name'].lower():
                    project_id = session['project_id']
                    if project_id in projects:
                        filtered_projects[project_id] = projects[project_id]

            # Build tree with filtered data
            self._build_tree_from_data(filtered_projects, sessions, agents)

        except Exception as e:
            messagebox.showerror("Search Error", f"Failed to filter projects: {e}")

    def _build_tree_from_data(self, projects, sessions, agents):
        """Helper method to build tree from given data"""
        # Group sessions by project
        project_sessions = {}
        for session_id, session in sessions.items():
            project_id = session['project_id']
            if project_id in projects:  # Only include sessions for filtered projects
                if project_id not in project_sessions:
                    project_sessions[project_id] = []
                project_sessions[project_id].append(session)

        # Group agents by session
        session_agents = {}
        for agent_id, agent in agents.items():
            session_id = agent.get('session_id')
            if session_id:
                if session_id not in session_agents:
                    session_agents[session_id] = []
                session_agents[session_id].append(agent)

        # Sort projects based on sort criteria
        sort_by = self.sort_var.get()
        if sort_by == "name":
            sorted_projects = sorted(projects.items(), key=lambda x: x[1]['name'])
        elif sort_by == "created_date":
            sorted_projects = sorted(projects.items(), key=lambda x: x[1]['created_at'] or '', reverse=True)
        elif sort_by == "agent_count":
            # Count agents per project
            project_agent_counts = {}
            for project_id in projects:
                count = 0
                for session in project_sessions.get(project_id, []):
                    count += len(session_agents.get(session['id'], []))
                project_agent_counts[project_id] = count
            sorted_projects = sorted(projects.items(), key=lambda x: project_agent_counts.get(x[0], 0), reverse=True)
        else:
            sorted_projects = list(projects.items())

        # Add projects with their sessions and agents
        for project_id, project in sorted_projects:
            project_node = self.project_tree.insert('', tk.END, text=f"📁 {project['name']}",
                                                   values=('project', project_id))

            # Add sessions for this project
            project_session_list = project_sessions.get(project_id, [])
            # Sort sessions by name
            project_session_list.sort(key=lambda x: x['name'])

            for session in project_session_list:
                session_agent_list = session_agents.get(session['id'], [])
                agent_count = len(session_agent_list)

                session_text = f"🔧 {session['name']} ({agent_count} agents)"
                session_node = self.project_tree.insert(project_node, tk.END, text=session_text,
                                                       values=('session', session['id']))

                # Add agents for this session
                for agent in session_agent_list:
                    status_icon = "🟢" if agent.get('status') == 'connected' else "🔴"
                    agent_text = f"{status_icon} {agent.get('name', agent.get('agent_id', 'Unknown'))}"
                    self.project_tree.insert(session_node, tk.END, text=agent_text,
                                           values=('agent', agent.get('agent_id')))

        # Expand all project nodes to show sessions
        for item in self.project_tree.get_children():
            self.project_tree.item(item, open=True)

    def rename_selected(self):
        """Rename selected project or session with enhanced validation"""
        selection = self.project_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a project or session to rename")
            return

        item = self.project_tree.item(selection[0])
        values = item.get('values', [])

        if len(values) >= 2:
            item_type, item_id = values[0], values[1]
        else:
            messagebox.showwarning("Warning", "Cannot rename this item")
            return

        item_text = item['text'].replace("📁 ", "").replace("🔧 ", "").split(" (")[0]  # Remove icons and agent count

        if item_type == 'project':
            new_name = simpledialog.askstring(
                "Rename Project",
                f"Enter new name for project:",
                initialvalue=item_text
            )
            if new_name and new_name != item_text:
                try:
                    # Enhanced validation
                    is_valid, error_msg = self.validator.validate_project_name(new_name, exclude_id=item_id)
                    if not is_valid:
                        messagebox.showerror("Validation Error", error_msg)
                        return

                    self.db_manager.execute_update(
                        "UPDATE projects SET name = ? WHERE id = ?",
                        (new_name.strip(), item_id)
                    )
                    self.refresh_tree()
                    messagebox.showinfo("Success", f"Project renamed to '{new_name.strip()}'")
                except Exception as e:
                    messagebox.showerror("Database Error", f"Failed to rename project: {e}")

        elif item_type == 'session':
            new_name = simpledialog.askstring(
                "Rename Session",
                f"Enter new name for session:",
                initialvalue=item_text
            )
            if new_name and new_name != item_text:
                try:
                    # Enhanced validation
                    is_valid, error_msg = self.validator.validate_session_name(new_name, exclude_id=item_id)
                    if not is_valid:
                        messagebox.showerror("Validation Error", error_msg)
                        return

                    self.db_manager.execute_update(
                        "UPDATE sessions SET name = ? WHERE id = ?",
                        (new_name.strip(), item_id)
                    )
                    self.refresh_tree()
                    messagebox.showinfo("Success", f"Session renamed to '{new_name.strip()}'")
                except Exception as e:
                    messagebox.showerror("Database Error", f"Failed to rename session: {e}")

        else:
            messagebox.showinfo("Info", "Only projects and sessions can be renamed")

    def save_details(self):
        """Save changes to project/session details with enhanced validation"""
        if not self.current_selection:
            messagebox.showwarning("Warning", "No item selected for editing")
            return

        item_type, item_id = self.current_selection
        new_name = self.edit_name_var.get().strip()
        new_description = self.edit_desc_text.get('1.0', tk.END).strip()

        try:
            if item_type == 'project':
                # Enhanced validation
                is_valid, error_msg = self.validator.validate_project_name(new_name, exclude_id=item_id)
                if not is_valid:
                    messagebox.showerror("Validation Error", error_msg)
                    return

                self.db_manager.execute_update(
                    "UPDATE projects SET name = ?, description = ? WHERE id = ?",
                    (new_name, new_description, item_id)
                )

            elif item_type == 'session':
                # Enhanced validation
                is_valid, error_msg = self.validator.validate_session_name(new_name, exclude_id=item_id)
                if not is_valid:
                    messagebox.showerror("Validation Error", error_msg)
                    return

                # Note: Sessions don't have description field in current schema
                self.db_manager.execute_update(
                    "UPDATE sessions SET name = ? WHERE id = ?",
                    (new_name, item_id)
                )

            self.refresh_tree()
            self.on_tree_select(None)  # Refresh details view
            messagebox.showinfo("Success", f"{item_type.title()} updated successfully")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to save changes: {e}")

    def load_current_details(self):
        """Load current details into edit form"""
        if not self.current_selection:
            messagebox.showwarning("Warning", "No item selected")
            return

        item_type, item_id = self.current_selection

        try:
            if item_type == 'project':
                result = self.db_manager.execute_query(
                    "SELECT name, description FROM projects WHERE id = ?", (item_id,)
                )
                if result:
                    name, description = result[0]
                    self.edit_name_var.set(name or '')
                    self.edit_desc_text.delete('1.0', tk.END)
                    self.edit_desc_text.insert('1.0', description or '')

            elif item_type == 'session':
                result = self.db_manager.execute_query(
                    "SELECT name FROM sessions WHERE id = ?", (item_id,)
                )
                if result:
                    name = result[0][0]
                    self.edit_name_var.set(name or '')
                    self.edit_desc_text.delete('1.0', tk.END)
                    self.edit_desc_text.insert('1.0', '')  # Sessions don't have descriptions

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load details: {e}")

    def filter_assignment_agents(self, *args):
        """Filter agents in assignment view"""
        self.refresh_agents()  # Just refresh with current filter

    def refresh_tree(self):
        """Load and display project data with sessions and agents in tree structure"""
        try:
            # Get all data
            projects = self.get_projects()
            sessions = self.get_sessions()
            agents = self.get_agents()

            # Clear existing items
            self.project_tree.delete(*self.project_tree.get_children())

            # Use helper method to build tree
            self._build_tree_from_data(projects, sessions, agents)

            # Also refresh the agents list and session combo
            self.refresh_agents()
            self.refresh_session_combo()

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load project tree: {e}")

    def get_projects(self):
        """Get all projects from database"""
        try:
            rows = self.db_manager.execute_query('SELECT id, name, description, created_at FROM projects ORDER BY name')
            projects = {}
            for row in rows:
                projects[row[0]] = {
                    'id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'created_at': row[3]
                }
            return projects
        except Exception:
            return {}

    def get_sessions(self):
        """Get all sessions from database"""
        try:
            rows = self.db_manager.execute_query('SELECT id, project_id, name, created_at FROM sessions ORDER BY name')
            sessions = {}
            for row in rows:
                sessions[row[0]] = {
                    'id': row[0],
                    'project_id': row[1],
                    'name': row[2],
                    'created_at': row[3]
                }
            return sessions
        except Exception:
            return {}

    def get_agents(self):
        """Get all agents from database"""
        try:
            # First check if agents have session_id field
            try:
                rows = self.db_manager.execute_query('''
                    SELECT agent_id, name, session_id, teams, is_active
                    FROM agents
                    WHERE is_active = 1
                    ORDER BY agent_id
                ''')
                agents = {}
                for row in rows:
                    agents[row[0]] = {
                        'agent_id': row[0],
                        'name': row[1],
                        'session_id': row[2],
                        'teams': row[3],
                        'status': 'connected' if row[4] else 'disconnected'
                    }
                return agents
            except sqlite3.OperationalError:
                # Fallback if session_id column doesn't exist yet
                rows = self.db_manager.execute_query('''
                    SELECT agent_id, name, teams, is_active
                    FROM agents
                    WHERE is_active = 1
                    ORDER BY agent_id
                ''')
                agents = {}
                for row in rows:
                    agents[row[0]] = {
                        'agent_id': row[0],
                        'name': row[1],
                        'session_id': None,
                        'teams': row[2],
                        'status': 'connected' if row[3] else 'disconnected'
                    }
                return agents
        except Exception:
            return {}

    def on_tree_select(self, event):
        """Handle tree selection and update details"""
        selection = self.project_tree.selection()
        if not selection:
            self.details_text.config(state=tk.NORMAL)
            self.details_text.delete(1.0, tk.END)
            self.details_text.config(state=tk.DISABLED)
            self.current_selection = None
            # Clear edit form
            self.edit_name_var.set('')
            self.edit_desc_text.delete('1.0', tk.END)
            return

        item = self.project_tree.item(selection[0])
        item_text = item['text']
        values = item.get('values', [])

        if len(values) >= 2:
            item_type, item_id = values[0], values[1]
        else:
            item_type, item_id = 'unknown', 'unknown'

        # Store current selection for editing
        self.current_selection = (item_type, item_id) if item_type in ['project', 'session'] else None

        # Update details text
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete(1.0, tk.END)

        if item_type == 'project':
            try:
                project_details = self.db_manager.execute_query(
                    'SELECT name, description, created_at FROM projects WHERE id = ?', (item_id,)
                )
                if project_details:
                    name, description, created_at = project_details[0]

                    # Count sessions and agents
                    session_count = self.db_manager.execute_query(
                        'SELECT COUNT(*) FROM sessions WHERE project_id = ?', (item_id,)
                    )[0][0]

                    agent_count = self.db_manager.execute_query(
                        '''SELECT COUNT(DISTINCT a.agent_id) FROM agents a
                           JOIN sessions s ON a.session_id = s.id
                           WHERE s.project_id = ? AND a.is_active = 1''', (item_id,)
                    )[0][0] if hasattr(self.db_manager.execute_query('PRAGMA table_info(agents)'), '__iter__') else 0

                    self.details_text.insert(1.0, f"📁 Project: {name}\n")
                    self.details_text.insert(tk.END, f"ID: {item_id}\n")
                    self.details_text.insert(tk.END, f"Description: {description or 'No description'}\n")
                    self.details_text.insert(tk.END, f"Sessions: {session_count}\n")
                    self.details_text.insert(tk.END, f"Agents: {agent_count}\n")
                    self.details_text.insert(tk.END, f"Created: {created_at or 'Unknown'}\n")

                    # Load into edit form
                    self.edit_name_var.set(name or '')
                    self.edit_desc_text.delete('1.0', tk.END)
                    self.edit_desc_text.insert('1.0', description or '')

            except Exception as e:
                self.details_text.insert(1.0, f"Error loading project details: {e}")

        elif item_type == 'session':
            try:
                session_details = self.db_manager.execute_query(
                    '''SELECT s.name, s.created_at, p.name as project_name
                       FROM sessions s
                       LEFT JOIN projects p ON s.project_id = p.id
                       WHERE s.id = ?''', (item_id,)
                )
                if session_details:
                    name, created_at, project_name = session_details[0]

                    # Count agents in this session
                    try:
                        agent_count = self.db_manager.execute_query(
                            'SELECT COUNT(*) FROM agents WHERE session_id = ? AND is_active = 1', (item_id,)
                        )[0][0]
                    except:
                        agent_count = 0  # session_id column might not exist

                    self.details_text.insert(1.0, f"🔧 Session: {name}\n")
                    self.details_text.insert(tk.END, f"ID: {item_id}\n")
                    self.details_text.insert(tk.END, f"Project: {project_name or 'Unknown'}\n")
                    self.details_text.insert(tk.END, f"Agents: {agent_count}\n")
                    self.details_text.insert(tk.END, f"Created: {created_at or 'Unknown'}\n")

                    # Load into edit form
                    self.edit_name_var.set(name or '')
                    self.edit_desc_text.delete('1.0', tk.END)
                    self.edit_desc_text.insert('1.0', '')  # Sessions don't have descriptions

            except Exception as e:
                self.details_text.insert(1.0, f"Error loading session details: {e}")

        elif item_type == 'agent':
            try:
                agent_details = self.db_manager.execute_query(
                    '''SELECT name, teams, permission_level, is_active
                       FROM agents
                       WHERE agent_id = ?''', (item_id,)
                )
                if agent_details:
                    name, teams, permission_level, is_active = agent_details[0]
                    self.details_text.insert(1.0, f"👤 Agent: {name or item_id}\n")
                    self.details_text.insert(tk.END, f"ID: {item_id}\n")
                    self.details_text.insert(tk.END, f"Teams: {teams or 'None'}\n")
                    self.details_text.insert(tk.END, f"Permission: {permission_level or 'team'}\n")
                    self.details_text.insert(tk.END, f"Status: {'🟢 Active' if is_active else '🔴 Inactive'}\n")

                # Clear edit form for agents (not editable here)
                self.edit_name_var.set('')
                self.edit_desc_text.delete('1.0', tk.END)
                self.current_selection = None

            except Exception as e:
                self.details_text.insert(1.0, f"Error loading agent details: {e}")

        else:
            self.edit_name_var.set('')
            self.edit_desc_text.delete('1.0', tk.END)
            self.current_selection = None

        self.details_text.config(state=tk.DISABLED)

    def refresh_agents(self):
        """Refresh agents display for assignment with filtering"""
        for item in self.agents_tree.get_children():
            self.agents_tree.delete(item)

        # Update validation label
        self.update_assignment_validation()

        try:
            # Build query with filters
            base_query = '''
                SELECT a.agent_id, a.name, s.name as session_name, a.teams
                FROM agents a
                LEFT JOIN sessions s ON a.session_id = s.id
                WHERE a.is_active = 1
            '''

            # Add filter conditions
            conditions = []
            params = []

            # Filter by search text
            if hasattr(self, 'agent_filter_var'):
                filter_text = self.agent_filter_var.get().strip().lower()
                if filter_text:
                    conditions.append('(LOWER(a.agent_id) LIKE ? OR LOWER(a.name) LIKE ? OR LOWER(a.teams) LIKE ?)')
                    params.extend([f'%{filter_text}%'] * 3)

            # Filter by unassigned only
            if hasattr(self, 'show_unassigned_var') and self.show_unassigned_var.get():
                conditions.append('a.session_id IS NULL')

            if conditions:
                base_query += ' AND ' + ' AND '.join(conditions)

            base_query += ' ORDER BY a.agent_id'

            try:
                agents = self.db_manager.execute_query(base_query, params if params else None)
            except sqlite3.OperationalError:
                # Add session_id column if it doesn't exist
                try:
                    self.db_manager.execute_update('ALTER TABLE agents ADD COLUMN session_id INTEGER')
                except:
                    pass  # Column might already exist

                # Retry query
                agents = self.db_manager.execute_query(base_query, params if params else None)

            for agent in agents:
                agent_id, name, session_name, teams = agent

                # Color code based on assignment status
                if session_name:
                    # Assigned agent
                    tags = ('assigned',)
                    display_session = f"🟢 {session_name}"
                else:
                    # Unassigned agent
                    tags = ('unassigned',)
                    display_session = "🔴 Unassigned"

                item = self.agents_tree.insert(
                    '',
                    'end',
                    text=agent_id,
                    values=(name or agent_id, display_session, teams or 'None'),
                    tags=tags
                )

            # Configure tags for visual feedback
            self.agents_tree.tag_configure('assigned', foreground='dark green')
            self.agents_tree.tag_configure('unassigned', foreground='red')

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load agents: {e}")

    def update_assignment_validation(self):
        """Update the assignment validation display"""
        try:
            selection = self.agents_tree.selection()
            session_selection = self.assign_session_var.get()

            if not selection:
                self.validation_label.config(text="📋 Select agents to see assignment validation", foreground="blue")
                return

            if not session_selection:
                self.validation_label.config(text="⚠️ Select a session for assignment", foreground="orange")
                return

            # Check for conflicts
            conflicts = []
            for item in selection:
                agent_id = self.agents_tree.item(item)['text']
                try:
                    current_session = self.db_manager.execute_query(
                        "SELECT session_id FROM agents WHERE agent_id = ? AND session_id IS NOT NULL",
                        (agent_id,)
                    )
                    if current_session:
                        conflicts.append(agent_id)
                except:
                    pass  # session_id column might not exist

            if conflicts:
                self.validation_label.config(
                    text=f"⚠️ {len(conflicts)} agent(s) already assigned to other sessions",
                    foreground="orange"
                )
            else:
                self.validation_label.config(
                    text=f"✅ Ready to assign {len(selection)} agent(s)",
                    foreground="green"
                )

        except Exception as e:
            self.validation_label.config(text=f"❌ Validation error: {str(e)}", foreground="red")

    def refresh_session_combo(self):
        """Refresh session combo box options"""
        try:
            sessions = self.db_manager.execute_query('''
                SELECT s.id, s.name, p.name as project_name
                FROM sessions s
                LEFT JOIN projects p ON s.project_id = p.id
                ORDER BY p.name, s.name
            ''')
            session_options = [f"{session[2] or 'Unknown'} > {session[1]} (ID: {session[0]})" for session in sessions]
            self.assign_session_combo['values'] = session_options

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load sessions for combo: {e}")

    def new_project(self):
        """Create a new project with enhanced validation"""
        name = simpledialog.askstring("New Project", "Enter project name:")
        if not name:
            return

        # Enhanced validation
        is_valid, error_msg = self.validator.validate_project_name(name)
        if not is_valid:
            messagebox.showerror("Validation Error", error_msg)
            return

        description = simpledialog.askstring("New Project", "Enter project description (optional):")

        try:
            self.db_manager.execute_update(
                "INSERT INTO projects (name, description) VALUES (?, ?)",
                (name.strip(), description.strip() if description else '')
            )
            self.refresh_tree()
            messagebox.showinfo("Success", f"Project '{name.strip()}' created successfully")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to create project: {e}")

    def new_session(self):
        """Create a new session with enhanced validation"""
        # First get available projects
        try:
            projects = self.db_manager.execute_query('SELECT id, name FROM projects ORDER BY name')
            if not projects:
                messagebox.showwarning("Warning", "No projects available. Create a project first.")
                return

            # Simple dialog for project selection
            project_name = simpledialog.askstring(
                "New Session",
                f"Available projects: {', '.join([p[1] for p in projects])}\nEnter project name:"
            )
            if not project_name:
                return

            # Find project ID
            project_id = None
            for proj_id, proj_name in projects:
                if proj_name.lower() == project_name.lower():
                    project_id = proj_id
                    break

            if project_id is None:
                messagebox.showerror("Error", f"Project '{project_name}' not found")
                return

            # Get session name
            session_name = simpledialog.askstring("New Session", "Enter session name:")
            if not session_name:
                return

            # Enhanced validation
            is_valid, error_msg = self.validator.validate_session_name(session_name, project_id)
            if not is_valid:
                messagebox.showerror("Validation Error", error_msg)
                return

            self.db_manager.execute_update(
                "INSERT INTO sessions (project_id, name) VALUES (?, ?)",
                (project_id, session_name.strip())
            )
            self.refresh_tree()
            messagebox.showinfo("Success", f"Session '{session_name.strip()}' created successfully")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to create session: {e}")

    def delete_selected(self):
        """Delete selected item from tree"""
        selection = self.project_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an item to delete")
            return

        item = self.project_tree.item(selection[0])
        values = item.get('values', [])

        if len(values) >= 2:
            item_type, item_id = values[0], values[1]
        else:
            messagebox.showwarning("Warning", "Cannot delete this item")
            return

        item_text = item['text']

        if item_type == 'project':
            if messagebox.askyesno("Confirm Delete", f"Delete project '{item_text}' and all its sessions?"):
                try:
                    # Delete sessions first
                    self.db_manager.execute_update("DELETE FROM sessions WHERE project_id = ?", (item_id,))
                    # Delete project
                    self.db_manager.execute_update("DELETE FROM projects WHERE id = ?", (item_id,))
                    self.refresh_tree()
                    messagebox.showinfo("Success", f"Project deleted")
                except Exception as e:
                    messagebox.showerror("Database Error", f"Failed to delete project: {e}")

        elif item_type == 'session':
            if messagebox.askyesno("Confirm Delete", f"Delete session '{item_text}'?"):
                try:
                    # Unassign agents from this session first
                    try:
                        self.db_manager.execute_update("UPDATE agents SET session_id = NULL WHERE session_id = ?", (item_id,))
                    except:
                        pass  # session_id column might not exist yet

                    # Delete session
                    self.db_manager.execute_update("DELETE FROM sessions WHERE id = ?", (item_id,))
                    self.refresh_tree()
                    messagebox.showinfo("Success", f"Session deleted")
                except Exception as e:
                    messagebox.showerror("Database Error", f"Failed to delete session: {e}")

        elif item_type == 'agent':
            messagebox.showinfo("Info", "Agents cannot be deleted from this view. Use the Agent Management tab.")

    def assign_agents(self):
        """Assign selected agents to selected session"""
        agent_selection = self.agents_tree.selection()
        session_selection = self.assign_session_var.get()

        if not agent_selection:
            messagebox.showwarning("Warning", "Please select agents to assign")
            return

        if not session_selection:
            messagebox.showwarning("Warning", "Please select a session")
            return

        # Extract session ID from selection
        try:
            session_id = int(session_selection.split("ID: ")[1].rstrip(")"))
        except (IndexError, ValueError):
            messagebox.showerror("Error", "Invalid session selection")
            return

        try:
            agent_ids = [self.agents_tree.item(item)['text'] for item in agent_selection]

            # Check if agents are assigned to other sessions
            conflicts = []
            for agent_id in agent_ids:
                try:
                    existing = self.db_manager.execute_query(
                        "SELECT session_id FROM agents WHERE agent_id = ? AND session_id IS NOT NULL",
                        (agent_id,)
                    )
                    if existing and existing[0][0] != session_id:
                        conflicts.append(agent_id)
                except:
                    pass  # session_id column might not exist

            if conflicts:
                if not messagebox.askyesno("Confirm",
                    f"The following agents are already assigned to other sessions: {', '.join(conflicts)}\n"
                    f"Do you want to reassign them?"):
                    return

            for agent_id in agent_ids:
                try:
                    self.db_manager.execute_update(
                        "UPDATE agents SET session_id = ? WHERE agent_id = ?",
                        (session_id, agent_id)
                    )
                except sqlite3.OperationalError:
                    # Add session_id column if it doesn't exist
                    try:
                        self.db_manager.execute_update('ALTER TABLE agents ADD COLUMN session_id INTEGER')
                        self.db_manager.execute_update(
                            "UPDATE agents SET session_id = ? WHERE agent_id = ?",
                            (session_id, agent_id)
                        )
                    except Exception as e:
                        messagebox.showerror("Database Error", f"Failed to add session_id column: {e}")
                        return

            self.refresh_tree()
            messagebox.showinfo("Success", f"Assigned {len(agent_ids)} agents to session")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to assign agents: {e}")

    def unassign_agents(self):
        """Unassign selected agents from their sessions"""
        selection = self.agents_tree.selection()

        if not selection:
            messagebox.showwarning("Warning", "Please select agents to unassign")
            return

        try:
            agent_ids = [self.agents_tree.item(item)['text'] for item in selection]

            for agent_id in agent_ids:
                try:
                    self.db_manager.execute_update(
                        "UPDATE agents SET session_id = NULL WHERE agent_id = ?",
                        (agent_id,)
                    )
                except sqlite3.OperationalError:
                    # session_id column doesn't exist, so agents aren't assigned
                    pass

            self.refresh_tree()
            messagebox.showinfo("Success", f"Unassigned {len(agent_ids)} agents")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to unassign agents: {e}")

    def on_drag_start(self, event):
        """Handle start of drag operation"""
        item = self.project_tree.identify_row(event.y)
        if item:
            item_values = self.project_tree.item(item).get('values', [])
            # Only allow dragging agents
            if len(item_values) >= 2 and item_values[0] == 'agent':
                self.drag_data["item"] = item
                self.drag_data["x"] = event.x
                self.drag_data["y"] = event.y
                # Change cursor to indicate dragging
                self.project_tree.config(cursor="hand2")

    def on_drag_motion(self, event):
        """Handle drag motion"""
        if self.drag_data["item"]:
            # Update cursor position
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y

    def on_drag_release(self, event):
        """Handle end of drag operation"""
        if self.drag_data["item"]:
            # Reset cursor
            self.project_tree.config(cursor="")

            # Get target item
            target_item = self.project_tree.identify_row(event.y)
            if target_item and target_item != self.drag_data["item"]:
                target_values = self.project_tree.item(target_item).get('values', [])

                # Can only drop on sessions
                if len(target_values) >= 2 and target_values[0] == 'session':
                    source_values = self.project_tree.item(self.drag_data["item"]).get('values', [])
                    if len(source_values) >= 2:
                        agent_id = source_values[1]
                        target_session_id = target_values[1]

                        # Confirm the move
                        agent_text = self.project_tree.item(self.drag_data["item"])['text']
                        session_text = self.project_tree.item(target_item)['text']

                        if messagebox.askyesno("Confirm Move",
                            f"Move {agent_text} to {session_text}?"):
                            self.move_agent_to_session(agent_id, target_session_id)

            # Reset drag data
            self.drag_data = {"item": None, "x": 0, "y": 0}

    def move_agent_to_session(self, agent_id, session_id):
        """Move an agent to a different session"""
        try:
            # Check if agent exists and get current assignment
            current_assignment = self.db_manager.execute_query(
                "SELECT session_id FROM agents WHERE agent_id = ?", (agent_id,)
            )

            if not current_assignment:
                messagebox.showerror("Error", f"Agent '{agent_id}' not found")
                return

            # Update agent's session assignment
            self.db_manager.execute_update(
                "UPDATE agents SET session_id = ? WHERE agent_id = ?",
                (session_id, agent_id)
            )

            # Refresh the tree to show the change
            self.refresh_tree()

            messagebox.showinfo("Success", f"Agent '{agent_id}' moved to new session")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to move agent: {e}")

class RedesignedComprehensiveGUI:
    """Main GUI class implementing all specifications"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Multi-Agent MCP Context Manager - Redesigned")

        # Use standard 16:10 ratio (1440x900) scaled for better visibility
        self.root.geometry("1440x900")
        self.root.minsize(1200, 750)  # Minimum size for functionality

        # Set larger default font for better readability
        self.root.option_add('*Font', 'Arial 14')

        # Configure ttk styles with larger fonts (minimum 14pt)
        style = ttk.Style()
        style.configure('TLabel', font=('Arial', 14))
        style.configure('TButton', font=('Arial', 14), padding=(12, 8))
        style.configure('TEntry', font=('Arial', 14), fieldbackground='white')
        style.configure('TCombobox', font=('Arial', 14), fieldbackground='white')
        style.configure('Treeview', font=('Arial', 14), rowheight=32)
        style.configure('Treeview.Heading', font=('Arial', 14, 'bold'))
        style.configure('TLabelFrame', font=('Arial', 16, 'bold'))
        style.configure('TNotebook.Tab', font=('Arial', 14, 'bold'), padding=(16, 10))

        # Initialize components
        self.db_manager = DatabaseManager()

        # Status monitoring
        self.status_monitor = ServerStatusMonitor(self.update_status)

        # Create main interface
        self.create_main_interface()

        # Start status monitoring
        self.status_monitor.start_monitoring()

        # Setup cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_main_interface(self):
        """Create the main interface"""
        # Main notebook
        self.main_notebook = ttk.Notebook(self.root)
        self.main_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create all tabs
        self.create_all_tabs()

        # Status bar
        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def create_all_tabs(self):
        """Create all management tabs"""
        # Data Format Instructions Tab (reimplemented)
        instructions_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(instructions_frame, text="📋 Data Format Instructions")

        instructions_widget = DataFormatInstructionsTab(instructions_frame)
        instructions_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

        # Project & Sessions Tab (reimplemented)
        project_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(project_frame, text="📁 Projects & Sessions")

        project_widget = ProjectSessionTab(project_frame, self.db_manager)
        project_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

        # Connection Assignment Tab (redesigned)
        connection_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(connection_frame, text="🔗 Connection Assignment")

        connection_widget = ConnectionAssignmentTab(connection_frame, self.db_manager)
        connection_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

        # Agent Management Tab (enhanced)
        agent_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(agent_frame, text="👥 Agent Management")

        agent_widget = AgentManagementTab(agent_frame, self.db_manager)
        agent_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

        # Contexts Tab (new)
        contexts_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(contexts_frame, text="📄 Contexts")

        contexts_widget = ContextsTab(contexts_frame, self.db_manager)
        contexts_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

    def update_status(self, status_data):
        """Update status bar with new data"""
        if hasattr(self, 'status_bar'):
            self.status_bar.update_status(status_data)

    def on_closing(self):
        """Clean up resources when closing the application"""
        try:
            # Stop status monitoring
            if hasattr(self, 'status_monitor'):
                self.status_monitor.stop_monitoring()

            # Close database connection pool
            if hasattr(self, 'db_manager'):
                self.db_manager.close_pool()

            # Destroy the root window
            self.root.destroy()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            # Force close
            try:
                self.root.destroy()
            except:
                pass

    def run(self):
        """Start the GUI with improved error recovery"""
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"GUI application error: {e}")
            messagebox.showerror("Application Error", f"An unexpected error occurred: {e}")
        finally:
            # Ensure cleanup happens
            try:
                if hasattr(self, 'status_monitor'):
                    self.status_monitor.stop_monitoring()
                if hasattr(self, 'db_manager'):
                    self.db_manager.close_pool()
            except Exception as e:
                print(f"Error during cleanup: {e}")

def main():
    """Main entry point"""
    app = RedesignedComprehensiveGUI()
    app.run()

if __name__ == "__main__":
    main()