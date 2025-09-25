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
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager
from functools import wraps
from cachetools import TTLCache
import asyncio
import threading
import json
import time
import base64
try:
    import keyring
except Exception:
    keyring = None
import pathlib
try:
    import websockets
except Exception:
    websockets = None
import socket
import os
import urllib.request
import urllib.error
import uvicorn
from mcp_server import app as mcp_app


class ServerSubscriber:
    """Background WebSocket subscriber that connects to the MCP server and listens for broadcasts.

    It runs an asyncio loop in a dedicated thread and schedules GUI-safe callbacks via the view's
    `root.after` method on agent_status events.
    """
    def __init__(self, view, uri: str = "ws://127.0.0.1:8765/ws/gui_subscriber"):
        self.view = view
        self.uri = uri
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        # Attempt to cancel the websocket connection by connecting a short-lived client
        # The worker loop checks _stop_event and will exit.
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run_loop(self):
        try:
            asyncio.run(self._main())
        except Exception:
            logger.exception("ServerSubscriber loop failed")

    async def _main(self):
        if websockets is None:
            logger.warning("websockets not available; ServerSubscriber disabled")
            return

        try:
            async with websockets.connect(self.uri) as ws:
                logger.info(f"ServerSubscriber connected to {self.uri}")
                while not self._stop_event.is_set():
                    try:
                        text = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    except Exception:
                        break

                    try:
                        msg = json.loads(text)
                    except Exception:
                        continue

                    # React to agent_status events
                    if isinstance(msg, dict) and msg.get("type") == "agent_status":
                        agent_id = msg.get("agent_id")
                        status = msg.get("status")
                        logger.info(f"Received agent_status: {agent_id}={status}")
                        # Schedule cache clear on the GUI thread via view.root.after
                        try:
                            root = getattr(self.view, 'root', None)
                            if root is not None and hasattr(root, 'after') and root.winfo_exists():
                                root.after(0, self.view.model.clear_cache)
                            else:
                                # Fallback: call clear_cache directly
                                self.view.model.clear_cache()
                        except Exception:
                            logger.exception("Failed handling agent_status")
        except Exception as e:
            logger.exception(f"ServerSubscriber connection failed: {e}")

