#!/usr/bin/env python3
"""
Hierarchical MCP Context Manager
Projects -> Sessions -> Agents
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

class MultiAgentMCPManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Multi-Agent MCP Context Manager")
        self.root.geometry("1000x700")
        
        self.db_path = "multi-agent_mcp_context_manager.db"
        self.init_database()
        
        # Data structures
        self.projects = {}
        self.sessions = {}
        self.agents = {}
        
        self.setup_ui()
        self.refresh_all_data()
    
    def init_database(self):
        """Initialize hierarchical database structure"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

        # Enable foreign keys
        cursor.execute('PRAGMA foreign_keys = ON')

        # Helper to check for column existence
        def column_exists(table: str, column: str) -> bool:
            cursor.execute("PRAGMA table_info('%s')" % table)
            return any(r[1] == column for r in cursor.fetchall())

        # Projects table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )''')

        # Sessions table (belongs to project)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            project_id TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            UNIQUE(project_id, name),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )''')

        # Agents table (connected to session). Include team/access columns in schema;
        # if the table already exists without these columns we'll ALTER below.
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            session_id TEXT,
            status TEXT DEFAULT 'disconnected',
            last_active TIMESTAMP,
            team_id TEXT,
            access_level TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
        )''')

        # Teams table (used by create_team)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            session_id TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )''')

        # Contexts table (agent-specific streams)
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
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL
        )''')

        # Sequence counters (atomic increments)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS context_sequences (
            session_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            sequence INTEGER DEFAULT 0,
            PRIMARY KEY (session_id, agent_id),
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
        )''')

        # Add missing columns safely (only if they don't already exist)
        try:
            if not column_exists('sessions', 'deleted_at'):
                cursor.execute('ALTER TABLE sessions ADD COLUMN deleted_at TIMESTAMP')
        except Exception:
            # If ALTER fails for any reason, ignore and continue - table may be in older schema
            pass

        # Ensure agents table has team_id and access_level columns (for backward compatibility)
        try:
            if not column_exists('agents', 'team_id'):
                cursor.execute("ALTER TABLE agents ADD COLUMN team_id TEXT")
            if not column_exists('agents', 'access_level'):
                cursor.execute("ALTER TABLE agents ADD COLUMN access_level TEXT")
            # add soft-delete column for agents/projects/contexts
            if not column_exists('agents', 'deleted_at'):
                cursor.execute("ALTER TABLE agents ADD COLUMN deleted_at TIMESTAMP")
            if not column_exists('projects', 'deleted_at'):
                cursor.execute("ALTER TABLE projects ADD COLUMN deleted_at TIMESTAMP")
            if not column_exists('contexts', 'deleted_at'):
                cursor.execute("ALTER TABLE contexts ADD COLUMN deleted_at TIMESTAMP")
        except Exception:
            pass

        # Performance indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_session ON agents(session_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_contexts_agent_recent ON contexts(agent_id, created_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_contexts_session_recent ON contexts(session_id, created_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_contexts_stream ON contexts(session_id, agent_id, sequence_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_contexts_pagination ON contexts(session_id, created_at DESC, id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(deleted_at)')

            conn.commit()
            logger.info(f"Database operation completed")
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def setup_ui(self):
        # Create notebook for different views
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Project View Tab
        self.setup_project_view(notebook)
        
        # Agent View Tab
        self.setup_agent_view(notebook)
        
        # Data View Tab
        self.setup_data_view(notebook)
    
    def setup_project_view(self, notebook):
        """Project hierarchy view: Projects -> Sessions -> Agents"""
        project_frame = ttk.Frame(notebook)
        notebook.add(project_frame, text="Project View")
        
        # Left panel - Projects
        left_frame = ttk.LabelFrame(project_frame, text="Projects", padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5, pady=5)
        
        self.project_tree = ttk.Treeview(left_frame, height=15)
        self.project_tree.heading('#0', text='Project Structure')
        # Set pixel width for the tree's primary column (the tree column '#0')
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
        
        # Selection info
        self.selection_label = ttk.Label(right_frame, text="Select item from project tree", font=('TkDefaultFont', 10, 'bold'))
        self.selection_label.pack(anchor=tk.W, pady=5)
        
        # Details text
        self.details_text = tk.Text(right_frame, height=10, wrap=tk.WORD)
        self.details_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Agent assignment for sessions
        assign_frame = ttk.LabelFrame(right_frame, text="Agent Assignment", padding="5")
        assign_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(assign_frame, text="Available Agents:").grid(row=0, column=0, sticky=tk.W)
        self.available_agents = ttk.Combobox(assign_frame, width=20, state="readonly")
        self.available_agents.grid(row=0, column=1, padx=5)
        
        ttk.Button(assign_frame, text="Assign to Session", command=self.assign_agent).grid(row=0, column=2, padx=5)
        ttk.Button(assign_frame, text="Disconnect", command=self.disconnect_agent).grid(row=0, column=3, padx=5)
    
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
        
        # Filters
        filter_frame = ttk.LabelFrame(data_frame, text="Filters", padding="10")
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(filter_frame, text="Project:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.filter_project = ttk.Combobox(filter_frame, width=15, state="readonly")
        self.filter_project.grid(row=0, column=1, padx=5)
        self.filter_project.bind('<<ComboboxSelected>>', self.on_filter_change)
        
        ttk.Label(filter_frame, text="Session:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.filter_session = ttk.Combobox(filter_frame, width=15, state="readonly")
        self.filter_session.grid(row=0, column=3, padx=5)
        self.filter_session.bind('<<ComboboxSelected>>', self.on_filter_change)
        
        ttk.Button(filter_frame, text="Refresh", command=self.refresh_data_view).grid(row=0, column=4, padx=10)
        
        # Context data
        context_frame = ttk.LabelFrame(data_frame, text="Context Data", padding="10")
        context_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.context_tree = ttk.Treeview(context_frame, columns=('title', 'agent', 'created', 'size'), height=15)
        self.context_tree.heading('#0', text='Context ID')
        self.context_tree.heading('title', text='Title')
        self.context_tree.heading('agent', text='Agent')
        self.context_tree.heading('created', text='Created')
        self.context_tree.heading('size', text='Size')
        self.context_tree.pack(fill=tk.BOTH, expand=True)
        self.context_tree.bind('<<TreeviewSelect>>', self.on_context_select)
        
        # Context preview
        preview_frame = ttk.LabelFrame(data_frame, text="Content Preview", padding="5")
        preview_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.context_preview = tk.Text(preview_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        self.context_preview.pack(fill=tk.X)
    
    def refresh_all_data(self):
        """Refresh all data displays"""
        self.load_projects()
        self.refresh_project_tree()
        self.refresh_agent_status()
        self.refresh_filters()
        self.refresh_data_view()
    
    def load_projects(self):
        """Load projects and sessions from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
        
        # Load projects (excluding soft-deleted)
        cursor.execute('SELECT * FROM projects WHERE deleted_at IS NULL ORDER BY name')
        for row in cursor.fetchall():
            self.projects[row[0]] = {
                'id': row[0], 'name': row[1], 'description': row[2],
                'created_at': row[3], 'updated_at': row[4], 'sessions': {}
            }
        
        # Load sessions (excluding soft-deleted)
        cursor.execute('SELECT * FROM sessions WHERE deleted_at IS NULL ORDER BY project_id, name')
        for row in cursor.fetchall():
            session_data = {
                'id': row[0], 'name': row[1], 'project_id': row[2], 
                'description': row[3], 'created_at': row[4], 'updated_at': row[5], 'agents': []
            }
            self.sessions[row[0]] = session_data
            if row[2] in self.projects:
                self.projects[row[2]]['sessions'][row[0]] = session_data
        
        # Load agents (excluding soft-deleted)
        cursor.execute('SELECT * FROM agents WHERE deleted_at IS NULL')
        for row in cursor.fetchall():
            agent_data = {
                'id': row[0], 'name': row[1], 'session_id': row[2],
                'status': row[3], 'last_active': row[4]
            }
            self.agents[row[0]] = agent_data
            if row[2] and row[2] in self.sessions:
                self.sessions[row[2]]['agents'].append(agent_data)
        
        conn.close()
    
    def refresh_project_tree(self):
        """Refresh project hierarchy tree"""
        self.project_tree.delete(*self.project_tree.get_children())
        
        for project_id, project in self.projects.items():
            # Add project node
            project_node = self.project_tree.insert('', tk.END, text=f"📁 {project['name']}", 
                                                   values=('project', project_id))
            
            # Add session nodes
            for session_id, session in project['sessions'].items():
                agent_count = len(session['agents'])
                session_text = f"🔧 {session['name']} ({agent_count} agents)"
                session_node = self.project_tree.insert(project_node, tk.END, text=session_text,
                                                       values=('session', session_id))
                
                # Add agent nodes
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
    
    def refresh_filters(self):
        """Refresh filter comboboxes"""
        project_names = ['All'] + [p['name'] for p in self.projects.values()]
        self.filter_project['values'] = project_names
        if not self.filter_project.get():
            self.filter_project.set('All')
        
        # Update available agents
        available = [a['name'] for a in self.agents.values() if not a['session_id']]
        self.available_agents['values'] = available
    
    def refresh_data_view(self):
        """Refresh context data view"""
        for item in self.context_tree.get_children():
            self.context_tree.delete(item)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
        
        query = 'SELECT c.*, a.name as agent_name FROM contexts c LEFT JOIN agents a ON c.agent_id = a.id WHERE c.deleted_at IS NULL'
        params = []
        
        if self.filter_project.get() != 'All':
            project_id = next((k for k, v in self.projects.items() if v['name'] == self.filter_project.get()), None)
            if project_id:
                query += ' AND c.project_id = ?'
                params.append(project_id)
        
        if hasattr(self, 'filter_session') and self.filter_session.get():
            session_id = next((k for k, v in self.sessions.items() if v['name'] == self.filter_session.get()), None)
            if session_id:
                query += ' AND c.session_id = ?'
                params.append(session_id)
        
        cursor.execute(query + ' ORDER BY c.updated_at DESC', params)
        
        for row in cursor.fetchall():
            content_size = f"{len(row[2])} chars" if row[2] else "0 chars"
            self.context_tree.insert('', tk.END, text=row[0],
                                   values=(row[1], row[9] or 'Unknown', row[7], content_size))
        
        conn.close()
    
    def on_project_tree_select(self, event):
        """Handle project tree selection"""
        selection = self.project_tree.selection()
        if not selection:
            return
        
        item = self.project_tree.item(selection[0])
        item_type, item_id = item['values']
        
        if item_type == 'project':
            project = self.projects[item_id]
            self.selection_label.config(text=f"Project: {project['name']}")
            details = f"Description: {project['description'] or 'None'}\n"
            details += f"Sessions: {len(project['sessions'])}\n"
            details += f"Created: {project['created_at']}"
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, details)
            
        elif item_type == 'session':
            session = self.sessions[item_id]
            project_name = self.projects[session['project_id']]['name']
            self.selection_label.config(text=f"Session: {session['name']} (Project: {project_name})")
            details = f"Description: {session['description'] or 'None'}\n"
            details += f"Connected Agents: {len(session['agents'])}\n"
            details += f"Created: {session['created_at']}\n\n"
            details += "Agents:\n"
            for agent in session['agents']:
                details += f"- {agent['name']} ({agent['status']})\n"
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, details)
    
    def on_filter_change(self, event):
        """Handle filter changes"""
        if self.filter_project.get() != 'All':
            project_id = next((k for k, v in self.projects.items() if v['name'] == self.filter_project.get()), None)
            if project_id:
                session_names = ['All'] + [s['name'] for s in self.projects[project_id]['sessions'].values()]
                self.filter_session['values'] = session_names
                if not self.filter_session.get():
                    self.filter_session.set('All')
        else:
            self.filter_session['values'] = ['All']
            self.filter_session.set('All')
        
        self.refresh_data_view()
    
    def on_context_select(self, event):
        """Handle context selection for preview"""
        selection = self.context_tree.selection()
        if not selection:
            return
        
        context_id = self.context_tree.item(selection[0])['text']
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
        cursor.execute('SELECT content FROM contexts WHERE id = ? AND deleted_at IS NULL', (context_id,))
        result = cursor.fetchone()
        conn.close()
        
        self.context_preview.config(state=tk.NORMAL)
        self.context_preview.delete(1.0, tk.END)
        if result:
            self.context_preview.insert(1.0, result[0] or 'No content')
        self.context_preview.config(state=tk.DISABLED)
    
    def validate_name(self, name: str, max_length: int = 50) -> tuple[bool, str]:
        """Validate name input"""
        if not name or not name.strip():
            return False, "Name cannot be empty"

        name = name.strip()
        if len(name) > max_length:
            return False, f"Name too long (max {max_length} chars)"

        if not re.match(r'^[a-zA-Z0-9_\-\s]+$', name):
            return False, "Name contains invalid characters"

        return True, name

    def new_project(self):
        """Create new project"""
        name = simpledialog.askstring("New Project", "Project name:")
        if not name:
            return

        valid, result = self.validate_name(name)
        if not valid:
            messagebox.showerror("Invalid Input", result)
            return
        name = result

        description = simpledialog.askstring("New Project", "Description (optional):") or ""

        project_id = f"proj_{name.lower().replace(' ', '_').replace('-', '_')}"
        now = datetime.now().isoformat()

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                          (project_id, name, description, now, now))
            conn.commit()
            self.refresh_all_data()
            messagebox.showinfo("Success", f"Project '{name}' created")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Project name already exists")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create project: {e}")
        finally:
            conn.close()
    
    def new_session(self):
        """Create new session for selected project"""
        selection = self.project_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Select a project first")
            return

        item = self.project_tree.item(selection[0])
        if item['values'][0] != 'project':
            messagebox.showwarning("Warning", "Select a project, not a session")
            return

        project_id = item['values'][1]
        project_name = self.projects[project_id]['name']

        name = simpledialog.askstring("New Session", f"Session name for project '{project_name}':")
        if not name:
            return

        valid, result = self.validate_name(name)
        if not valid:
            messagebox.showerror("Invalid Input", result)
            return
        name = result

        description = simpledialog.askstring("New Session", "Description (optional):") or ""

        session_id = f"sess_{project_id}_{name.lower().replace(' ', '_').replace('-', '_')}"
        now = datetime.now().isoformat()

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO sessions (id, name, project_id, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                          (session_id, name, project_id, description, now, now))
            conn.commit()
            self.refresh_all_data()
            messagebox.showinfo("Success", f"Session '{name}' created in project '{project_name}'")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Session name already exists in this project")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create session: {e}")
        finally:
            conn.close()

    def add_agent(self):
        """Add new agent"""
        name = self.new_agent_name.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Enter agent name")
            return

        valid, result = self.validate_name(name)
        if not valid:
            messagebox.showerror("Invalid Input", result)
            return
        name = result

        agent_id = f"agent_{name.lower().replace(' ', '_').replace('-', '_')}"
        now = datetime.now().isoformat()

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO agents (id, name, status, last_active) VALUES (?, ?, ?, ?)',
                          (agent_id, name, 'disconnected', now))
            conn.commit()
            self.new_agent_name.delete(0, tk.END)
            self.refresh_all_data()
            messagebox.showinfo("Success", f"Agent '{name}' added")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Agent name already exists")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add agent: {e}")
        finally:
            conn.close()
    
    def assign_agent(self):
        """Assign selected agent to selected session"""
        selection = self.project_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Select a session")
            return
        
        item = self.project_tree.item(selection[0])
        if item['values'][0] != 'session':
            messagebox.showwarning("Warning", "Select a session")
            return
        
        session_id = item['values'][1]
        agent_name = self.available_agents.get()
        if not agent_name:
            messagebox.showwarning("Warning", "Select an agent")
            return
        
        agent_id = next((k for k, v in self.agents.items() if v['name'] == agent_name), None)
        if not agent_id:
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
        cursor.execute('UPDATE agents SET session_id = ?, status = ? WHERE id = ?',
                      (session_id, 'connected', agent_id))
            conn.commit()
            logger.info(f"Database operation completed")
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
        
        self.refresh_all_data()
        messagebox.showinfo("Success", f"Agent '{agent_name}' assigned to session")
    
    def disconnect_agent(self):
        """Disconnect selected agent"""
        selection = self.agent_status_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Select an agent")
            return
        
        agent_id = self.agent_status_tree.item(selection[0])['text']
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
        cursor.execute('UPDATE agents SET session_id = NULL, status = ? WHERE id = ?',
                      ('disconnected', agent_id))
            conn.commit()
            logger.info(f"Database operation completed")
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
        
        self.refresh_all_data()
        messagebox.showinfo("Success", "Agent disconnected")
    
    def get_agent_accessible_contexts(self, agent_id: str, limit: int = 50) -> List[Dict]:
        """Get contexts based on agent's access level"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
        
        # Get agent's access level and team
        cursor.execute('SELECT access_level, team_id, session_id FROM agents WHERE id = ? AND deleted_at IS NULL', (agent_id,))
        agent_info = cursor.fetchone()
        if not agent_info:
            conn.close()
            return []
        
        access_level, team_id, session_id = agent_info
        
        if access_level == 'own_only':
            # Only own stream
            query = '''
            SELECT c.*, a.name as agent_name FROM contexts c 
            LEFT JOIN agents a ON c.agent_id = a.id
            WHERE c.agent_id = ? ORDER BY c.created_at DESC LIMIT ?
            '''
            cursor.execute(query, (agent_id, limit))
            
        elif access_level == 'team_only' and team_id:
            # Team members' streams
            query = '''
            SELECT c.*, a.name as agent_name FROM contexts c 
            LEFT JOIN agents a ON c.agent_id = a.id
            WHERE c.agent_id IN (SELECT id FROM agents WHERE team_id = ?)
            ORDER BY c.created_at DESC LIMIT ?
            '''
            cursor.execute(query, (team_id, limit))
            
        elif access_level == 'session_wide' and session_id:
            # All streams in session
            query = '''
            SELECT c.*, a.name as agent_name FROM contexts c 
            LEFT JOIN agents a ON c.agent_id = a.id
            WHERE c.session_id = ? ORDER BY c.created_at DESC LIMIT ?
            '''
            cursor.execute(query, (session_id, limit))
            
        else:
            # Fallback to own only
            query = '''
            SELECT c.*, a.name as agent_name FROM contexts c 
            LEFT JOIN agents a ON c.agent_id = a.id
            WHERE c.agent_id = ? ORDER BY c.created_at DESC LIMIT ?
            '''
            cursor.execute(query, (agent_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        return [{
            'id': r[0], 'title': r[1], 'content': r[2],
            'project_id': r[3], 'session_id': r[4], 'agent_id': r[5],
            'sequence_number': r[6], 'metadata': json.loads(r[7] or '{}'),
            'created_at': r[8], 'updated_at': r[9], 'agent_name': r[10]
        } for r in results]
    
    def create_team(self, name: str, session_id: str, description: str = None) -> str:
        """Create new team within session"""
        team_id = f"team_{session_id}_{name.lower().replace(' ', '_')}"
        now = datetime.now().isoformat()
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
        cursor.execute('INSERT INTO teams (id, name, session_id, description, created_at) VALUES (?, ?, ?, ?, ?)',
                      (team_id, name, session_id, description, now))
            conn.commit()
            logger.info(f"Database operation completed")
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
        return team_id
    
    def assign_agent_to_team(self, agent_id: str, team_id: str, access_level: str = 'team_only'):
        """Assign agent to team with access level"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
        cursor.execute('UPDATE agents SET team_id = ?, access_level = ? WHERE id = ?',
                      (team_id, access_level, agent_id))
            conn.commit()
            logger.info(f"Database operation completed")
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def set_agent_access_level(self, agent_id: str, access_level: str):
        """Update agent access level"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
        cursor.execute('UPDATE agents SET access_level = ? WHERE id = ?',
                      (access_level, agent_id))
            conn.commit()
            logger.info(f"Database operation completed")
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def delete_selected(self):
        """Soft-delete the currently selected project, session, or agent from the UI and DB by setting deleted_at timestamps.

        This will mark related sessions and contexts as deleted as well so they no longer appear in the UI.
        """
        now = datetime.now().isoformat()

        # Prefer selection from project tree
        selection = self.project_tree.selection()
        if selection:
            item = self.project_tree.item(selection[0])
            item_type, item_id = item.get('values', (None, None))
            if not item_type:
                messagebox.showwarning("Warning", "Select an item to delete")
                return

            if not messagebox.askyesno("Confirm Delete", f"Delete selected {item_type}? This will be a soft-delete (recoverable). Continue?"):
                return

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                if item_type == 'project':
                    # Soft-delete project and cascade to sessions and contexts
                    cursor.execute('UPDATE projects SET deleted_at = ? WHERE id = ?', (now, item_id))
                    cursor.execute('UPDATE sessions SET deleted_at = ? WHERE project_id = ?', (now, item_id))
                    cursor.execute('UPDATE contexts SET deleted_at = ? WHERE project_id = ?', (now, item_id))
                elif item_type == 'session':
                    cursor.execute('UPDATE sessions SET deleted_at = ? WHERE id = ?', (now, item_id))
                    cursor.execute('UPDATE contexts SET deleted_at = ? WHERE session_id = ?', (now, item_id))
                elif item_type == 'agent':
                    cursor.execute('UPDATE agents SET deleted_at = ? WHERE id = ?', (now, item_id))
                    cursor.execute('UPDATE contexts SET deleted_at = ? WHERE agent_id = ?', (now, item_id))
                conn.commit()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to soft-delete: {e}")
            finally:
                conn.close()

            self.refresh_all_data()
            return

        # Otherwise try agent status selection
        selection = self.agent_status_tree.selection()
        if selection:
            agent_id = self.agent_status_tree.item(selection[0])['text']
            if not messagebox.askyesno("Confirm Delete", f"Delete agent '{agent_id}'? This will be a soft-delete (recoverable). Continue?"):
                return
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                cursor.execute('UPDATE agents SET deleted_at = ? WHERE id = ?', (now, agent_id))
                cursor.execute('UPDATE contexts SET deleted_at = ? WHERE agent_id = ?', (now, agent_id))
                conn.commit()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to soft-delete agent: {e}")
            finally:
                conn.close()

            self.refresh_all_data()
            return

        messagebox.showwarning("Warning", "Select a project, session, or agent to delete")
