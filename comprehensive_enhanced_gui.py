#!/usr/bin/env python3
"""
Comprehensive Enhanced GUI Module for Multi-Agent MCP Context Manager
Implements redesigned system requirements

Features:
- Agent management with read levels and team configuration
- Project and session management
- Connection assignment with auto-matching
- Data format instructions
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import json
import sqlite3
import requests
import os
from datetime import datetime
from typing import Dict, List, Optional, Set

class DatabaseManager:
    """Handles all database operations"""

    def __init__(self, db_path="multi-agent_mcp_context_manager.db"):
        self.db_path = db_path

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def execute_query(self, query, params=None):
        """Execute a query and return results"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()

    def execute_update(self, query, params=None):
        """Execute an update/insert/delete query"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor.rowcount

class ConnectionManagementTab:
    """Manages agent-connection assignments"""

    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db_manager = db_manager
        self.frame = ttk.Frame(parent)

    def create_widgets(self):
        """Create connection management widgets"""
        # Title
        title_label = ttk.Label(
            self.frame,
            text="🔗 Agent-Connection Management",
            font=("Arial", 12, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Instructions
        instructions = ttk.Label(
            self.frame,
            text="Manage agent-connection assignments. Connections matching agent IDs are auto-assigned.",
            wraplength=600
        )
        instructions.pack(pady=(0, 10))

        # Main container
        main_container = ttk.Frame(self.frame)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Connections tree
        columns = ('connection_id', 'assigned_agent', 'status', 'first_seen', 'last_seen')
        self.connections_tree = ttk.Treeview(
            main_container,
            columns=columns,
            show='tree headings',
            height=15
        )

        self.connections_tree.heading('#0', text='#')
        self.connections_tree.heading('connection_id', text='Connection ID')
        self.connections_tree.heading('assigned_agent', text='Assigned Agent')
        self.connections_tree.heading('status', text='Status')
        self.connections_tree.heading('first_seen', text='First Seen')
        self.connections_tree.heading('last_seen', text='Last Seen')

        self.connections_tree.column('#0', width=50)
        self.connections_tree.column('connection_id', width=150)
        self.connections_tree.column('assigned_agent', width=150)
        self.connections_tree.column('status', width=100)
        self.connections_tree.column('first_seen', width=150)
        self.connections_tree.column('last_seen', width=150)

        self.connections_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Control buttons
        control_frame = ttk.Frame(main_container)
        control_frame.pack(fill=tk.X)

        # Manual assignment controls
        assign_frame = ttk.LabelFrame(control_frame, text="Manual Assignment", padding=5)
        assign_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        ttk.Label(assign_frame, text="Agent ID:").pack(side=tk.LEFT)
        self.agent_assignment_entry = ttk.Entry(assign_frame, width=20)
        self.agent_assignment_entry.pack(side=tk.LEFT, padx=(5, 10))

        ttk.Button(
            assign_frame,
            text="Assign to Selected Connection",
            command=self.assign_agent_manually
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            assign_frame,
            text="Unassign Selected",
            command=self.unassign_connection
        ).pack(side=tk.LEFT)

        # Action buttons
        action_frame = ttk.Frame(control_frame)
        action_frame.pack(side=tk.RIGHT)

        ttk.Button(
            action_frame,
            text="🔄 Refresh",
            command=self.refresh_connections
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text="🗑️ Delete Selected",
            command=self.delete_connection
        ).pack(side=tk.LEFT)

        # Load initial data
        self.refresh_connections()

        return self.frame

    def refresh_connections(self):
        """Refresh connections display"""
        for item in self.connections_tree.get_children():
            self.connections_tree.delete(item)

        try:
            connections = self.db_manager.execute_query('''
                SELECT connection_id, assigned_agent_id, status, first_seen, last_seen
                FROM connections
                ORDER BY first_seen DESC
            ''')

            for i, connection in enumerate(connections, 1):
                connection_id, assigned_agent, status, first_seen, last_seen = connection

                self.connections_tree.insert(
                    '',
                    'end',
                    text=str(i),
                    values=(
                        connection_id,
                        assigned_agent or 'Not Assigned',
                        status,
                        first_seen or 'Unknown',
                        last_seen or 'Unknown'
                    )
                )

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load connections: {e}")

    def assign_agent_manually(self):
        """Manually assign agent to selected connection"""
        selection = self.connections_tree.selection()
        agent_id = self.agent_assignment_entry.get().strip()

        if not selection:
            messagebox.showwarning("Warning", "Please select a connection to assign")
            return

        if not agent_id:
            messagebox.showwarning("Warning", "Please enter an agent ID")
            return

        try:
            connection_id = self.connections_tree.item(selection[0])['values'][0]

            # Update database
            self.db_manager.execute_update('''
                UPDATE connections
                SET assigned_agent_id = ?, status = 'assigned'
                WHERE connection_id = ?
            ''', (agent_id, connection_id))

            # Update agent if exists
            self.db_manager.execute_update('''
                UPDATE agents
                SET connection_id = ?, last_seen = CURRENT_TIMESTAMP
                WHERE assigned_agent_id = ?
            ''', (connection_id, agent_id))

            self.agent_assignment_entry.delete(0, tk.END)
            self.refresh_connections()
            messagebox.showinfo("Success", f"Agent {agent_id} assigned to connection {connection_id}")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to assign agent: {e}")

    def unassign_connection(self):
        """Unassign agent from selected connection"""
        selection = self.connections_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a connection to unassign")
            return

        try:
            connection_id = self.connections_tree.item(selection[0])['values'][0]
            assigned_agent = self.connections_tree.item(selection[0])['values'][1]

            if assigned_agent == 'Not Assigned':
                messagebox.showwarning("Warning", "Connection is not assigned to any agent")
                return

            if messagebox.askyesno("Confirm", f"Unassign agent from connection {connection_id}?"):
                # Update database
                self.db_manager.execute_update('''
                    UPDATE connections
                    SET assigned_agent_id = NULL, status = 'pending'
                    WHERE connection_id = ?
                ''', (connection_id,))

                # Clear agent connection
                self.db_manager.execute_update('''
                    UPDATE agents
                    SET connection_id = NULL
                    WHERE assigned_agent_id = ?
                ''', (assigned_agent,))

                self.refresh_connections()
                messagebox.showinfo("Success", f"Connection {connection_id} unassigned")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to unassign connection: {e}")

    def delete_connection(self):
        """Delete selected connection"""
        selection = self.connections_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a connection to delete")
            return

        try:
            connection_id = self.connections_tree.item(selection[0])['values'][0]

            if messagebox.askyesno("Confirm", f"Delete connection {connection_id}?"):
                # Clear agent connection first
                assigned_agent = self.connections_tree.item(selection[0])['values'][1]
                if assigned_agent != 'Not Assigned':
                    self.db_manager.execute_update('''
                        UPDATE agents
                        SET connection_id = NULL
                        WHERE assigned_agent_id = ?
                    ''', (assigned_agent,))

                # Delete connection
                self.db_manager.execute_update('''
                    DELETE FROM connections WHERE connection_id = ?
                ''', (connection_id,))

                self.refresh_connections()
                messagebox.showinfo("Success", f"Connection {connection_id} deleted")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to delete connection: {e}")

class AgentManagementTab:
    """Manages agent configuration tab"""

    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db_manager = db_manager
        self.frame = ttk.Frame(parent)

    def create_widgets(self):
        """Create agent management widgets"""
        # Title
        title_label = ttk.Label(
            self.frame,
            text="👥 Agent Management & Configuration",
            font=("Arial", 12, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Create notebook for agent management subtabs
        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Agent List Tab
        self.create_agent_list_tab()

        # Permission Management Tab
        self.create_permission_tab()

        # Team Management Tab
        self.create_team_tab()

        return self.frame

    def create_agent_list_tab(self):
        """Create agent list and basic management tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="🏷️ Agent List")

        # Controls frame
        controls_frame = ttk.Frame(frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)

        # Add new agent
        ttk.Label(controls_frame, text="Add Agent:").pack(side=tk.LEFT)
        self.new_agent_entry = ttk.Entry(controls_frame, width=20)
        self.new_agent_entry.pack(side=tk.LEFT, padx=(5, 10))

        add_agent_btn = ttk.Button(
            controls_frame,
            text="➕ Add Agent",
            command=self.add_new_agent
        )
        add_agent_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Refresh button
        refresh_btn = ttk.Button(
            controls_frame,
            text="🔄 Refresh",
            command=self.refresh_agents
        )
        refresh_btn.pack(side=tk.RIGHT)

        # Agent tree
        columns = ('agent_id', 'name', 'connection_id', 'team_id', 'read_permission', 'is_active')
        self.agent_tree = ttk.Treeview(
            frame,
            columns=columns,
            show='tree headings'
        )

        # Configure columns
        self.agent_tree.heading('#0', text='#')
        self.agent_tree.heading('agent_id', text='Agent ID')
        self.agent_tree.heading('name', text='Name')
        self.agent_tree.heading('connection_id', text='Connection')
        self.agent_tree.heading('team_id', text='Team')
        self.agent_tree.heading('read_permission', text='Permission')
        self.agent_tree.heading('is_active', text='Active')

        # Set column widths
        self.agent_tree.column('#0', width=50)
        self.agent_tree.column('agent_id', width=120)
        self.agent_tree.column('name', width=120)
        self.agent_tree.column('connection_id', width=120)
        self.agent_tree.column('team_id', width=100)
        self.agent_tree.column('read_permission', width=100)
        self.agent_tree.column('is_active', width=80)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.agent_tree.yview)
        self.agent_tree.configure(yscrollcommand=scrollbar.set)

        # Pack tree and scrollbar
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.agent_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Context menu
        self.agent_tree.bind("<Button-3>", self.show_agent_context_menu)
        self.agent_tree.bind("<Double-1>", self.rename_agent)

        # Action buttons
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill=tk.X, padx=10, pady=5)

        rename_btn = ttk.Button(
            action_frame,
            text="✏️ Rename Selected",
            command=self.rename_agent
        )
        rename_btn.pack(side=tk.LEFT, padx=(0, 10))

        delete_btn = ttk.Button(
            action_frame,
            text="🗑️ Delete Selected",
            command=self.delete_agent
        )
        delete_btn.pack(side=tk.LEFT)

        # Load initial data
        self.refresh_agents()

    def create_permission_tab(self):
        """Create permission management tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="🔐 Permissions")

        # Instructions
        instructions = ttk.Label(
            frame,
            text="Configure read permission levels for agents (self_only, team_level, session_level)",
            wraplength=600
        )
        instructions.pack(pady=10)

        # Bulk permission controls
        bulk_frame = ttk.LabelFrame(frame, text="Bulk Permission Operations", padding=10)
        bulk_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(bulk_frame, text="Set permission for selected agents:").pack(side=tk.LEFT)

        self.bulk_permission_var = tk.StringVar(value="self_only")
        permission_combo = ttk.Combobox(
            bulk_frame,
            textvariable=self.bulk_permission_var,
            values=["self_only", "team_level", "session_level"],
            state="readonly",
            width=15
        )
        permission_combo.pack(side=tk.LEFT, padx=(10, 10))

        apply_permission_btn = ttk.Button(
            bulk_frame,
            text="Apply to Selected",
            command=self.apply_bulk_permission
        )
        apply_permission_btn.pack(side=tk.LEFT)

        # Permission tree (reuse agent tree structure)
        columns = ('agent_id', 'current_permission', 'team_id', 'contexts_count')
        self.permission_tree = ttk.Treeview(
            frame,
            columns=columns,
            show='tree headings'
        )

        self.permission_tree.heading('#0', text='#')
        self.permission_tree.heading('agent_id', text='Agent ID')
        self.permission_tree.heading('current_permission', text='Current Permission')
        self.permission_tree.heading('team_id', text='Team')
        self.permission_tree.heading('contexts_count', text='Contexts')

        self.permission_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.refresh_permissions()

    def create_team_tab(self):
        """Create team management tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="👥 Teams")

        # Team management controls
        team_controls = ttk.Frame(frame)
        team_controls.pack(fill=tk.X, padx=10, pady=5)

        # Create team
        ttk.Label(team_controls, text="Create Team:").pack(side=tk.LEFT)
        self.new_team_entry = ttk.Entry(team_controls, width=20)
        self.new_team_entry.pack(side=tk.LEFT, padx=(5, 10))

        create_team_btn = ttk.Button(
            team_controls,
            text="➕ Create Team",
            command=self.create_team
        )
        create_team_btn.pack(side=tk.LEFT, padx=(0, 20))

        # Team assignment
        ttk.Label(team_controls, text="Assign to Team:").pack(side=tk.LEFT)
        self.team_assignment_var = tk.StringVar()
        self.team_combo = ttk.Combobox(
            team_controls,
            textvariable=self.team_assignment_var,
            width=15,
            state="readonly"
        )
        self.team_combo.pack(side=tk.LEFT, padx=(5, 10))

        assign_team_btn = ttk.Button(
            team_controls,
            text="Assign Selected",
            command=self.assign_to_team
        )
        assign_team_btn.pack(side=tk.LEFT)

        # Two-pane layout
        paned_window = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left pane - Teams
        left_frame = ttk.LabelFrame(paned_window, text="Teams", padding=5)
        paned_window.add(left_frame, weight=1)

        self.teams_listbox = tk.Listbox(left_frame)
        self.teams_listbox.pack(fill=tk.BOTH, expand=True)
        self.teams_listbox.bind('<<ListboxSelect>>', self.on_team_select)

        # Right pane - Team members
        right_frame = ttk.LabelFrame(paned_window, text="Team Members", padding=5)
        paned_window.add(right_frame, weight=2)

        self.team_members_tree = ttk.Treeview(
            right_frame,
            columns=('agent_id', 'name', 'permission'),
            show='tree headings'
        )

        self.team_members_tree.heading('#0', text='#')
        self.team_members_tree.heading('agent_id', text='Agent ID')
        self.team_members_tree.heading('name', text='Name')
        self.team_members_tree.heading('permission', text='Permission')

        self.team_members_tree.pack(fill=tk.BOTH, expand=True)

        self.refresh_teams()

    def refresh_agents(self):
        """Refresh the agents display"""
        # Clear existing items
        for item in self.agent_tree.get_children():
            self.agent_tree.delete(item)

        try:
            agents = self.db_manager.execute_query('''
                SELECT assigned_agent_id, name, connection_id, team_id, read_permission, is_active
                FROM agents
                ORDER BY created_at DESC
            ''')

            for i, agent in enumerate(agents, 1):
                agent_id, name, connection_id, team_id, read_permission, is_active = agent

                self.agent_tree.insert(
                    '',
                    'end',
                    text=str(i),
                    values=(
                        agent_id or '',
                        name or '',
                        connection_id or 'Not Assigned',
                        team_id or 'No Team',
                        read_permission or 'self_only',
                        'Yes' if is_active else 'No'
                    )
                )
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load agents: {e}")

    def refresh_permissions(self):
        """Refresh the permissions display"""
        for item in self.permission_tree.get_children():
            self.permission_tree.delete(item)

        try:
            agents = self.db_manager.execute_query('''
                SELECT a.assigned_agent_id, a.read_permission, a.team_id,
                       COUNT(c.id) as context_count
                FROM agents a
                LEFT JOIN contexts c ON a.assigned_agent_id = c.agent_id
                WHERE a.is_active = 1
                GROUP BY a.assigned_agent_id, a.read_permission, a.team_id
                ORDER BY a.assigned_agent_id
            ''')

            for i, agent in enumerate(agents, 1):
                agent_id, permission, team_id, context_count = agent

                self.permission_tree.insert(
                    '',
                    'end',
                    text=str(i),
                    values=(
                        agent_id,
                        permission or 'self_only',
                        team_id or 'No Team',
                        context_count
                    )
                )
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load permissions: {e}")

    def refresh_teams(self):
        """Refresh teams display"""
        self.teams_listbox.delete(0, tk.END)

        try:
            # Get unique teams
            teams = self.db_manager.execute_query('''
                SELECT DISTINCT team_id
                FROM agents
                WHERE team_id IS NOT NULL AND team_id != ''
                ORDER BY team_id
            ''')

            team_list = [team[0] for team in teams]

            for team in team_list:
                self.teams_listbox.insert(tk.END, team)

            # Update team combo
            self.team_combo['values'] = team_list

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load teams: {e}")

    def add_new_agent(self):
        """Add a new agent"""
        agent_id = self.new_agent_entry.get().strip()
        if not agent_id:
            messagebox.showwarning("Warning", "Please enter an agent ID")
            return

        try:
            # Check if agent already exists
            existing = self.db_manager.execute_query(
                "SELECT assigned_agent_id FROM agents WHERE assigned_agent_id = ?",
                (agent_id,)
            )

            if existing:
                messagebox.showwarning("Warning", f"Agent {agent_id} already exists")
                return

            # Add new agent
            self.db_manager.execute_update('''
                INSERT INTO agents (assigned_agent_id, name, read_permission, is_active)
                VALUES (?, ?, 'self_only', 1)
            ''', (agent_id, agent_id))

            self.new_agent_entry.delete(0, tk.END)
            self.refresh_agents()
            messagebox.showinfo("Success", f"Agent {agent_id} added")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to add agent: {e}")

    def rename_agent(self, event=None):
        """Rename selected agent"""
        selection = self.agent_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an agent to rename")
            return

        item = selection[0]
        agent_id = self.agent_tree.item(item)['values'][0]
        current_name = self.agent_tree.item(item)['values'][1]

        new_name = simpledialog.askstring(
            "Rename Agent",
            f"Enter new name for agent {agent_id}:",
            initialvalue=current_name
        )

        if new_name and new_name != current_name:
            try:
                self.db_manager.execute_update(
                    "UPDATE agents SET name = ? WHERE assigned_agent_id = ?",
                    (new_name, agent_id)
                )
                self.refresh_agents()
                messagebox.showinfo("Success", f"Agent {agent_id} renamed to {new_name}")
            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to rename agent: {e}")

    def delete_agent(self):
        """Delete selected agent and all associated contexts"""
        selection = self.agent_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an agent to delete")
            return

        item = selection[0]
        agent_id = self.agent_tree.item(item)['values'][0]

        # Get context count
        try:
            context_count = self.db_manager.execute_query(
                "SELECT COUNT(*) FROM contexts WHERE agent_id = ?",
                (agent_id,)
            )[0][0]

            warning_msg = f"Delete agent {agent_id}?"
            if context_count > 0:
                warning_msg += f"\nThis will also delete {context_count} associated contexts."

            if messagebox.askyesno("Confirm Deletion", warning_msg):
                # Delete contexts first
                self.db_manager.execute_update(
                    "DELETE FROM contexts WHERE agent_id = ?",
                    (agent_id,)
                )

                # Delete agent
                self.db_manager.execute_update(
                    "DELETE FROM agents WHERE assigned_agent_id = ?",
                    (agent_id,)
                )

                self.refresh_agents()
                messagebox.showinfo("Success", f"Agent {agent_id} and {context_count} contexts deleted")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to delete agent: {e}")

    def apply_bulk_permission(self):
        """Apply permission to selected agents"""
        selection = self.permission_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select agents to update")
            return

        permission = self.bulk_permission_var.get()
        agent_ids = [self.permission_tree.item(item)['values'][0] for item in selection]

        try:
            for agent_id in agent_ids:
                self.db_manager.execute_update(
                    "UPDATE agents SET read_permission = ? WHERE assigned_agent_id = ?",
                    (permission, agent_id)
                )

            self.refresh_permissions()
            messagebox.showinfo("Success", f"Updated permission to {permission} for {len(agent_ids)} agents")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to update permissions: {e}")

    def create_team(self):
        """Create a new team"""
        team_name = self.new_team_entry.get().strip()
        if not team_name:
            messagebox.showwarning("Warning", "Please enter a team name")
            return

        self.new_team_entry.delete(0, tk.END)
        self.refresh_teams()
        messagebox.showinfo("Success", f"Team structure ready for {team_name}")

    def assign_to_team(self):
        """Assign selected agents to team"""
        selection = self.agent_tree.selection()
        team = self.team_assignment_var.get()

        if not selection:
            messagebox.showwarning("Warning", "Please select agents to assign")
            return

        if not team:
            messagebox.showwarning("Warning", "Please select a team")
            return

        try:
            agent_ids = [self.agent_tree.item(item)['values'][0] for item in selection]

            for agent_id in agent_ids:
                self.db_manager.execute_update(
                    "UPDATE agents SET team_id = ? WHERE assigned_agent_id = ?",
                    (team, agent_id)
                )

            self.refresh_agents()
            self.refresh_teams()
            messagebox.showinfo("Success", f"Assigned {len(agent_ids)} agents to team {team}")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to assign to team: {e}")

    def on_team_select(self, event):
        """Handle team selection"""
        selection = self.teams_listbox.curselection()
        if not selection:
            return

        team_id = self.teams_listbox.get(selection[0])

        # Clear team members tree
        for item in self.team_members_tree.get_children():
            self.team_members_tree.delete(item)

        try:
            members = self.db_manager.execute_query('''
                SELECT assigned_agent_id, name, read_permission
                FROM agents
                WHERE team_id = ? AND is_active = 1
                ORDER BY assigned_agent_id
            ''', (team_id,))

            for i, member in enumerate(members, 1):
                agent_id, name, permission = member
                self.team_members_tree.insert(
                    '',
                    'end',
                    text=str(i),
                    values=(agent_id, name or agent_id, permission or 'self_only')
                )

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load team members: {e}")

    def show_agent_context_menu(self, event):
        """Show context menu for agent"""
        # This could be expanded with more context menu options
        pass

