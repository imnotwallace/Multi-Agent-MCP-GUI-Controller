#!/usr/bin/env python3
"""
Refactored Multi-Agent MCP Context Manager
Separated into Model-View-Controller architecture
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MCPDataModel:
    """Data access layer for MCP Context Manager"""
    def __init__(self, db_path: str = "multi-agent_mcp_context_manager.db"):
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA foreign_keys = ON')
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_database(self):
        """Initialize hierarchical database structure"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            def column_exists(table: str, column: str) -> bool:
                cursor.execute("PRAGMA table_info('%s')" % table)
                return any(r[1] == column for r in cursor.fetchall())

            # Create tables
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                deleted_at TIMESTAMP
            )''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                project_id TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                deleted_at TIMESTAMP,
                UNIQUE(project_id, name),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                session_id TEXT,
                status TEXT DEFAULT 'disconnected',
                last_active TIMESTAMP,
                team_id TEXT,
                access_level TEXT,
                deleted_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
            )''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS contexts (
                id TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                project_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                agent_id TEXT,
                sequence_number INTEGER,
                metadata TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                deleted_at TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL
            )''')

            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_session ON agents(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_contexts_agent_recent ON contexts(agent_id, created_at DESC)')

            conn.commit()

    def create_project(self, name: str, description: str = "") -> str:
        """Create new project"""
        project_id = f"proj_{name.lower().replace(' ', '_').replace('-', '_')}"
        now = datetime.now().isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                          (project_id, name, description, now, now))
            conn.commit()
            logger.info(f"Created project: {name}")
            return project_id

    def create_session(self, name: str, project_id: str, description: str = "") -> str:
        """Create new session"""
        session_id = f"sess_{project_id}_{name.lower().replace(' ', '_').replace('-', '_')}"
        now = datetime.now().isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO sessions (id, name, project_id, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                          (session_id, name, project_id, description, now, now))
            conn.commit()
            logger.info(f"Created session: {name} in project: {project_id}")
            return session_id

    def create_agent(self, name: str) -> str:
        """Create new agent"""
        agent_id = f"agent_{name.lower().replace(' ', '_').replace('-', '_')}"
        now = datetime.now().isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO agents (id, name, status, last_active) VALUES (?, ?, ?, ?)',
                          (agent_id, name, 'disconnected', now))
            conn.commit()
            logger.info(f"Created agent: {name}")
            return agent_id

    def get_projects(self) -> Dict:
        """Get all active projects"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM projects WHERE deleted_at IS NULL ORDER BY name')
            projects = {}
            for row in cursor.fetchall():
                projects[row[0]] = {
                    'id': row[0], 'name': row[1], 'description': row[2],
                    'created_at': row[3], 'updated_at': row[4], 'sessions': {}
                }
            return projects

    def get_sessions(self) -> Dict:
        """Get all active sessions"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM sessions WHERE deleted_at IS NULL ORDER BY project_id, name')
            sessions = {}
            for row in cursor.fetchall():
                sessions[row[0]] = {
                    'id': row[0], 'name': row[1], 'project_id': row[2],
                    'description': row[3], 'created_at': row[4], 'updated_at': row[5], 'agents': []
                }
            return sessions

    def get_agents(self) -> Dict:
        """Get all active agents"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM agents WHERE deleted_at IS NULL')
            agents = {}
            for row in cursor.fetchall():
                agents[row[0]] = {
                    'id': row[0], 'name': row[1], 'session_id': row[2],
                    'status': row[3], 'last_active': row[4]
                }
            return agents

    def soft_delete_item(self, table: str, item_id: str):
        """Soft delete an item and its dependencies"""
        now = datetime.now().isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()

            if table == 'projects':
                cursor.execute('UPDATE projects SET deleted_at = ? WHERE id = ?', (now, item_id))
                cursor.execute('UPDATE sessions SET deleted_at = ? WHERE project_id = ?', (now, item_id))
                cursor.execute('UPDATE contexts SET deleted_at = ? WHERE project_id = ?', (now, item_id))
            elif table == 'sessions':
                cursor.execute('UPDATE sessions SET deleted_at = ? WHERE id = ?', (now, item_id))
                cursor.execute('UPDATE contexts SET deleted_at = ? WHERE session_id = ?', (now, item_id))
            elif table == 'agents':
                cursor.execute('UPDATE agents SET deleted_at = ? WHERE id = ?', (now, item_id))
                cursor.execute('UPDATE contexts SET deleted_at = ? WHERE agent_id = ?', (now, item_id))

            conn.commit()
            logger.info(f"Soft deleted {table}: {item_id}")

class MCPValidator:
    """Input validation utilities"""

    @staticmethod
    def validate_name(name: str, max_length: int = 50) -> tuple[bool, str]:
        """Validate name input"""
        if not name or not name.strip():
            return False, "Name cannot be empty"

        name = name.strip()
        if len(name) > max_length:
            return False, f"Name too long (max {max_length} chars)"

        if not re.match(r'^[a-zA-Z0-9_\-\s]+$', name):
            return False, "Name contains invalid characters"

        return True, name

class MCPController:
    """Business logic controller"""
    def __init__(self, model: MCPDataModel):
        self.model = model

    def create_project(self, name: str, description: str = "") -> tuple[bool, str]:
        """Create project with validation"""
        try:
            valid, validated_name = MCPValidator.validate_name(name)
            if not valid:
                return False, validated_name

            project_id = self.model.create_project(validated_name, description)
            return True, f"Project '{validated_name}' created successfully"
        except sqlite3.IntegrityError:
            return False, "Project name already exists"
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            return False, f"Failed to create project: {e}"

    def create_session(self, name: str, project_id: str, description: str = "") -> tuple[bool, str]:
        """Create session with validation"""
        try:
            valid, validated_name = MCPValidator.validate_name(name)
            if not valid:
                return False, validated_name

            session_id = self.model.create_session(validated_name, project_id, description)
            return True, f"Session '{validated_name}' created successfully"
        except sqlite3.IntegrityError:
            return False, "Session name already exists in this project"
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return False, f"Failed to create session: {e}"

    def create_agent(self, name: str) -> tuple[bool, str]:
        """Create agent with validation"""
        try:
            valid, validated_name = MCPValidator.validate_name(name)
            if not valid:
                return False, validated_name

            agent_id = self.model.create_agent(validated_name)
            return True, f"Agent '{validated_name}' created successfully"
        except sqlite3.IntegrityError:
            return False, "Agent name already exists"
        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            return False, f"Failed to create agent: {e}"

class MCPView:
    """GUI View layer"""
    def __init__(self, controller: MCPController, model: MCPDataModel):
        self.controller = controller
        self.model = model

        self.root = tk.Tk()
        self.root.title("Multi-Agent MCP Context Manager")
        self.root.geometry("1000x700")

        # Data caches
        self.projects = {}
        self.sessions = {}
        self.agents = {}

        self.setup_ui()
        self.refresh_all_data()

    def setup_ui(self):
        """Setup the user interface"""
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.setup_project_view(notebook)
        self.setup_agent_view(notebook)
        self.setup_data_view(notebook)

    def setup_project_view(self, notebook):
        """Project hierarchy view"""
        project_frame = ttk.Frame(notebook)
        notebook.add(project_frame, text="Project View")

        # Left panel - Projects
        left_frame = ttk.LabelFrame(project_frame, text="Projects", padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5, pady=5)

        self.project_tree = ttk.Treeview(left_frame, height=15)
        self.project_tree.heading('#0', text='Project Structure')
        self.project_tree.column('#0', width=300)
        self.project_tree.pack(fill=tk.BOTH, expand=True)
        self.project_tree.bind('<<TreeviewSelect>>', self.on_project_tree_select)

        # Project buttons
        project_btn_frame = ttk.Frame(left_frame)
        project_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(project_btn_frame, text="New Project", command=self.new_project).pack(side=tk.LEFT, padx=2)
        ttk.Button(project_btn_frame, text="New Session", command=self.new_session).pack(side=tk.LEFT, padx=2)
        ttk.Button(project_btn_frame, text="Delete", command=self.delete_selected).pack(side=tk.LEFT, padx=2)

        # Right panel - Details
        right_frame = ttk.LabelFrame(project_frame, text="Details", padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.selection_label = ttk.Label(right_frame, text="Select item from project tree", font=('TkDefaultFont', 10, 'bold'))
        self.selection_label.pack(anchor=tk.W, pady=5)

        self.details_text = tk.Text(right_frame, height=10, wrap=tk.WORD)
        self.details_text.pack(fill=tk.BOTH, expand=True, pady=5)

    def setup_agent_view(self, notebook):
        """Agent-centric view"""
        agent_frame = ttk.Frame(notebook)
        notebook.add(agent_frame, text="Agent View")

        # Agent management
        mgmt_frame = ttk.LabelFrame(agent_frame, text="Agent Management", padding="10")
        mgmt_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(mgmt_frame, text="Agent Name:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.new_agent_name = ttk.Entry(mgmt_frame, width=20)
        self.new_agent_name.grid(row=0, column=1, padx=5)
        ttk.Button(mgmt_frame, text="Add Agent", command=self.add_agent).grid(row=0, column=2, padx=5)

        # Agent status table
        status_frame = ttk.LabelFrame(agent_frame, text="Agent Status", padding="10")
        status_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.agent_status_tree = ttk.Treeview(status_frame, columns=('name', 'project', 'session', 'status', 'last_active'), height=20)
        self.agent_status_tree.heading('#0', text='Agent ID')
        self.agent_status_tree.heading('name', text='Name')
        self.agent_status_tree.heading('project', text='Project')
        self.agent_status_tree.heading('session', text='Session')
        self.agent_status_tree.heading('status', text='Status')
        self.agent_status_tree.heading('last_active', text='Last Active')

        for col in ('name', 'project', 'session', 'status', 'last_active'):
            self.agent_status_tree.column(col, width=120)

        self.agent_status_tree.pack(fill=tk.BOTH, expand=True)

    def setup_data_view(self, notebook):
        """Context data view"""
        data_frame = ttk.Frame(notebook)
        notebook.add(data_frame, text="Data View")

        # Basic placeholder
        ttk.Label(data_frame, text="Data View - Context management coming soon").pack(pady=20)

    def refresh_all_data(self):
        """Refresh all data displays"""
        try:
            self.load_data()
            self.refresh_project_tree()
            self.refresh_agent_status()
        except Exception as e:
            logger.error(f"Failed to refresh data: {e}")
            messagebox.showerror("Error", f"Failed to refresh data: {e}")

    def load_data(self):
        """Load data from model"""
        self.projects = self.model.get_projects()
        self.sessions = self.model.get_sessions()
        self.agents = self.model.get_agents()

        # Link sessions to projects
        for session_id, session in self.sessions.items():
            project_id = session['project_id']
            if project_id in self.projects:
                self.projects[project_id]['sessions'][session_id] = session

        # Link agents to sessions
        for agent_id, agent in self.agents.items():
            session_id = agent['session_id']
            if session_id and session_id in self.sessions:
                self.sessions[session_id]['agents'].append(agent)

    def refresh_project_tree(self):
        """Refresh project hierarchy tree"""
        self.project_tree.delete(*self.project_tree.get_children())

        for project_id, project in self.projects.items():
            project_node = self.project_tree.insert('', tk.END, text=f"📁 {project['name']}",
                                                   values=('project', project_id))

            for session_id, session in project['sessions'].items():
                agent_count = len(session['agents'])
                session_text = f"🔧 {session['name']} ({agent_count} agents)"
                session_node = self.project_tree.insert(project_node, tk.END, text=session_text,
                                                       values=('session', session_id))

                for agent in session['agents']:
                    status_icon = "🟢" if agent['status'] == 'connected' else "🔴"
                    agent_text = f"{status_icon} {agent['name']}"
                    self.project_tree.insert(session_node, tk.END, text=agent_text,
                                           values=('agent', agent['id']))

        # Expand all nodes
        for item in self.project_tree.get_children():
            self.project_tree.item(item, open=True)
            for child in self.project_tree.get_children(item):
                self.project_tree.item(child, open=True)

    def refresh_agent_status(self):
        """Refresh agent status table"""
        for item in self.agent_status_tree.get_children():
            self.agent_status_tree.delete(item)

        for agent_id, agent in self.agents.items():
            project_name = ""
            session_name = ""

            if agent['session_id'] and agent['session_id'] in self.sessions:
                session = self.sessions[agent['session_id']]
                session_name = session['name']
                if session['project_id'] in self.projects:
                    project_name = self.projects[session['project_id']]['name']

            self.agent_status_tree.insert('', tk.END, text=agent_id,
                                         values=(agent['name'], project_name, session_name,
                                               agent['status'], agent['last_active'] or 'Never'))

    def on_project_tree_select(self, event):
        """Handle project tree selection"""
        selection = self.project_tree.selection()
        if not selection:
            return

        item = self.project_tree.item(selection[0])
        if not item.get('values'):
            return

        item_type, item_id = item['values']

        if item_type == 'project':
            project = self.projects[item_id]
            self.selection_label.config(text=f"Project: {project['name']}")
            details = f"Description: {project['description'] or 'None'}\n"
            details += f"Sessions: {len(project['sessions'])}\n"
            details += f"Created: {project['created_at']}"
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, details)

    def new_project(self):
        """Create new project"""
        name = simpledialog.askstring("New Project", "Project name:")
        if not name:
            return

        description = simpledialog.askstring("New Project", "Description (optional):") or ""

        success, message = self.controller.create_project(name, description)
        if success:
            self.refresh_all_data()
            messagebox.showinfo("Success", message)
        else:
            messagebox.showerror("Error", message)

    def new_session(self):
        """Create new session for selected project"""
        selection = self.project_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Select a project first")
            return

        item = self.project_tree.item(selection[0])
        if not item.get('values') or item['values'][0] != 'project':
            messagebox.showwarning("Warning", "Select a project, not a session")
            return

        project_id = item['values'][1]
        project_name = self.projects[project_id]['name']

        name = simpledialog.askstring("New Session", f"Session name for project '{project_name}':")
        if not name:
            return

        description = simpledialog.askstring("New Session", "Description (optional):") or ""

        success, message = self.controller.create_session(name, project_id, description)
        if success:
            self.refresh_all_data()
            messagebox.showinfo("Success", message)
        else:
            messagebox.showerror("Error", message)

    def add_agent(self):
        """Add new agent"""
        name = self.new_agent_name.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Enter agent name")
            return

        success, message = self.controller.create_agent(name)
        if success:
            self.new_agent_name.delete(0, tk.END)
            self.refresh_all_data()
            messagebox.showinfo("Success", message)
        else:
            messagebox.showerror("Error", message)

    def delete_selected(self):
        """Delete the currently selected item"""
        selection = self.project_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Select an item to delete")
            return

        item = self.project_tree.item(selection[0])
        if not item.get('values'):
            return

        item_type, item_id = item['values']

        if not messagebox.askyesno("Confirm Delete", f"Delete selected {item_type}? This will be a soft-delete (recoverable). Continue?"):
            return

        try:
            self.model.soft_delete_item(item_type + 's', item_id)  # pluralize table name
            self.refresh_all_data()
            messagebox.showinfo("Success", f"{item_type.title()} deleted successfully")
        except Exception as e:
            logger.error(f"Failed to delete {item_type}: {e}")
            messagebox.showerror("Error", f"Failed to delete: {e}")

    def run(self):
        """Start the GUI application"""
        try:
            self.root.mainloop()
        except Exception as e:
            logger.error(f"Application error: {e}")
            messagebox.showerror("Error", f"Application error: {e}")

def main():
    """Main application entry point"""
    try:
        model = MCPDataModel()
        controller = MCPController(model)
        view = MCPView(controller, model)
        view.run()
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        messagebox.showerror("Error", f"Failed to start application: {e}")

if __name__ == "__main__":
    main()