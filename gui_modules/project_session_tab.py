#!/usr/bin/env python3
"""
Project Session Tab Module
Extracted from redesigned_comprehensive_gui.py
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3


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

        # Control buttons - Two rows
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        # First row: New Project, New Session, Rename
        btn_row1 = ttk.Frame(btn_frame)
        btn_row1.pack(fill=tk.X, pady=(0, 2))

        ttk.Button(btn_row1, text="➕ New Project", command=self.new_project).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row1, text="➕ New Session", command=self.new_session).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row1, text="✏️ Rename", command=self.rename_selected).pack(side=tk.LEFT, padx=2)

        # Second row: Refresh, Delete
        btn_row2 = ttk.Frame(btn_frame)
        btn_row2.pack(fill=tk.X)

        ttk.Button(btn_row2, text="🔄 Refresh", command=self.refresh_tree).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row2, text="🗑️ Delete", command=self.delete_selected).pack(side=tk.LEFT, padx=2)

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