class LazyTreeView(ttk.Treeview):
    """Treeview with lazy loading for large datasets"""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.data_loader = None
        self.loaded_items = set()
        self.bind('<<TreeviewOpen>>', self.on_item_open)

    def set_data_loader(self, loader):
        """Set function to load data on demand"""
        self.data_loader = loader

    def on_item_open(self, event):
        """Load children when item is expanded"""
        item = self.focus()
        if item not in self.loaded_items and self.data_loader:
            self.data_loader(item)
            self.loaded_items.add(item)

class ProjectSessionTab:
    """Manages projects and sessions with tree structure"""

    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db_manager = db_manager
        self.frame = ttk.Frame(parent)

    def create_widgets(self):
        """Create project/session management widgets with tree structure"""
        # Title
        title_label = ttk.Label(
            self.frame,
            text="📁 Project & Session Management",
            font=("Arial", 12, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Main container with two panels
        main_container = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel - Tree structure
        left_frame = ttk.LabelFrame(main_container, text="Project Structure", padding=10)
        main_container.add(left_frame, weight=1)

        # Tree view
        self.project_tree = LazyTreeView(left_frame, height=15)
        self.project_tree.heading('#0', text='Project Structure')
        self.project_tree.column('#0', width=350)
        self.project_tree.pack(fill=tk.BOTH, expand=True)
        self.project_tree.bind('<<TreeviewSelect>>', self.on_tree_select)

        # Set up lazy loading
        self.project_tree.set_data_loader(self.load_tree_children)

        # Control buttons
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="➕ New Project", command=self.new_project).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="➕ New Session", command=self.new_session).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🔄 Refresh", command=self.refresh_tree).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🗑️ Delete", command=self.delete_selected).pack(side=tk.RIGHT, padx=2)

        # Right panel - Details and assignment
        right_frame = ttk.LabelFrame(main_container, text="Details & Management", padding=10)
        main_container.add(right_frame, weight=1)

        # Details section
        details_frame = ttk.LabelFrame(right_frame, text="Selection Details", padding=5)
        details_frame.pack(fill=tk.X, pady=(0, 10))

        self.details_text = tk.Text(details_frame, height=6, wrap=tk.WORD, state=tk.DISABLED)
        details_scroll = ttk.Scrollbar(details_frame, orient=tk.VERTICAL, command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=details_scroll.set)
        self.details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        details_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Assignment section
        assign_frame = ttk.LabelFrame(right_frame, text="Agent Assignment", padding=5)
        assign_frame.pack(fill=tk.BOTH, expand=True)

        # Assignment controls
        assign_controls = ttk.Frame(assign_frame)
        assign_controls.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(assign_controls, text="Assign agents to session:").pack(side=tk.LEFT)
        self.assign_session_var = tk.StringVar()
        self.assign_session_combo = ttk.Combobox(
            assign_controls,
            textvariable=self.assign_session_var,
            width=25,
            state="readonly"
        )
        self.assign_session_combo.pack(side=tk.LEFT, padx=(5, 10))

        ttk.Button(assign_controls, text="Assign Selected", command=self.assign_agents).pack(side=tk.LEFT, padx=2)
        ttk.Button(assign_controls, text="Unassign", command=self.unassign_agents).pack(side=tk.LEFT, padx=2)

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

        # Load initial data
        self.refresh_tree()
        self.refresh_agents()
        self.refresh_session_combo()

        return self.frame

    def load_tree_children(self, parent_item):
        """Load children for tree item on demand (lazy loading)"""
        # This is a placeholder for future lazy loading functionality
        pass

    def refresh_tree(self):
        """Load and display project data with sessions and agents in tree structure"""
        try:
            # Get all data
            projects = self.get_projects()
            sessions = self.get_sessions()
            agents = self.get_agents()

            # Clear existing items
            self.project_tree.delete(*self.project_tree.get_children())

            # Group sessions by project
            project_sessions = {}
            for session_id, session in sessions.items():
                project_id = session['project_id']
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

            # Add projects with their sessions and agents
            for project_id, project in projects.items():
                project_node = self.project_tree.insert('', tk.END, text=f"📁 {project['name']}",
                                                       values=('project', project_id))

                # Add sessions for this project
                project_session_list = project_sessions.get(project_id, [])
                for session in project_session_list:
                    session_agent_list = session_agents.get(session['id'], [])
                    agent_count = len(session_agent_list)

                    session_text = f"🔧 {session['name']} ({agent_count} agents)"
                    session_node = self.project_tree.insert(project_node, tk.END, text=session_text,
                                                           values=('session', session['id']))

                    # Add agents for this session
                    for agent in session_agent_list:
                        status_icon = "🟢" if agent.get('status') == 'connected' else "🔴"
                        agent_text = f"{status_icon} {agent.get('name', agent.get('assigned_agent_id', 'Unknown'))}"
                        self.project_tree.insert(session_node, tk.END, text=agent_text,
                                               values=('agent', agent.get('assigned_agent_id')))

            # Expand all project nodes to show sessions
            for item in self.project_tree.get_children():
                self.project_tree.item(item, open=True)

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
            rows = self.db_manager.execute_query('''
                SELECT assigned_agent_id, name, session_id, team_id, is_active
                FROM agents
                WHERE is_active = 1
                ORDER BY assigned_agent_id
            ''')
            agents = {}
            for row in rows:
                agents[row[0]] = {
                    'assigned_agent_id': row[0],
                    'name': row[1],
                    'session_id': row[2],
                    'team_id': row[3],
                    'status': 'connected' if row[4] else 'disconnected'
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
            return

        item = self.project_tree.item(selection[0])
        item_text = item['text']
        values = item.get('values', [])

        if len(values) >= 2:
            item_type, item_id = values[0], values[1]
        else:
            item_type, item_id = 'unknown', 'unknown'

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
                    self.details_text.insert(1.0, f"Project: {name}\n")
                    self.details_text.insert(tk.END, f"ID: {item_id}\n")
                    self.details_text.insert(tk.END, f"Description: {description or 'None'}\n")
                    self.details_text.insert(tk.END, f"Created: {created_at or 'Unknown'}\n")
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
                    self.details_text.insert(1.0, f"Session: {name}\n")
                    self.details_text.insert(tk.END, f"ID: {item_id}\n")
                    self.details_text.insert(tk.END, f"Project: {project_name or 'Unknown'}\n")
                    self.details_text.insert(tk.END, f"Created: {created_at or 'Unknown'}\n")
            except Exception as e:
                self.details_text.insert(1.0, f"Error loading session details: {e}")

        elif item_type == 'agent':
            try:
                agent_details = self.db_manager.execute_query(
                    '''SELECT name, team_id, read_permission, is_active
                       FROM agents
                       WHERE assigned_agent_id = ?''', (item_id,)
                )
                if agent_details:
                    name, team_id, read_permission, is_active = agent_details[0]
                    self.details_text.insert(1.0, f"Agent: {name or item_id}\n")
                    self.details_text.insert(tk.END, f"ID: {item_id}\n")
                    self.details_text.insert(tk.END, f"Team: {team_id or 'None'}\n")
                    self.details_text.insert(tk.END, f"Permission: {read_permission or 'self_only'}\n")
                    self.details_text.insert(tk.END, f"Status: {'Active' if is_active else 'Inactive'}\n")
            except Exception as e:
                self.details_text.insert(1.0, f"Error loading agent details: {e}")

        self.details_text.config(state=tk.DISABLED)

    def refresh_agents(self):
        """Refresh agents display for assignment"""
        for item in self.agents_tree.get_children():
            self.agents_tree.delete(item)

        try:
            agents = self.db_manager.execute_query('''
                SELECT a.assigned_agent_id, a.name, s.name as session_name, a.team_id
                FROM agents a
                LEFT JOIN sessions s ON a.session_id = s.id
                WHERE a.is_active = 1
                ORDER BY a.assigned_agent_id
            ''')

            for agent in agents:
                agent_id, name, session_name, team_id = agent
                self.agents_tree.insert(
                    '',
                    'end',
                    text=agent_id,
                    values=(name or agent_id, session_name or 'Unassigned', team_id or 'None')
                )

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load agents: {e}")

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
        """Create a new project"""
        name = tk.simpledialog.askstring("New Project", "Enter project name:")
        if not name:
            return

        description = tk.simpledialog.askstring("New Project", "Enter project description (optional):")

        try:
            self.db_manager.execute_update(
                "INSERT INTO projects (name, description) VALUES (?, ?)",
                (name.strip(), description.strip() if description else '')
            )
            self.refresh_tree()  # Auto-refresh
            messagebox.showinfo("Success", f"Project '{name}' created successfully")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to create project: {e}")

    def new_session(self):
        """Create a new session"""
        # First get available projects
        try:
            projects = self.db_manager.execute_query('SELECT id, name FROM projects ORDER BY name')
            if not projects:
                messagebox.showwarning("Warning", "No projects available. Create a project first.")
                return

            project_options = [f"{project[1]} (ID: {project[0]})" for project in projects]

            # Simple dialog for project selection
            project_name = tk.simpledialog.askstring(
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
            session_name = tk.simpledialog.askstring("New Session", "Enter session name:")
            if not session_name:
                return

            self.db_manager.execute_update(
                "INSERT INTO sessions (project_id, name) VALUES (?, ?)",
                (project_id, session_name.strip())
            )
            self.refresh_tree()  # Auto-refresh
            messagebox.showinfo("Success", f"Session '{session_name}' created successfully")

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
                    self.db_manager.execute_update("DELETE FROM projects WHERE id = ?", (item_id,))
                    self.refresh_tree()  # Auto-refresh
                    messagebox.showinfo("Success", f"Project deleted")
                except Exception as e:
                    messagebox.showerror("Database Error", f"Failed to delete project: {e}")

        elif item_type == 'session':
            if messagebox.askyesno("Confirm Delete", f"Delete session '{item_text}'?"):
                try:
                    self.db_manager.execute_update("DELETE FROM sessions WHERE id = ?", (item_id,))
                    self.refresh_tree()  # Auto-refresh
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

            for agent_id in agent_ids:
                self.db_manager.execute_update(
                    "UPDATE agents SET session_id = ? WHERE assigned_agent_id = ?",
                    (session_id, agent_id)
                )

            self.refresh_tree()  # Auto-refresh
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
                self.db_manager.execute_update(
                    "UPDATE agents SET session_id = NULL WHERE assigned_agent_id = ?",
                    (agent_id,)
                )

            self.refresh_tree()  # Auto-refresh
            messagebox.showinfo("Success", f"Unassigned {len(agent_ids)} agents")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to unassign agents: {e}")


class DataFormatInstructionsTab:
    """Updated data format instructions tab with new JSON formats"""

    def __init__(self, parent):
        self.parent = parent
        self.frame = ttk.LabelFrame(parent, text="📋 MCP Server Data Format Instructions", padding=10)

    def create_widgets(self):
        """Create instruction widgets with updated formats"""
        # Title
        title_label = ttk.Label(
            self.frame,
            text="Multi-Agent MCP Context Manager - Communication Format (Updated)",
            font=("Arial", 12, "bold")
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
   - self_only: Returns only contexts created by the requesting agent
   - team_level: Returns contexts from agents in the same team
   - session_level: Returns all contexts in the current session

Permission Levels:
- self_only: Maximum security, agent isolation
- team_level: Team collaboration
- session_level: Full session access

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

class ComprehensiveEnhancedGUI:
    """Main GUI class that combines all tabs"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Multi-Agent MCP Context Manager - Comprehensive Management")
        self.root.geometry("1400x900")

        self.db_manager = DatabaseManager()

        # Create main notebook
        self.main_notebook = ttk.Notebook(self.root)
        self.main_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create all tabs
        self.create_all_tabs()

    def create_all_tabs(self):
        """Create all management tabs"""
        # Data Format Instructions Tab
        instructions_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(instructions_frame, text="📋 Data Format Instructions")

        instructions_widget = DataFormatInstructionsTab(instructions_frame)
        instructions_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

        # Connection Management Tab
        connection_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(connection_frame, text="🔗 Connections")

        connection_widget = ConnectionManagementTab(connection_frame, self.db_manager)
        connection_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

        # Agent Management Tab
        agent_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(agent_frame, text="👥 Agent Management")

        agent_widget = AgentManagementTab(agent_frame, self.db_manager)
        agent_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

        # Project & Session Management Tab
        project_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(project_frame, text="📁 Projects & Sessions")

        project_widget = ProjectSessionTab(project_frame, self.db_manager)
        project_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

        # Original Connection Assignment Tab (from enhanced_gui_module.py)
        from archive.enhanced_gui_module import ConnectionAssignmentWidget

        connection_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(connection_frame, text="🔗 Connection Assignment")

        connection_widget = ConnectionAssignmentWidget(connection_frame)
        connection_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

    def run(self):
        """Start the GUI"""
        self.root.mainloop()

def main():
    """Main entry point"""
    app = ComprehensiveEnhancedGUI()
    app.run()

if __name__ == "__main__":
    main()