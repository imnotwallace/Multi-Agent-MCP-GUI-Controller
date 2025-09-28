#!/usr/bin/env python3
"""
Connection Assignment Tab Module
Extracted from redesigned_comprehensive_gui.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import requests


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