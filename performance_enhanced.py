#!/usr/bin/env python3
"""
Performance-Enhanced Multi-Agent MCP Context Manager
Includes caching, connection pooling, and background operations
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import json
import re
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import contextmanager
from functools import wraps
from cachetools import TTLCache

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def async_operation(func):
    """Decorator to run operations in background thread"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        def run_in_thread():
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Background operation failed: {e}")

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        return thread
    return wrapper

class ConnectionPool:
    """Simple database connection pool"""
    def __init__(self, db_path: str, max_connections: int = 5):
        self.db_path = db_path
        self.connections = []
        self.max_connections = max_connections
        self.lock = threading.Lock()

    @contextmanager
    def get_connection(self):
        """Get connection from pool"""
        conn = None
        with self.lock:
            if self.connections:
                conn = self.connections.pop()
            elif len(self.connections) < self.max_connections:
                conn = sqlite3.connect(self.db_path)
                conn.execute('PRAGMA foreign_keys = ON')

        if not conn:
            # Fall back to direct connection
            conn = sqlite3.connect(self.db_path)
            conn.execute('PRAGMA foreign_keys = ON')

        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            with self.lock:
                if len(self.connections) < self.max_connections:
                    self.connections.append(conn)
                else:
                    conn.close()

class CachedMCPDataModel:
    """Enhanced data model with caching and connection pooling"""
    def __init__(self, db_path: str = "multi-agent_mcp_context_manager.db"):
        self.db_path = db_path
        self.pool = ConnectionPool(db_path)

        # TTL caches (expire after 5 minutes)
        self.projects_cache = TTLCache(maxsize=100, ttl=300)
        self.sessions_cache = TTLCache(maxsize=500, ttl=300)
        self.agents_cache = TTLCache(maxsize=1000, ttl=300)

        self.init_database()

    def init_database(self):
        """Initialize database with performance optimizations"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()

            # Enable performance settings
            cursor.execute('PRAGMA journal_mode = WAL')  # Write-Ahead Logging
            cursor.execute('PRAGMA synchronous = NORMAL')  # Better performance
            cursor.execute('PRAGMA cache_size = 10000')  # Larger cache
            cursor.execute('PRAGMA temp_store = MEMORY')  # Memory temp storage

            # Create tables (simplified for space)
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
                deleted_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
            )''')

            # Performance indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_session ON agents(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_projects_active ON projects(deleted_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(deleted_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_active ON agents(deleted_at)')

            conn.commit()
            logger.info("Database initialized with performance optimizations")

    def clear_cache(self):
        """Clear all caches"""
        self.projects_cache.clear()
        self.sessions_cache.clear()
        self.agents_cache.clear()
        logger.info("Data caches cleared")

    def get_projects(self) -> Dict:
        """Get projects with caching"""
        cache_key = "all_projects"

        if cache_key in self.projects_cache:
            return self.projects_cache[cache_key]

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM projects WHERE deleted_at IS NULL ORDER BY name')

            projects = {}
            for row in cursor.fetchall():
                projects[row[0]] = {
                    'id': row[0], 'name': row[1], 'description': row[2],
                    'created_at': row[3], 'updated_at': row[4], 'sessions': {}
                }

            self.projects_cache[cache_key] = projects
            return projects

    @async_operation
    def create_project_async(self, name: str, description: str = "") -> str:
        """Create project asynchronously"""
        project_id = f"proj_{name.lower().replace(' ', '_').replace('-', '_')}"
        now = datetime.now().isoformat()

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                          (project_id, name, description, now, now))
            conn.commit()

            # Clear cache to force refresh
            self.clear_cache()
            logger.info(f"Created project asynchronously: {name}")
            return project_id

    def get_sessions(self, project_id: str = None) -> Dict:
        """Get sessions with optional project filtering"""
        cache_key = f"sessions_{project_id or 'all'}"

        if cache_key in self.sessions_cache:
            return self.sessions_cache[cache_key]

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()

            if project_id:
                cursor.execute('SELECT * FROM sessions WHERE project_id = ? AND deleted_at IS NULL ORDER BY name',
                              (project_id,))
            else:
                cursor.execute('SELECT * FROM sessions WHERE deleted_at IS NULL ORDER BY project_id, name')

            sessions = {}
            for row in cursor.fetchall():
                sessions[row[0]] = {
                    'id': row[0], 'name': row[1], 'project_id': row[2],
                    'description': row[3], 'created_at': row[4], 'updated_at': row[5], 'agents': []
                }

            self.sessions_cache[cache_key] = sessions
            return sessions

    def get_agents(self) -> Dict:
        """Get agents with caching"""
        cache_key = "all_agents"

        if cache_key in self.agents_cache:
            return self.agents_cache[cache_key]

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM agents WHERE deleted_at IS NULL ORDER BY name')

            agents = {}
            for row in cursor.fetchall():
                agents[row[0]] = {
                    'id': row[0], 'name': row[1], 'session_id': row[2],
                    'status': row[3], 'last_active': row[4]
                }

            self.agents_cache[cache_key] = agents
            return agents

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

class PerformantMCPView:
    """Performance-enhanced view with lazy loading and async operations"""
    def __init__(self, model: CachedMCPDataModel):
        self.model = model
        self.root = tk.Tk()
        self.root.title("Multi-Agent MCP Context Manager (Performance Enhanced)")
        self.root.geometry("1200x800")

        # Data refresh flag
        self.refresh_pending = False
        self.last_refresh = datetime.now()

        self.setup_ui()
        self.schedule_refresh()

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
        self.setup_performance_monitor(notebook)

    def setup_project_view(self, notebook):
        """Enhanced project view with lazy loading"""
        project_frame = ttk.Frame(notebook)
        notebook.add(project_frame, text="Project View")

        # Left panel with lazy tree
        left_frame = ttk.LabelFrame(project_frame, text="Projects", padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5, pady=5)

        self.project_tree = LazyTreeView(left_frame, height=15)
        self.project_tree.heading('#0', text='Project Structure')
        self.project_tree.column('#0', width=350)
        self.project_tree.pack(fill=tk.BOTH, expand=True)

        # Set up lazy loading
        self.project_tree.set_data_loader(self.load_tree_children)

        # Enhanced buttons with progress indicators
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        self.create_btn = ttk.Button(btn_frame, text="New Project", command=self.new_project_async)
        self.create_btn.pack(side=tk.LEFT, padx=2)

        ttk.Button(btn_frame, text="Refresh", command=self.refresh_data).pack(side=tk.LEFT, padx=2)

        # Progress bar
        self.progress = ttk.Progressbar(btn_frame, mode='indeterminate')
        self.progress.pack(side=tk.RIGHT, padx=5)

        # Right panel - Details with search
        right_frame = ttk.LabelFrame(project_frame, text="Details & Search", padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Search frame
        search_frame = ttk.Frame(right_frame)
        search_frame.pack(fill=tk.X, pady=5)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind('<KeyRelease>', self.on_search)

        self.details_text = tk.Text(right_frame, height=15, wrap=tk.WORD)
        self.details_text.pack(fill=tk.BOTH, expand=True, pady=5)

    def setup_performance_monitor(self, notebook):
        """Performance monitoring tab"""
        perf_frame = ttk.Frame(notebook)
        notebook.add(perf_frame, text="Performance")

        # Cache statistics
        cache_frame = ttk.LabelFrame(perf_frame, text="Cache Statistics", padding="10")
        cache_frame.pack(fill=tk.X, padx=5, pady=5)

        self.cache_info = tk.Text(cache_frame, height=10, width=60)
        self.cache_info.pack(fill=tk.BOTH, expand=True)

        # Refresh button
        ttk.Button(cache_frame, text="Refresh Stats", command=self.update_performance_stats).pack(pady=5)

        # Initial stats
        self.update_performance_stats()

    def load_tree_children(self, parent_item):
        """Load children for tree item on demand"""
        # This would implement lazy loading of sessions and agents
        # For now, just a placeholder
        logger.info(f"Lazy loading children for item: {parent_item}")

    def new_project_async(self):
        """Create project with async operation"""
        name = simpledialog.askstring("New Project", "Project name:")
        if not name:
            return

        description = simpledialog.askstring("New Project", "Description (optional):") or ""

        # Disable button and show progress
        self.create_btn.config(state='disabled', text='Creating...')
        self.progress.start()
        self.status_var.set("Creating project...")

        # Create project in background
        thread = self.model.create_project_async(name, description)

        # Monitor completion
        self.root.after(100, lambda: self.monitor_async_operation(thread, "Project created successfully"))

    def monitor_async_operation(self, thread, success_message):
        """Monitor background thread completion"""
        if thread.is_alive():
            # Still running, check again
            self.root.after(100, lambda: self.monitor_async_operation(thread, success_message))
            return

        # Operation completed
        self.create_btn.config(state='normal', text='New Project')
        self.progress.stop()
        self.status_var.set(success_message)

        # Refresh data
        self.root.after(500, self.refresh_data)  # Small delay for user feedback

    def refresh_data(self):
        """Refresh data with rate limiting"""
        now = datetime.now()
        if (now - self.last_refresh).seconds < 1:  # Rate limit: max once per second
            return

        self.last_refresh = now
        self.status_var.set("Refreshing data...")

        # Clear caches and reload
        self.model.clear_cache()
        self.load_project_data()

        self.status_var.set("Data refreshed")

    def load_project_data(self):
        """Load and display project data"""
        try:
            projects = self.model.get_projects()

            # Clear existing items
            self.project_tree.delete(*self.project_tree.get_children())

            # Add projects
            for project_id, project in projects.items():
                self.project_tree.insert('', tk.END, text=f"📁 {project['name']}",
                                       values=('project', project_id))

            logger.info(f"Loaded {len(projects)} projects")

        except Exception as e:
            logger.error(f"Failed to load project data: {e}")
            messagebox.showerror("Error", f"Failed to load data: {e}")

    def on_search(self, event=None):
        """Handle search functionality"""
        search_term = self.search_var.get().lower()
        if not search_term:
            return

        # Simple search implementation
        # In a full implementation, this would search through all data
        self.status_var.set(f"Searching for: {search_term}")

    def update_performance_stats(self):
        """Update performance statistics"""
        stats = []
        stats.append("=== Cache Statistics ===")
        stats.append(f"Projects Cache: {len(self.model.projects_cache)}/{self.model.projects_cache.maxsize}")
        stats.append(f"Sessions Cache: {len(self.model.sessions_cache)}/{self.model.sessions_cache.maxsize}")
        stats.append(f"Agents Cache: {len(self.model.agents_cache)}/{self.model.agents_cache.maxsize}")
        stats.append("")
        stats.append("=== Connection Pool ===")
        stats.append(f"Available Connections: {len(self.model.pool.connections)}/{self.model.pool.max_connections}")
        stats.append("")
        stats.append("=== Performance Tips ===")
        stats.append("• Caches expire after 5 minutes")
        stats.append("• Connection pool reduces DB overhead")
        stats.append("• Lazy loading improves UI responsiveness")

        self.cache_info.delete(1.0, tk.END)
        self.cache_info.insert(1.0, "\\n".join(stats))

    def schedule_refresh(self):
        """Schedule periodic data refresh"""
        self.load_project_data()
        # Schedule next refresh in 30 seconds
        self.root.after(30000, self.schedule_refresh)

    def run(self):
        """Start the enhanced application"""
        try:
            self.root.mainloop()
        except Exception as e:
            logger.error(f"Application error: {e}")
            messagebox.showerror("Error", f"Application error: {e}")

def main():
    """Main entry point for performance-enhanced version"""
    try:
        model = CachedMCPDataModel()
        view = PerformantMCPView(model)
        view.run()
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        messagebox.showerror("Error", f"Failed to start application: {e}")

if __name__ == "__main__":
    main()