class SelectionDialog:
    """Dialog for selecting options without name/description requirements"""
    def __init__(self, parent, title, message, fields):
        self.result = None
        self.parent = parent

        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.setup_ui(message, fields)

        # Center the dialog after setup
        self.center_dialog()

    def setup_ui(self, message, fields):
        """Setup dialog UI for selections"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Message with text wrapping
        if message:
            message_label = tk.Label(main_frame, text=message, wraplength=360, justify=tk.LEFT, font=('TkDefaultFont', 10))
            message_label.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 15))

        # Fields
        self.field_widgets = {}
        row = 1
        for field_name, field_config in fields.items():
            ttk.Label(main_frame, text=field_config['label']).grid(row=row, column=0, sticky=tk.W, pady=5, padx=(0, 10))

            if field_config['type'] == 'combobox':
                widget = ttk.Combobox(main_frame, width=30, state="readonly",
                                    values=field_config.get('values', []))
                if field_config.get('default'):
                    widget.set(field_config['default'])
            else:
                widget = ttk.Entry(main_frame, width=30)

            widget.grid(row=row, column=1, columnspan=2, sticky=tk.EW, pady=5)
            self.field_widgets[field_name] = widget
            row += 1

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=3, pady=(20, 0))

        ttk.Button(button_frame, text="Confirm", command=self.on_confirm).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.LEFT)

        # Configure column weights
        main_frame.columnconfigure(1, weight=1)

        # Bind keys
        self.dialog.bind('<Return>', lambda e: self.on_confirm())
        self.dialog.bind('<Escape>', lambda e: self.on_cancel())

        # Focus first field
        if self.field_widgets:
            first_widget = next(iter(self.field_widgets.values()))
            first_widget.focus()

    def center_dialog(self):
        """Center dialog on screen after measuring content"""
        self.dialog.update_idletasks()
        width = self.dialog.winfo_reqwidth()
        height = self.dialog.winfo_reqheight()

        # Ensure minimum size but allow dynamic sizing
        width = max(450, width)
        height = max(200, height)

        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")

    def on_confirm(self):
        """Handle confirm button"""
        # Get field values
        field_values = {}
        for field_name, widget in self.field_widgets.items():
            value = widget.get().strip()
            field_values[field_name] = value

        # Validate that required fields have values
        missing_fields = []
        for field_name, widget in self.field_widgets.items():
            if not widget.get().strip():
                missing_fields.append(field_name)

        if missing_fields:
            messagebox.showwarning("Warning", f"Please select: {', '.join(missing_fields)}", parent=self.dialog)
            return

        self.result = field_values
        self.dialog.destroy()

    def on_cancel(self):
        """Handle cancel button"""
        self.result = None
        self.dialog.destroy()

    def show(self):
        """Show dialog and return result"""
        self.dialog.wait_window()
        return self.result


class UnifiedDialog:
    """Unified dialog for creating entities with name and description"""
    def __init__(self, parent, title, name_label="Name:", description_label="Description (optional):",
                 extra_fields=None):
        self.result = None
        self.parent = parent

        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (300 // 2)
        self.dialog.geometry(f"400x300+{x}+{y}")

        self.setup_ui(name_label, description_label, extra_fields or {})

    def setup_ui(self, name_label, description_label, extra_fields):
        """Setup dialog UI"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Name field
        ttk.Label(main_frame, text=name_label).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(main_frame, width=40, font=('TkDefaultFont', 10))
        self.name_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=5)
        self.name_entry.focus()

        # Extra fields (like project selection for sessions)
        self.extra_widgets = {}
        row = 1
        for field_name, field_config in extra_fields.items():
            ttk.Label(main_frame, text=field_config['label']).grid(row=row, column=0, sticky=tk.W, pady=5)

            if field_config['type'] == 'combobox':
                widget = ttk.Combobox(main_frame, width=37, state="readonly",
                                    values=field_config.get('values', []))
                if field_config.get('default'):
                    widget.set(field_config['default'])
            else:
                widget = ttk.Entry(main_frame, width=40)

            widget.grid(row=row, column=1, columnspan=2, sticky=tk.EW, pady=5)
            self.extra_widgets[field_name] = widget
            row += 1

        # Description field
        ttk.Label(main_frame, text=description_label).grid(row=row, column=0, sticky=tk.NW, pady=5)
        self.description_text = tk.Text(main_frame, width=40, height=6, font=('TkDefaultFont', 9))
        self.description_text.grid(row=row, column=1, columnspan=2, sticky=tk.EW, pady=5)

        # Scrollbar for description
        desc_scroll = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.description_text.yview)
        desc_scroll.grid(row=row, column=3, sticky=tk.NS, pady=5)
        self.description_text.config(yscrollcommand=desc_scroll.set)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row+1, column=0, columnspan=4, pady=20)

        ttk.Button(button_frame, text="Create", command=self.on_create).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.LEFT, padx=5)

        # Configure column weights
        main_frame.columnconfigure(1, weight=1)

        # Bind Enter key to create
        self.dialog.bind('<Return>', lambda e: self.on_create())
        self.dialog.bind('<Escape>', lambda e: self.on_cancel())

    def on_create(self):
        """Handle create button"""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Name is required", parent=self.dialog)
            self.name_entry.focus()
            return

        description = self.description_text.get(1.0, tk.END).strip()

        # Get extra field values
        extra_values = {}
        for field_name, widget in self.extra_widgets.items():
            extra_values[field_name] = widget.get()

        self.result = {
            'name': name,
            'description': description,
            **extra_values
        }
        self.dialog.destroy()

    def on_cancel(self):
        """Handle cancel button"""
        self.result = None
        self.dialog.destroy()

    def show(self):
        """Show dialog and return result"""
        self.dialog.wait_window()
        return self.result

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _is_port_responding(port: int, timeout: float = 0.5) -> bool:
    """Return True if an HTTP health endpoint responds on the given port."""
    try:
        url = f"http://127.0.0.1:{port}/healthz"
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _is_port_free(port: int, host: str = '127.0.0.1') -> bool:
    """Try to bind to the port to check whether it's free. Returns True if free."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((host, port))
        s.listen(1)
        return True
    except OSError:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def _start_uvicorn_in_thread(port: int) -> threading.Thread:
    """Start uvicorn programmatically in a daemon thread and return the thread object.

    The server instance is attached to `mcp_app.state._uvicorn_server` so shutdown endpoint can set should_exit.
    """
    def _run():
        try:
            config = uvicorn.Config(app=mcp_app, host="127.0.0.1", port=port, log_level="info")
            server = uvicorn.Server(config)
            # expose server on app state
            try:
                mcp_app.state._uvicorn_server = server
            except Exception:
                logger.exception("Failed to attach server instance to app.state")

            logger.info(f"Starting programmatic uvicorn server on port {port}")
            asyncio.run(server.serve())
            logger.info("Programmatic uvicorn server exited")
        except Exception:
            logger.exception("Programmatic uvicorn thread failed")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread

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
        self.teams_cache = TTLCache(maxsize=200, ttl=300)

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
            CREATE TABLE IF NOT EXISTS teams (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                session_id TEXT,
                description TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                deleted_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                session_id TEXT,
                team_id TEXT,
                status TEXT DEFAULT 'disconnected',
                last_active TIMESTAMP,
                updated_at TIMESTAMP,
                deleted_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL,
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL
            )''')

            # Performance indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_session ON agents(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_team ON agents(team_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_teams_session ON teams(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_projects_active ON projects(deleted_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(deleted_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_active ON agents(deleted_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_teams_active ON teams(deleted_at)')

            conn.commit()
            logger.info("Database initialized with performance optimizations")

    def clear_cache(self):
        """Clear all caches"""
        self.projects_cache.clear()
        self.sessions_cache.clear()
        self.agents_cache.clear()
        self.teams_cache.clear()
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
                    'team_id': row[3], 'status': row[4], 'last_active': row[5]
                }

            self.agents_cache[cache_key] = agents
            return agents

    def get_teams(self, session_id: str = None) -> Dict:
        """Get all teams (teams are independent of sessions)"""
        cache_key = "teams_all"  # Teams are session-independent

        if cache_key in self.teams_cache:
            return self.teams_cache[cache_key]

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM teams WHERE deleted_at IS NULL ORDER BY name')

            teams = {}
            for row in cursor.fetchall():
                teams[row[0]] = {
                    'id': row[0], 'name': row[1], 'session_id': row[2],  # Keep for compatibility
                    'description': row[3], 'created_at': row[4]
                }

            self.teams_cache[cache_key] = teams
            return teams

    def create_team(self, name: str, session_id: str = None, description: str = "") -> str:
        """Create new team"""
        team_id = f"team_{name.lower().replace(' ', '_').replace('-', '_')}"
        now = datetime.now().isoformat()

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO teams (id, name, session_id, description, created_at) VALUES (?, ?, ?, ?, ?)',
                          (team_id, name, session_id, description, now))
            conn.commit()

            # Clear cache to force refresh
            self.clear_cache()
            logger.info(f"Created team: {name}")
            return team_id

    def assign_agents_to_team(self, agent_ids: List[str], team_id: str = None):
        """Assign multiple agents to a team or unassign them"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            for agent_id in agent_ids:
                cursor.execute('UPDATE agents SET team_id = ? WHERE id = ?', (team_id, agent_id))
            conn.commit()
            self.clear_cache()
            action = f"assigned to team {team_id}" if team_id else "unassigned from teams"
            logger.info(f"Bulk {action}: {len(agent_ids)} agents")

    def assign_agents_to_session(self, agent_ids: List[str], session_id: str = None):
        """Assign multiple agents to a session or disconnect them"""
        status = 'connected' if session_id else 'disconnected'
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            for agent_id in agent_ids:
                cursor.execute('UPDATE agents SET session_id = ?, status = ? WHERE id = ?',
                              (session_id, status, agent_id))
            conn.commit()
            self.clear_cache()
            action = f"assigned to session {session_id}" if session_id else "disconnected"
            logger.info(f"Bulk {action}: {len(agent_ids)} agents")

    def rename_agent(self, agent_id: str, new_name: str):
        """Rename an agent"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE agents SET name = ? WHERE id = ?', (new_name, agent_id))
            conn.commit()
            self.clear_cache()
            logger.info(f"Renamed agent {agent_id} to {new_name}")

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
        # Config file path
        self.config_path = pathlib.Path.home() / ".mcp_config.json"
        self.root = tk.Tk()
        self.root.title("Multi-Agent MCP Context Manager (Performance Enhanced)")
        self.root.geometry("1200x800")

        # Ensure MCP server is running (auto-launch if needed) and pick a port
        self.server_port = None
        try:
            self.ensure_server_running()
        except Exception:
            logger.exception("Failed to ensure server running; continuing without server")

        # Start a background subscriber to server broadcasts (if websockets available)
        self.server_subscriber = None
        if websockets is not None and self.server_port is not None:
            try:
                ws_uri = f"ws://127.0.0.1:{self.server_port}/ws/gui_subscriber"
                self.server_subscriber = ServerSubscriber(self, uri=ws_uri)
                self.server_subscriber.start()
            except Exception:
                logger.exception("Failed to start server subscriber")

        # Data refresh flag
        self.refresh_pending = False
        self.last_refresh = datetime.now()

        self.setup_ui()
        self.schedule_refresh()
        self.load_agent_data()
        self.load_team_data()
        # Ensure graceful shutdown when window closed
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def ensure_server_running(self, start_port: int = 8765, max_tries: int = 50, wait_seconds: float = 5.0):
        """Ensure MCP server is running. If not found, try to start it on start_port and increment until available.

        This will set self.server_port to the discovered port, or leave it None if no server could be started.
        """
        port = start_port
        for attempt in range(max_tries):
            try_port = start_port + attempt
            # If a running server responds, adopt that port
            try:
                if _is_port_responding(try_port):
                    self.server_port = try_port
                    logger.info(f"Found running MCP server on port {try_port}")
                    return
            except Exception:
                pass

            # If port appears free, attempt to start programmatic server there
            try:
                if _is_port_free(try_port):
                    logger.info(f"Attempting to programmatically start MCP server on port {try_port}")
                    _start_uvicorn_in_thread(try_port)
                    # Wait for server to come up
                    deadline = time.time() + wait_seconds
                    while time.time() < deadline:
                        if _is_port_responding(try_port):
                            self.server_port = try_port
                            logger.info(f"Programmatic MCP server started on port {try_port}")
                            return
                        time.sleep(0.1)
                    logger.warning(f"Server did not respond on port {try_port} after start attempt")
            except Exception:
                logger.exception(f"Failed attempting to start server on port {try_port}")

        logger.warning("Could not find or start MCP server on ports %s-%s", start_port, start_port + max_tries - 1)

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
        self.setup_team_management(notebook)
        self.setup_performance_monitor(notebook)
    # Admin tab for allowlist management
    self.setup_admin_tab(notebook)

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
        self.project_tree.bind('<<TreeviewSelect>>', self.on_project_tree_select)

        # Set up lazy loading
        self.project_tree.set_data_loader(self.load_tree_children)

        # Enhanced buttons with progress indicators
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        self.create_btn = ttk.Button(btn_frame, text="New Project", command=self.new_project_async)
        self.create_btn.pack(side=tk.LEFT, padx=2)

        ttk.Button(btn_frame, text="New Session", command=self.new_session).pack(side=tk.LEFT, padx=2)
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

        self.details_text = tk.Text(right_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.details_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Context viewing button
        context_frame = ttk.Frame(right_frame)
        context_frame.pack(fill=tk.X, pady=2)
        self.view_contexts_btn = ttk.Button(context_frame, text="View Agent Contexts", command=self.view_agent_contexts, state=tk.DISABLED)
        self.view_contexts_btn.pack(side=tk.RIGHT, padx=5)

        # Agent assignment section
        assign_frame = ttk.LabelFrame(right_frame, text="Agent Assignment", padding="5")
        assign_frame.pack(fill=tk.X, pady=5)

        ttk.Label(assign_frame, text="Available Agents:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.available_agents_combo = ttk.Combobox(assign_frame, width=20, state="readonly")
        self.available_agents_combo.grid(row=0, column=1, padx=5)
        ttk.Button(assign_frame, text="Assign to Session", command=self.assign_agent_to_session).grid(row=0, column=2, padx=5)
        ttk.Button(assign_frame, text="Disconnect", command=self.disconnect_agent_from_session).grid(row=0, column=3, padx=5)

        # Team assignment section
        ttk.Label(assign_frame, text="Team Operations:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=(10,5))
        ttk.Button(assign_frame, text="Assign Team to Session", command=self.assign_team_to_session_dialog).grid(row=1, column=1, columnspan=2, padx=5, pady=(10,5), sticky=tk.W)


    def setup_agent_management(self, notebook):
        """Enhanced agent management with multi-select and bulk operations"""
        agent_frame = ttk.Frame(notebook)
        notebook.add(agent_frame, text="Agent Management")

        # Top section - Agent creation
        create_frame = ttk.LabelFrame(agent_frame, text="Create Agent", padding="10")
        create_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(create_frame, text="Create New Agent", command=self.create_agent).pack(pady=10)

        # Agent list with multi-select
        list_frame = ttk.LabelFrame(agent_frame, text="Agents", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Agent treeview with checkboxes (multi-select)
        self.agent_tree = ttk.Treeview(list_frame, columns=('name', 'session', 'team', 'status'),
                                      selectmode='extended', height=15)
        self.agent_tree.heading('#0', text='Select')
        self.agent_tree.heading('name', text='Name', command=lambda: self.sort_agents('name'))
        self.agent_tree.heading('session', text='Session', command=lambda: self.sort_agents('session'))
        self.agent_tree.heading('team', text='Team', command=lambda: self.sort_agents('team'))
        self.agent_tree.heading('status', text='Status', command=lambda: self.sort_agents('status'))

        # Column widths
        self.agent_tree.column('#0', width=60)
        for col in ('name', 'session', 'team', 'status'):
            self.agent_tree.column(col, width=120)

        self.agent_tree.pack(fill=tk.BOTH, expand=True, pady=5)
        self.agent_tree.bind('<Double-1>', self.rename_agent_dialog)

        # Bulk operations frame
        bulk_frame = ttk.LabelFrame(agent_frame, text="Bulk Operations", padding="10")
        bulk_frame.pack(fill=tk.X, padx=5, pady=5)

        # Session operations
        session_frame = ttk.Frame(bulk_frame)
        session_frame.pack(fill=tk.X, pady=2)
        ttk.Label(session_frame, text="Session:").pack(side=tk.LEFT)
        self.session_combo = ttk.Combobox(session_frame, width=20, state="readonly")
        self.session_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(session_frame, text="Assign to Session", command=self.bulk_assign_session).pack(side=tk.LEFT, padx=5)
        ttk.Button(session_frame, text="Disconnect All", command=self.bulk_disconnect).pack(side=tk.LEFT, padx=5)

        # Team operations
        team_frame = ttk.Frame(bulk_frame)
        team_frame.pack(fill=tk.X, pady=2)
        ttk.Label(team_frame, text="Team:").pack(side=tk.LEFT)
        self.team_combo = ttk.Combobox(team_frame, width=20, state="readonly")
        self.team_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(team_frame, text="Assign to Team", command=self.bulk_assign_team).pack(side=tk.LEFT, padx=5)
        ttk.Button(team_frame, text="Unassign from Teams", command=self.bulk_unassign_team).pack(side=tk.LEFT, padx=5)

        # Individual operations
        individual_frame = ttk.Frame(bulk_frame)
        individual_frame.pack(fill=tk.X, pady=2)
        ttk.Button(individual_frame, text="View Agent Contexts", command=self.view_agent_contexts_from_management).pack(side=tk.LEFT, padx=5)

    def ensure_agent_allowlisted(self, agent_id: str):
        """Ensure the given agent_id is present in the allowlist file and update running server allowlist if possible.

        This function is silent and best-effort. It writes to MCP_AGENT_ALLOWLIST_FILE or ~/.mcp_allowlist.txt.
        """
        try:
            path = os.environ.get('MCP_AGENT_ALLOWLIST_FILE') or os.path.expanduser('~/.mcp_allowlist.txt')
            existing = set()
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as fh:
                        for ln in fh:
                            ln = ln.strip()
                            if ln and not ln.startswith('#'):
                                existing.add(ln)
                except Exception:
                    logger.exception("Failed to read allowlist file for migration")

            if agent_id not in existing:
                try:
                    with open(path, 'a', encoding='utf-8') as fh:
                        fh.write(f"{agent_id}\n")
                    logger.info("Added agent to allowlist file: %s", path)
                except Exception:
                    logger.exception("Failed to append agent to allowlist file")

            # Try to update running server module's AGENT_ALLOWLIST if present
            try:
                import mcp_server
                if hasattr(mcp_server, 'AGENT_ALLOWLIST'):
                    try:
                        mcp_server.AGENT_ALLOWLIST.add(agent_id)
                        logger.info("Added agent to running server allowlist: %s", agent_id)
                    except Exception:
                        logger.exception("Failed updating mcp_server.AGENT_ALLOWLIST at runtime")
            except Exception:
                # Not fatal; server may not be running in same process
                pass
        except Exception:
            logger.exception("ensure_agent_allowlisted failed for %s", agent_id)

    def setup_team_management(self, notebook):
        """Team management interface"""
        team_frame = ttk.Frame(notebook)
        notebook.add(team_frame, text="Team Management")

        # Team creation
        create_frame = ttk.LabelFrame(team_frame, text="Create Team", padding="10")
        create_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(create_frame, text="Create New Team", command=self.create_team).pack(pady=10)

        # Team list
        list_frame = ttk.LabelFrame(team_frame, text="Teams", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.team_tree = ttk.Treeview(list_frame, columns=('name', 'agent_count', 'created'), height=15)
        self.team_tree.heading('#0', text='Team ID')
        self.team_tree.heading('name', text='Name', command=lambda: self.sort_teams('name'))
        self.team_tree.heading('agent_count', text='Agents', command=lambda: self.sort_teams('agent_count'))
        self.team_tree.heading('created', text='Created', command=lambda: self.sort_teams('created'))

        for col in ('name', 'agent_count', 'created'):
            self.team_tree.column(col, width=150)

        self.team_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Team bulk operations frame
        team_bulk_frame = ttk.LabelFrame(team_frame, text="Team Operations", padding="10")
        team_bulk_frame.pack(fill=tk.X, padx=5, pady=5)

        # Session operations for all agents in team
        session_frame = ttk.Frame(team_bulk_frame)
        session_frame.pack(fill=tk.X, pady=2)
        ttk.Label(session_frame, text="Assign all team agents to session:").pack(side=tk.LEFT)
        self.team_agents_session_combo = ttk.Combobox(session_frame, width=25, state="readonly")
        self.team_agents_session_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(session_frame, text="Assign Team Agents", command=self.assign_team_agents_to_session).pack(side=tk.LEFT, padx=5)
        ttk.Button(session_frame, text="Disconnect Team Agents", command=self.disconnect_team_agents).pack(side=tk.LEFT, padx=5)

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
        # Shutdown server button (local only)
        ttk.Button(cache_frame, text="Shutdown Server", command=self.shutdown_server).pack(pady=5)

        # Initial stats
        self.update_performance_stats()

    def setup_admin_tab(self, notebook):
        """Admin tab for managing agent allowlist"""
        admin_frame = ttk.Frame(notebook)
        notebook.add(admin_frame, text="Admin")

        allow_frame = ttk.LabelFrame(admin_frame, text="Agent Allowlist", padding="10")
        allow_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # List of allowlisted agents
        self.allowlist_var = tk.StringVar(value=self._read_allowlist_file())
        self.allowlist_listbox = tk.Listbox(allow_frame, listvariable=self.allowlist_var, height=12, selectmode=tk.SINGLE)
        self.allowlist_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(0,10))

        # Controls
        ctrl_frame = ttk.Frame(allow_frame)
        ctrl_frame.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Button(ctrl_frame, text="Add Agent", command=self._admin_add_agent).pack(fill=tk.X, pady=5)
        ttk.Button(ctrl_frame, text="Remove Selected", command=self._admin_remove_selected).pack(fill=tk.X, pady=5)
        ttk.Button(ctrl_frame, text="Reload Allowlist", command=self._admin_reload_allowlist).pack(fill=tk.X, pady=5)
        ttk.Button(ctrl_frame, text="Persist & Push", command=self._admin_persist_and_push).pack(fill=tk.X, pady=5)

    def _read_allowlist_file(self):
        try:
            path = os.environ.get('MCP_AGENT_ALLOWLIST_FILE') or os.path.expanduser('~/.mcp_allowlist.txt')
            items = []
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as fh:
                    for ln in fh:
                        ln = ln.strip()
                        if ln and not ln.startswith('#'):
                            items.append(ln)
            return items
        except Exception:
            logger.exception("Failed to read allowlist file")
            return []

    def _write_allowlist_file(self, items):
        try:
            path = os.environ.get('MCP_AGENT_ALLOWLIST_FILE') or os.path.expanduser('~/.mcp_allowlist.txt')
            with open(path, 'w', encoding='utf-8') as fh:
                for it in items:
                    fh.write(f"{it}\n")
            logger.info("Persisted allowlist to %s", path)
        except Exception:
            logger.exception("Failed to persist allowlist file")

    def _admin_add_agent(self):
        name = simpledialog.askstring("Add Agent to Allowlist", "Agent ID:", parent=self.root)
        if not name:
            return
        items = list(self.allowlist_var.get()) if isinstance(self.allowlist_var.get(), (list, tuple)) else list(self._read_allowlist_file())
        if name in items:
            messagebox.showinfo("Info", "Agent already in allowlist", parent=self.root)
            return
        items.append(name)
        self.allowlist_var.set(items)

    def _admin_remove_selected(self):
        sel = self.allowlist_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        items = list(self.allowlist_var.get()) if isinstance(self.allowlist_var.get(), (list, tuple)) else list(self._read_allowlist_file())
        try:
            removed = items.pop(idx)
            self.allowlist_var.set(items)
            messagebox.showinfo("Removed", f"Removed {removed} from allowlist", parent=self.root)
        except Exception:
            logger.exception("Failed removing selected allowlist item")

    def _admin_reload_allowlist(self):
        items = self._read_allowlist_file()
        self.allowlist_var.set(items)
        messagebox.showinfo("Reloaded", "Allowlist reloaded from file", parent=self.root)

    def _admin_persist_and_push(self):
        # Persist to file
        items = list(self.allowlist_var.get()) if isinstance(self.allowlist_var.get(), (list, tuple)) else list(self._read_allowlist_file())
        self._write_allowlist_file(items)

        # Try to push to running server module
        try:
            import mcp_server
            if hasattr(mcp_server, 'AGENT_ALLOWLIST'):
                try:
                    mcp_server.AGENT_ALLOWLIST.clear()
                    for it in items:
                        mcp_server.AGENT_ALLOWLIST.add(it)
                    messagebox.showinfo("Pushed", "Allowlist pushed to running server", parent=self.root)
                    logger.info("Pushed allowlist to running server: %s", items)
                except Exception:
                    logger.exception("Failed to update running server AGENT_ALLOWLIST")
                    messagebox.showerror("Error", "Failed to push allowlist to server (see logs)", parent=self.root)
            else:
                messagebox.showwarning("Warning", "Running server not detected in-process; changes persisted to file only", parent=self.root)
        except Exception:
            logger.exception("Failed to push allowlist to running server")
            messagebox.showwarning("Warning", "Could not contact running server in-process; allowlist persisted to file", parent=self.root)

    def load_tree_children(self, parent_item):
        """Load children for tree item on demand"""
        # This would implement lazy loading of sessions and agents
        # For now, just a placeholder
        logger.info(f"Lazy loading children for item: {parent_item}")

    def new_project_async(self):
        """Create project with unified dialog"""
        dialog = UnifiedDialog(
            self.root,
            "Create New Project",
            "Project Name:",
            "Project Description (optional):"
        )
        result = dialog.show()

        if not result:
            return

        name = result['name']
        description = result['description']

        try:
            project_id = f"proj_{name.lower().replace(' ', '_').replace('-', '_')}"
            now = datetime.now().isoformat()

            with self.model.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                              (project_id, name, description, now, now))
                conn.commit()

            # Clear cache and refresh
            self.model.clear_cache()
            self.load_project_data()
            self.status_var.set("Project created successfully")
            messagebox.showinfo("Success", f"Project '{name}' created successfully")

        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Project name already exists")
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            messagebox.showerror("Error", f"Failed to create project: {e}")

    def shutdown_server(self):
        """Request the local MCP server to shut down (development helper)."""
        import urllib.request
        import urllib.error
        import os

        port = getattr(self, 'server_port', 8765)
        url = f"http://127.0.0.1:{port}/shutdown"
        # Confirm with the user before sending shutdown
        if not messagebox.askyesno("Confirm Shutdown", "Shut down the local MCP server? This will flush pending writes.", parent=self.root):
            return

        headers = {}
        # Silent token handling: prefer environment, then OS keyring, then local config file (base64).
        token = os.environ.get('MCP_SHUTDOWN_TOKEN')
        if not token:
            try:
                # Try OS keyring first (secure)
                if keyring is not None:
                    try:
                        token = keyring.get_password('mcp', 'shutdown_token')
                    except Exception:
                        logger.exception("Keyring lookup failed; falling back to config file")

                # If still not found, fallback to config file (legacy storage)
                if not token and self.config_path.exists():
                    cfg = json.loads(self.config_path.read_text())
                    b64 = cfg.get('shutdown_token_b64')
                    if b64:
                        token = base64.b64decode(b64.encode('ascii')).decode('utf-8')

                        # If keyring is available, silently migrate token into keyring and remove legacy entry
                        if keyring is not None:
                            try:
                                keyring.set_password('mcp', 'shutdown_token', token)
                                # Remove legacy entry
                                cfg.pop('shutdown_token_b64', None)
                                try:
                                    self.config_path.write_text(json.dumps(cfg, indent=2))
                                except Exception:
                                    logger.exception("Failed to remove legacy token from config after migration")
                            except Exception:
                                logger.exception("Failed to migrate shutdown token into keyring")
            except Exception:
                logger.exception("Failed to read shutdown token from config/keyring; proceeding without token")

        if token:
            headers['Authorization'] = f"Bearer {token}"

        # Create a modal progress dialog
        progress_win = tk.Toplevel(self.root)
        progress_win.title("Shutting down server")
        progress_win.transient(self.root)
        progress_win.grab_set()
        ttk.Label(progress_win, text="Waiting for server to flush pending writes and stop...").pack(padx=20, pady=(10, 5))
        pb = ttk.Progressbar(progress_win, mode='indeterminate')
        pb.pack(fill=tk.X, padx=20, pady=(0, 10))
        pb.start(10)

        def do_shutdown():
            try:
                req = urllib.request.Request(url, method='POST', headers=headers)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = resp.read().decode('utf-8')
                # Show info and update status on GUI thread
                self.root.after(0, lambda: messagebox.showinfo("Server Shutdown", f"Server response: {body}", parent=self.root))
                self.root.after(0, lambda: self.status_var.set("Server stopped"))
            except urllib.error.HTTPError as he:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Shutdown failed: {he.code} {he.reason}", parent=self.root))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to contact server: {e}", parent=self.root))
            finally:
                # Stop and destroy progress window on GUI thread
                self.root.after(0, lambda: (pb.stop(), progress_win.destroy()))

        # Note: we intentionally do not prompt the user to save or enter tokens.
        # Token storage is handled silently via environment or config file.

        thread = threading.Thread(target=do_shutdown, daemon=True)
        thread.start()

    def new_session(self):
        """Create new session with unified dialog"""
        # Get available projects
        projects = self.model.get_projects()
        if not projects:
            messagebox.showwarning("Warning", "Create a project first")
            return

        # Prepare project options for combobox
        project_options = [p['name'] for p in projects.values()]

        dialog = UnifiedDialog(
            self.root,
            "Create New Session",
            "Session Name:",
            "Session Description (optional):",
            extra_fields={
                'project': {
                    'label': 'Project:',
                    'type': 'combobox',
                    'values': project_options,
                    'default': project_options[0] if project_options else ""
                }
            }
        )
        result = dialog.show()

        if not result:
            return

        session_name = result['name']
        description = result['description']
        project_choice = result['project']

        # Find project ID
        project_id = None
        for pid, project in projects.items():
            if project['name'] == project_choice:
                project_id = pid
                break

        if not project_id:
            messagebox.showerror("Error", "Project not found")
            return

        try:
            session_id = f"sess_{project_id}_{session_name.lower().replace(' ', '_').replace('-', '_')}"
            now = datetime.now().isoformat()

            with self.model.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO sessions (id, name, project_id, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                              (session_id, session_name, project_id, description, now, now))
                conn.commit()

            # Clear cache and refresh
            self.model.clear_cache()
            self.load_project_data()
            self.load_agent_data()  # Refresh agent combos
            self.status_var.set("Session created successfully")
            messagebox.showinfo("Success", f"Session '{session_name}' created in project '{project_choice}'")

        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Session name already exists in this project")
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            messagebox.showerror("Error", f"Failed to create session: {e}")

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

    def on_project_tree_select(self, event):
        """Handle project tree selection"""
        selection = self.project_tree.selection()
        if not selection:
            self.details_text.config(state=tk.NORMAL)
            self.details_text.delete(1.0, tk.END)
            self.details_text.config(state=tk.DISABLED)
            self.available_agents_combo['values'] = []
            self.view_contexts_btn.config(state=tk.DISABLED)
            return

        item = self.project_tree.item(selection[0])
        if not item.get('values'):
            return

        item_type, item_id = item['values']
        projects = self.model.get_projects()
        sessions = self.model.get_sessions()
        agents = self.model.get_agents()

        # Clear and populate details
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete(1.0, tk.END)
        self.view_contexts_btn.config(state=tk.DISABLED)
        self.current_selected_agent = None

        if item_type == 'project':
            project = projects.get(item_id)
            if project:
                details = f"PROJECT: {project['name']}\n\n"
                details += f"Description: {project['description'] or 'None'}\n"
                details += f"Created: {project['created_at']}\n"
                details += f"Sessions: {len([s for s in sessions.values() if s['project_id'] == item_id])}\n\n"

                # List sessions
                project_sessions = [s for s in sessions.values() if s['project_id'] == item_id]
                if project_sessions:
                    details += "SESSIONS:\n"
                    for session in project_sessions:
                        agent_count = len([a for a in agents.values() if a['session_id'] == session['id']])
                        details += f"• {session['name']} ({agent_count} agents)\n"

                self.details_text.insert(1.0, details)
                self.details_text.config(state=tk.DISABLED)

            # No agent assignment for projects
            self.available_agents_combo['values'] = []

        elif item_type == 'session':
            session = sessions.get(item_id)
            if session:
                project = projects.get(session['project_id'])
                session_agents = [a for a in agents.values() if a['session_id'] == item_id]

                details = f"SESSION: {session['name']}\n\n"
                details += f"Project: {project['name'] if project else 'Unknown'}\n"
                details += f"Description: {session['description'] or 'None'}\n"
                details += f"Created: {session['created_at']}\n"
                details += f"Connected Agents: {len(session_agents)}\n\n"

                if session_agents:
                    details += "AGENTS:\n"
                    for agent in session_agents:
                        status = "🟢 Connected" if agent['status'] == 'connected' else "🔴 Disconnected"
                        details += f"• {agent['name']} - {status}\n"

                self.details_text.insert(1.0, details)
                self.details_text.config(state=tk.DISABLED)

                # Show available agents for assignment
                available_agents = [a['name'] for a in agents.values() if not a['session_id']]
                self.available_agents_combo['values'] = available_agents

        elif item_type == 'agent':
            agent = agents.get(item_id)
            if agent:
                session = sessions.get(agent['session_id']) if agent['session_id'] else None
                project = projects.get(session['project_id']) if session else None

                details = f"AGENT: {agent['name']}\n\n"
                details += f"Status: {agent['status']}\n"
                details += f"Session: {session['name'] if session else 'None'}\n"
                details += f"Project: {project['name'] if project else 'None'}\n"
                details += f"Last Active: {agent['last_active'] or 'Never'}\n\n"

                # Show context count
                details += "CONTEXT DATA:\n"
                details += "Click 'View Agent Contexts' button to see saved conversations and data."

                self.details_text.insert(1.0, details)
                self.details_text.config(state=tk.DISABLED)

                # Enable context viewing for agents
                self.view_contexts_btn.config(state=tk.NORMAL)
                self.current_selected_agent = item_id

            self.available_agents_combo['values'] = []

    def assign_agent_to_session(self):
        """Assign selected agent to selected session"""
        selection = self.project_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Select a session first")
            return

        item = self.project_tree.item(selection[0])
        if not item.get('values') or item['values'][0] != 'session':
            messagebox.showwarning("Warning", "Select a session to assign agents to")
            return

        session_id = item['values'][1]
        agent_name = self.available_agents_combo.get()
        if not agent_name:
            messagebox.showwarning("Warning", "Select an agent to assign")
            return

        # Find agent ID
        agents = self.model.get_agents()
        agent_id = None
        for aid, agent in agents.items():
            if agent['name'] == agent_name:
                agent_id = aid
                break

        if agent_id:
            self.model.assign_agents_to_session([agent_id], session_id)
            self.model.clear_cache()
            self.load_project_data()
            self.load_agent_data()
            messagebox.showinfo("Success", f"Agent '{agent_name}' assigned to session")

    def disconnect_agent_from_session(self):
        """Disconnect selected agent"""
        selection = self.project_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Select an agent first")
            return

        item = self.project_tree.item(selection[0])
        if not item.get('values') or item['values'][0] != 'agent':
            messagebox.showwarning("Warning", "Select an agent to disconnect")
            return

        agent_id = item['values'][1]
        agents = self.model.get_agents()
        agent = agents.get(agent_id)

        if agent and messagebox.askyesno("Confirm", f"Disconnect agent '{agent['name']}'?"):
            self.model.assign_agents_to_session([agent_id], None)
            self.model.clear_cache()
            self.load_project_data()
            self.load_agent_data()
            messagebox.showinfo("Success", f"Agent '{agent['name']}' disconnected")

    def assign_team_to_session_dialog(self):
        """Show dialog to assign all agents from a team to a session"""
        # Get available teams and sessions
        teams = self.model.get_teams()
        sessions = self.model.get_sessions()
        projects = self.model.get_projects()

        if not teams:
            messagebox.showwarning("Warning", "No teams available")
            return

        if not sessions:
            messagebox.showwarning("Warning", "No sessions available")
            return

        # Prepare options for comboboxes
        team_options = [team['name'] for team in teams.values()]

        session_options = []
        for session_id, session in sessions.items():
            project = projects.get(session['project_id'])
            project_name = project['name'] if project else 'Unknown Project'
            session_options.append(f"[{project_name}] {session['name']}")

        # Create dialog
        dialog = SelectionDialog(
            self.root,
            "Assign Team to Session",
            "This will disconnect other agents from the target session and assign all agents from the selected team to it.",
            {
                'team': {
                    'label': 'Team:',
                    'type': 'combobox',
                    'values': team_options,
                    'default': team_options[0] if team_options else ""
                },
                'session': {
                    'label': 'Target Session:',
                    'type': 'combobox',
                    'values': session_options,
                    'default': session_options[0] if session_options else ""
                }
            }
        )
        result = dialog.show()

        if not result:
            return

        team_name = result['team']
        session_choice = result['session']

        # Find team ID
        team_id = None
        for tid, team in teams.items():
            if team['name'] == team_name:
                team_id = tid
                break

        if not team_id:
            messagebox.showerror("Error", "Team not found")
            return

        # Find session ID from formatted string
        session_id = None
        session_display = None
        for sid, session in sessions.items():
            project = projects.get(session['project_id'])
            project_name = project['name'] if project else 'Unknown Project'
            expected_format = f"[{project_name}] {session['name']}"

            if expected_format == session_choice:
                session_id = sid
                session_display = f"{project_name} > {session['name']}"
                break

        if not session_id:
            messagebox.showerror("Error", "Session not found")
            return

        # Execute the assignment logic
        self.execute_team_to_session_assignment(team_id, team_name, session_id, session_display)

    def execute_team_to_session_assignment(self, team_id, team_name, session_id, session_display):
        """Execute the team to session assignment logic"""
        try:
            with self.model.pool.get_connection() as conn:
                cursor = conn.cursor()

                # Get all agents in the selected team
                cursor.execute('SELECT id, name, session_id FROM agents WHERE team_id = ? AND deleted_at IS NULL', (team_id,))
                team_agents = cursor.fetchall()

                if not team_agents:
                    messagebox.showwarning("Warning", f"No agents found in team '{team_name}'")
                    return

                # Get all agents currently connected to the target session (not in our team)
                cursor.execute('SELECT id, name, team_id FROM agents WHERE session_id = ? AND team_id != ? AND deleted_at IS NULL',
                             (session_id, team_id))
                current_session_agents = cursor.fetchall()

                disconnected_count = 0
                connected_count = 0

                # First, disconnect all agents currently in the target session (not from our team)
                for agent_id, agent_name, agent_team_id in current_session_agents:
                    cursor.execute('UPDATE agents SET session_id = NULL, updated_at = ? WHERE id = ?',
                                 (datetime.now().isoformat(), agent_id))
                    disconnected_count += 1

                # Then, connect all team agents to the target session
                for agent_id, agent_name, current_session_id in team_agents:
                    if current_session_id != session_id:  # Only update if not already connected
                        cursor.execute('UPDATE agents SET session_id = ?, updated_at = ? WHERE id = ?',
                                     (session_id, datetime.now().isoformat(), agent_id))
                        connected_count += 1

                conn.commit()

            # Clear cache and refresh
            self.model.clear_cache()
            self.load_project_data()
            self.load_agent_data()
            self.load_team_data()

            # Show success message
            message = f"Team Assignment Complete:\n"
            message += f"• Connected {connected_count} agents from '{team_name}' to {session_display}\n"
            if disconnected_count > 0:
                message += f"• Disconnected {disconnected_count} other agents from {session_display}"

            messagebox.showinfo("Success", message)

        except Exception as e:
            logger.error(f"Failed to assign team to session: {e}")
            messagebox.showerror("Error", f"Failed to assign team to session: {e}")

    def view_agent_contexts(self):
        """View contexts for selected agent"""
        if not hasattr(self, 'current_selected_agent') or not self.current_selected_agent:
            messagebox.showwarning("Warning", "Select an agent first")
            return

        # Create context viewing window
        context_window = tk.Toplevel(self.root)
        context_window.title("Agent Contexts")
        context_window.geometry("800x600")
        context_window.transient(self.root)

        # Center the window
        context_window.update_idletasks()
        x = (context_window.winfo_screenwidth() // 2) - (800 // 2)
        y = (context_window.winfo_screenheight() // 2) - (600 // 2)
        context_window.geometry(f"800x600+{x}+{y}")

        main_frame = ttk.Frame(context_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Get agent info
        agents = self.model.get_agents()
        agent = agents.get(self.current_selected_agent)
        agent_name = agent['name'] if agent else 'Unknown Agent'

        ttk.Label(main_frame, text=f"Contexts for Agent: {agent_name}",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

        # Context list
        list_frame = ttk.LabelFrame(main_frame, text="Context History", padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Treeview for contexts
        context_tree = ttk.Treeview(list_frame, columns=('title', 'created', 'size'), height=15)
        context_tree.heading('#0', text='ID')
        context_tree.heading('title', text='Title')
        context_tree.heading('created', text='Created')
        context_tree.heading('size', text='Size')

        context_tree.column('#0', width=100)
        context_tree.column('title', width=300)
        context_tree.column('created', width=150)
        context_tree.column('size', width=100)

        context_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Load contexts from database
        try:
            with self.model.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, title, content, created_at, updated_at
                    FROM contexts
                    WHERE agent_id = ? AND deleted_at IS NULL
                    ORDER BY created_at DESC
                ''', (self.current_selected_agent,))

                contexts = cursor.fetchall()

                if contexts:
                    for ctx in contexts:
                        ctx_id, title, content, created_at, updated_at = ctx
                        content_size = f"{len(content or '')} chars"
                        created_date = created_at[:16] if created_at else 'Unknown'

                        context_tree.insert('', tk.END, text=ctx_id[:8] + '...',
                                          values=(title or 'Untitled', created_date, content_size))
                else:
                    context_tree.insert('', tk.END, text='No contexts',
                                      values=('No context data found for this agent', '', ''))

        except Exception as e:
            logger.error(f"Failed to load contexts: {e}")
            context_tree.insert('', tk.END, text='Error',
                              values=(f'Failed to load contexts: {e}', '', ''))

        # Context preview
        preview_frame = ttk.LabelFrame(main_frame, text="Context Preview", padding="5")
        preview_frame.pack(fill=tk.X, pady=(0, 10))

        preview_text = tk.Text(preview_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        preview_text.pack(fill=tk.X)

        def on_context_select(event):
            selection = context_tree.selection()
            if not selection:
                return

            # Get selected context
            item = context_tree.item(selection[0])
            if item['text'] == 'No contexts' or item['text'] == 'Error':
                return

            # Load full context content
            try:
                with self.model.pool.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT content FROM contexts WHERE agent_id = ? AND id LIKE ? AND deleted_at IS NULL',
                                 (self.current_selected_agent, item['text'].replace('...', '') + '%'))
                    result = cursor.fetchone()

                    preview_text.config(state=tk.NORMAL)
                    preview_text.delete(1.0, tk.END)
                    if result:
                        preview_text.insert(1.0, result[0] or 'No content')
                    else:
                        preview_text.insert(1.0, 'Context not found')
                    preview_text.config(state=tk.DISABLED)

            except Exception as e:
                logger.error(f"Failed to load context content: {e}")
                preview_text.config(state=tk.NORMAL)
                preview_text.delete(1.0, tk.END)
                preview_text.insert(1.0, f'Error loading content: {e}')
                preview_text.config(state=tk.DISABLED)

        context_tree.bind('<<TreeviewSelect>>', on_context_select)

        # Close button
        ttk.Button(main_frame, text="Close", command=context_window.destroy).pack(pady=(10, 0))

    def create_agent(self):
        """Create new agent with unified dialog"""
        dialog = UnifiedDialog(
            self.root,
            "Create New Agent",
            "Agent Name:",
            "Agent Description (optional):"
        )
        result = dialog.show()

        if not result:
            return

        name = result['name']

        try:
            agent_id = f"agent_{name.lower().replace(' ', '_').replace('-', '_')}"
            now = datetime.now().isoformat()

            with self.model.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO agents (id, name, status, last_active) VALUES (?, ?, ?, ?)',
                              (agent_id, name, 'disconnected', now))
                conn.commit()

            self.model.clear_cache()
            self.load_agent_data()
            # Ensure GUI-created agents are allowlisted so they can announce
            try:
                self.ensure_agent_allowlisted(agent_id)
            except Exception:
                logger.exception("Failed to ensure agent allowlist update for %s", agent_id)
            messagebox.showinfo("Success", f"Agent '{name}' created")

        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Agent name already exists")
        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            messagebox.showerror("Error", f"Failed to create agent: {e}")

    def create_team(self):
        """Create new team with unified dialog"""
        dialog = UnifiedDialog(
            self.root,
            "Create New Team",
            "Team Name:",
            "Team Description (optional):"
        )
        result = dialog.show()

        if not result:
            return

        name = result['name']
        description = result['description']

        try:
            team_id = self.model.create_team(name, None, description)  # Teams don't belong to sessions
            self.load_team_data()
            self.load_agent_data()  # Refresh team combos
            messagebox.showinfo("Success", f"Team '{name}' created")

        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Team name already exists")
        except Exception as e:
            logger.error(f"Failed to create team: {e}")
            messagebox.showerror("Error", f"Failed to create team: {e}")

    def get_selected_agents(self):
        """Get list of selected agent IDs"""
        selected_items = self.agent_tree.selection()
        return [self.agent_tree.item(item)['text'] for item in selected_items]

    def view_agent_contexts_from_management(self):
        """View contexts for selected agent from agent management screen"""
        selected_agents = self.get_selected_agents()
        if not selected_agents:
            messagebox.showwarning("Warning", "Select an agent first")
            return

        if len(selected_agents) > 1:
            messagebox.showwarning("Warning", "Please select only one agent to view contexts")
            return

        # Set the selected agent and use existing view method
        self.current_selected_agent = selected_agents[0]
        self.view_agent_contexts()

    def bulk_assign_session(self):
        """Assign selected agents to session"""
        agent_ids = self.get_selected_agents()
        if not agent_ids:
            messagebox.showwarning("Warning", "Select agents first")
            return

        session_selection = self.session_combo.get()
        if not session_selection:
            messagebox.showwarning("Warning", "Select a session")
            return

        # Parse [Project]>Session format
        if '>' in session_selection:
            session_name = session_selection.split('>')[-1]
        else:
            session_name = session_selection

        # Find session ID
        sessions = self.model.get_sessions()
        session_id = None
        for sid, session in sessions.items():
            if session['name'] == session_name:
                session_id = sid
                break

        if session_id:
            self.model.assign_agents_to_session(agent_ids, session_id)
            self.load_agent_data()
            messagebox.showinfo("Success", f"Assigned {len(agent_ids)} agents to session '{session_name}'")

    def bulk_disconnect(self):
        """Disconnect selected agents"""
        agent_ids = self.get_selected_agents()
        if not agent_ids:
            messagebox.showwarning("Warning", "Select agents first")
            return

        if messagebox.askyesno("Confirm", f"Disconnect {len(agent_ids)} agents?"):
            self.model.assign_agents_to_session(agent_ids, None)
            self.load_agent_data()
            messagebox.showinfo("Success", f"Disconnected {len(agent_ids)} agents")

    def bulk_assign_team(self):
        """Assign selected agents to team"""
        agent_ids = self.get_selected_agents()
        if not agent_ids:
            messagebox.showwarning("Warning", "Select agents first")
            return

        team_name = self.team_combo.get()
        if not team_name:
            messagebox.showwarning("Warning", "Select a team")
            return

        # Find team ID
        teams = self.model.get_teams()
        team_id = None
        for tid, team in teams.items():
            if team['name'] == team_name:
                team_id = tid
                break

        if team_id:
            self.model.assign_agents_to_team(agent_ids, team_id)
            self.load_agent_data()
            messagebox.showinfo("Success", f"Assigned {len(agent_ids)} agents to team '{team_name}'")

    def bulk_unassign_team(self):
        """Unassign selected agents from teams"""
        agent_ids = self.get_selected_agents()
        if not agent_ids:
            messagebox.showwarning("Warning", "Select agents first")
            return

        if messagebox.askyesno("Confirm", f"Unassign {len(agent_ids)} agents from their teams?"):
            self.model.assign_agents_to_team(agent_ids, None)
            self.load_agent_data()
            messagebox.showinfo("Success", f"Unassigned {len(agent_ids)} agents from teams")

    def rename_agent_dialog(self, event):
        """Open rename dialog for agent"""
        selected_items = self.agent_tree.selection()
        if not selected_items:
            return

        agent_id = self.agent_tree.item(selected_items[0])['text']
        current_name = self.agent_tree.item(selected_items[0])['values'][0]

        # Create simple rename dialog with proper sizing
        dialog = tk.Toplevel(self.root)
        dialog.title("Rename Agent")
        dialog.geometry("400x180")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (dialog.winfo_screenheight() // 2) - (180 // 2)
        dialog.geometry(f"400x180+{x}+{y}")

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Label
        ttk.Label(main_frame, text=f"Rename '{current_name}':", font=('TkDefaultFont', 10)).pack(pady=(0, 15))

        # Entry field
        name_entry = ttk.Entry(main_frame, width=35, font=('TkDefaultFont', 10))
        name_entry.pack(pady=(0, 20))
        name_entry.insert(0, current_name)
        name_entry.select_range(0, tk.END)
        name_entry.focus()

        result = [None]

        def on_ok():
            new_name = name_entry.get().strip()
            if new_name and new_name != current_name:
                result[0] = new_name
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        # Button frame with proper spacing
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 0))

        ttk.Button(button_frame, text="Rename", command=on_ok, width=12).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=on_cancel, width=12).pack(side=tk.LEFT)

        dialog.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_cancel())

        dialog.wait_window()

        if not result[0]:
            return

        try:
            self.model.rename_agent(agent_id, result[0])
            self.load_agent_data()
            messagebox.showinfo("Success", f"Renamed agent to '{result[0]}'")

        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Agent name already exists")
        except Exception as e:
            logger.error(f"Failed to rename agent: {e}")
            messagebox.showerror("Error", f"Failed to rename agent: {e}")

    def sort_agents(self, column):
        """Sort agents by the specified column"""
        # Get all items and their data
        items = []
        for child in self.agent_tree.get_children():
            item_data = self.agent_tree.item(child)
            agent_id = item_data['text']
            values = item_data['values']

            # Create sortable tuple based on column
            if column == 'name':
                sort_key = values[0].lower() if values[0] else ''
            elif column == 'session':
                sort_key = values[1].lower() if values[1] else ''
            elif column == 'team':
                sort_key = values[2].lower() if values[2] else ''
            elif column == 'status':
                sort_key = values[3].lower() if values[3] else ''
            else:
                sort_key = ''

            items.append((sort_key, agent_id, values))

        # Check if already sorted in ascending order
        if hasattr(self, 'agent_sort_reverse') and hasattr(self, 'agent_last_sort_column'):
            if self.agent_last_sort_column == column:
                # Toggle sort order
                self.agent_sort_reverse = not self.agent_sort_reverse
            else:
                # New column, start with ascending
                self.agent_sort_reverse = False
                self.agent_last_sort_column = column
        else:
            # First sort
            self.agent_sort_reverse = False
            self.agent_last_sort_column = column

        # Sort items
        items.sort(key=lambda x: x[0], reverse=self.agent_sort_reverse)

        # Clear and repopulate tree
        self.agent_tree.delete(*self.agent_tree.get_children())
        for sort_key, agent_id, values in items:
            self.agent_tree.insert('', tk.END, text=agent_id, values=values)

        # Update column heading to show sort direction
        direction = ' ↓' if self.agent_sort_reverse else ' ↑'
        # Reset all headings first, maintaining click commands
        self.agent_tree.heading('name', text='Name', command=lambda: self.sort_agents('name'))
        self.agent_tree.heading('session', text='Session', command=lambda: self.sort_agents('session'))
        self.agent_tree.heading('team', text='Team', command=lambda: self.sort_agents('team'))
        self.agent_tree.heading('status', text='Status', command=lambda: self.sort_agents('status'))

        # Add direction to current column
        current_text = {'name': 'Name', 'session': 'Session', 'team': 'Team', 'status': 'Status'}[column]
        self.agent_tree.heading(column, text=current_text + direction, command=lambda: self.sort_agents(column))

    def load_agent_data(self):
        """Load and display agent data"""
        try:
            # Clear existing items
            for item in self.agent_tree.get_children():
                self.agent_tree.delete(item)

            agents = self.model.get_agents()
            sessions = self.model.get_sessions()
            teams = self.model.get_teams()

            # Update comboboxes with project>session format
            session_options = [""]
            projects = self.model.get_projects()
            for session_id, session in sessions.items():
                project = projects.get(session['project_id'])
                project_name = project['name'] if project else 'Unknown Project'
                session_options.append(f"[{project_name}]>{session['name']}")
            self.session_combo['values'] = session_options

            team_names = [""] + [t['name'] for t in teams.values()]
            self.team_combo['values'] = team_names

            # Note: Teams are independent of sessions - agents belong to teams regardless of session

            # Add agents to tree
            for agent_id, agent in agents.items():
                session_name = ""
                team_name = ""

                if agent['session_id']:
                    session = sessions.get(agent['session_id'])
                    if session:
                        session_name = session['name']

                if agent['team_id']:
                    team = teams.get(agent['team_id'])
                    if team:
                        team_name = team['name']

                self.agent_tree.insert('', tk.END, text=agent_id,
                                     values=(agent['name'], session_name, team_name, agent['status']))

            logger.info(f"Loaded {len(agents)} agents")

        except Exception as e:
            logger.error(f"Failed to load agent data: {e}")
            messagebox.showerror("Error", f"Failed to load agent data: {e}")

    def load_team_data(self):
        """Load and display team data"""
        try:
            # Clear existing items
            for item in self.team_tree.get_children():
                self.team_tree.delete(item)

            teams = self.model.get_teams()
            sessions = self.model.get_sessions()
            agents = self.model.get_agents()

            # Count agents per team
            team_agent_counts = {}
            for agent in agents.values():
                team_id = agent.get('team_id')
                if team_id:
                    team_agent_counts[team_id] = team_agent_counts.get(team_id, 0) + 1

            # Update session combo for team agent operations
            projects = self.model.get_projects()
            session_options = []
            for session_id, session in sessions.items():
                project = projects.get(session['project_id'])
                project_name = project['name'] if project else 'Unknown Project'
                session_options.append(f"[{project_name}]>{session['name']}")

            if hasattr(self, 'team_agents_session_combo'):
                self.team_agents_session_combo['values'] = session_options

            # Add teams to tree (no session column - teams are independent of sessions)
            for team_id, team in teams.items():
                agent_count = team_agent_counts.get(team_id, 0)
                created_date = team['created_at'][:10] if team['created_at'] else ""

                self.team_tree.insert('', tk.END, text=team_id,
                                    values=(team['name'], agent_count, created_date))

            logger.info(f"Loaded {len(teams)} teams")

        except Exception as e:
            logger.error(f"Failed to load team data: {e}")
            messagebox.showerror("Error", f"Failed to load team data: {e}")

    def assign_team_agents_to_session(self):
        """Assign all agents from selected team to a session (team membership stays the same)"""
        selected_items = self.team_tree.selection()
        if not selected_items:
            messagebox.showwarning("Warning", "Select a team first")
            return

        if len(selected_items) > 1:
            messagebox.showwarning("Warning", "Please select only one team")
            return

        session_choice = self.team_agents_session_combo.get()
        if not session_choice:
            messagebox.showwarning("Warning", "Select a session")
            return

        team_id = self.team_tree.item(selected_items[0])['text']
        teams = self.model.get_teams()
        team = teams.get(team_id)

        if not team:
            messagebox.showerror("Error", "Team not found")
            return

        # Parse session choice to find session ID
        session_id = None
        sessions = self.model.get_sessions()

        # Parse format: [Project Name]>Session Name
        for sid, session in sessions.items():
            projects = self.model.get_projects()
            project = projects.get(session['project_id'])
            project_name = project['name'] if project else 'Unknown Project'
            expected_format = f"[{project_name}]>{session['name']}"

            if expected_format == session_choice:
                session_id = sid
                session_display_name = session['name']
                break

        if session_id is None:
            messagebox.showerror("Error", "Session not found")
            return

        try:
            with self.model.pool.get_connection() as conn:
                cursor = conn.cursor()

                # Get all agents in this team and update their sessions (keep team membership)
                cursor.execute('SELECT id, name FROM agents WHERE team_id = ? AND deleted_at IS NULL', (team_id,))
                team_agents = cursor.fetchall()

                if not team_agents:
                    messagebox.showwarning("Warning", "No agents found in selected team")
                    return

                for agent_id, agent_name in team_agents:
                    cursor.execute('UPDATE agents SET session_id = ?, updated_at = ? WHERE id = ?',
                                 (session_id, datetime.now().isoformat(), agent_id))

                conn.commit()

            # Clear cache and refresh
            self.model.clear_cache()
            self.load_team_data()
            self.load_agent_data()
            self.load_project_data()

            agent_count = len(team_agents)
            messagebox.showinfo("Success",
                              f"All {agent_count} agents from team '{team['name']}' assigned to session: {session_display_name}")

        except Exception as e:
            logger.error(f"Failed to assign team agents to session: {e}")
            messagebox.showerror("Error", f"Failed to assign team agents to session: {e}")

    def disconnect_team_agents(self):
        """Disconnect all agents from selected team from their sessions (keep team membership)"""
        selected_items = self.team_tree.selection()
        if not selected_items:
            messagebox.showwarning("Warning", "Select a team first")
            return

        if len(selected_items) > 1:
            messagebox.showwarning("Warning", "Please select only one team")
            return

        team_id = self.team_tree.item(selected_items[0])['text']
        teams = self.model.get_teams()
        team = teams.get(team_id)

        if not team:
            messagebox.showerror("Error", "Team not found")
            return

        try:
            with self.model.pool.get_connection() as conn:
                cursor = conn.cursor()

                # Get all agents in this team
                cursor.execute('SELECT id, name FROM agents WHERE team_id = ? AND deleted_at IS NULL', (team_id,))
                team_agents = cursor.fetchall()

                if not team_agents:
                    messagebox.showwarning("Warning", "No agents found in selected team")
                    return

                if not messagebox.askyesno("Confirm",
                                         f"Disconnect all {len(team_agents)} agents from team '{team['name']}' from their sessions?"):
                    return

                # Disconnect all team agents from sessions (keep team membership)
                for agent_id, agent_name in team_agents:
                    cursor.execute('UPDATE agents SET session_id = NULL, updated_at = ? WHERE id = ?',
                                 (datetime.now().isoformat(), agent_id))

                conn.commit()

            # Clear cache and refresh
            self.model.clear_cache()
            self.load_team_data()
            self.load_agent_data()
            self.load_project_data()

            agent_count = len(team_agents)
            messagebox.showinfo("Success",
                              f"Disconnected all {agent_count} agents from team '{team['name']}' from their sessions")

        except Exception as e:
            logger.error(f"Failed to disconnect team agents: {e}")
            messagebox.showerror("Error", f"Failed to disconnect team agents: {e}")

    def sort_teams(self, column):
        """Sort teams by the specified column"""
        # Get all items and their data
        items = []
        for child in self.team_tree.get_children():
            item_data = self.team_tree.item(child)
            team_id = item_data['text']
            values = item_data['values']

            # Create sortable tuple based on column
            if column == 'name':
                sort_key = values[0].lower() if values[0] else ''
            elif column == 'agent_count':
                # Sort numerically for agent count
                sort_key = int(values[1]) if values[1] and str(values[1]).isdigit() else 0
            elif column == 'created':
                sort_key = values[2] if values[2] else ''
            else:
                sort_key = ''

            items.append((sort_key, team_id, values))

        # Check if already sorted in ascending order
        if hasattr(self, 'team_sort_reverse') and hasattr(self, 'team_last_sort_column'):
            if self.team_last_sort_column == column:
                # Toggle sort order
                self.team_sort_reverse = not self.team_sort_reverse
            else:
                # New column, start with ascending
                self.team_sort_reverse = False
                self.team_last_sort_column = column
        else:
            # First sort
            self.team_sort_reverse = False
            self.team_last_sort_column = column

        # Sort items
        items.sort(key=lambda x: x[0], reverse=self.team_sort_reverse)

        # Clear and repopulate tree
        self.team_tree.delete(*self.team_tree.get_children())
        for sort_key, team_id, values in items:
            self.team_tree.insert('', tk.END, text=team_id, values=values)

        # Update column heading to show sort direction
        direction = ' ↓' if self.team_sort_reverse else ' ↑'
        # Reset all headings first, maintaining click commands
        self.team_tree.heading('name', text='Name', command=lambda: self.sort_teams('name'))
        self.team_tree.heading('agent_count', text='Agents', command=lambda: self.sort_teams('agent_count'))
        self.team_tree.heading('created', text='Created', command=lambda: self.sort_teams('created'))

        # Add direction to current column
        current_text = {
            'name': 'Name',
            'agent_count': 'Agents',
            'created': 'Created'
        }[column]
        self.team_tree.heading(column, text=current_text + direction, command=lambda: self.sort_teams(column))

    def load_project_data(self):
        """Load and display project data with sessions and agents"""
        try:
            projects = self.model.get_projects()
            sessions = self.model.get_sessions()
            agents = self.model.get_agents()

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
                session_id = agent['session_id']
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
                        status_icon = "🟢" if agent['status'] == 'connected' else "🔴"
                        agent_text = f"{status_icon} {agent['name']}"
                        self.project_tree.insert(session_node, tk.END, text=agent_text,
                                               values=('agent', agent['id']))

            # Expand all project nodes to show sessions
            for item in self.project_tree.get_children():
                self.project_tree.item(item, open=True)

            logger.info(f"Loaded {len(projects)} projects, {len(sessions)} sessions, {len(agents)} agents")

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
        # Run the Tk main loop
        try:
            self.root.mainloop()
        finally:
            # Ensure subscriber stops when mainloop exits
            if hasattr(self, 'server_subscriber') and self.server_subscriber:
                self.server_subscriber.stop()

    def on_close(self):
        # Stop background subscriber then destroy window
        if hasattr(self, 'server_subscriber') and self.server_subscriber:
            try:
                self.server_subscriber.stop()
            except Exception:
                logger.exception("Error stopping server subscriber")
        try:
            self.root.destroy()
        except Exception:
            pass
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