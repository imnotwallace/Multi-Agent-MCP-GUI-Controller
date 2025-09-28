#!/usr/bin/env python3
"""
Agent Management Tab Module
Extracted from redesigned_comprehensive_gui.py
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import csv
import os


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
            item_text = self.teams_tree.item(selection[0])['text']
            # Extract team_id from text like "📁 Team Name (team_id)"
            team_id = item_text.split('(')[-1].rstrip(')')

            if messagebox.askyesno("Confirm Deletion", f"Delete team '{team_id}'?"):
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

        try:
            item_text = self.teams_tree.item(selection[0])['text']
            # Extract team_id from text like "📁 Team Name (team_id)"
            team_id = item_text.split('(')[-1].rstrip(')')
            new_name = simpledialog.askstring("Rename Team", f"Enter new name for team {team_id}:")

            if new_name:
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