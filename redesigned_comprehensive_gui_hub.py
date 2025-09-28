#!/usr/bin/env python3
"""
Main GUI Hub for Multi-Agent MCP Context Manager
Imports modular components and creates the main application window
"""

import tkinter as tk
from tkinter import ttk
import sqlite3
import requests
import threading
import time
import queue

# Import GUI modules
from gui_modules.data_format_tab import DataFormatInstructionsTab
from gui_modules.project_session_tab import ProjectSessionTab
from gui_modules.connection_assignment_tab import ConnectionAssignmentTab
from gui_modules.agent_management_tab import AgentManagementTab
from gui_modules.contexts_tab import ContextsTab


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
        return self.connection_pool.get()

    def return_connection(self, conn):
        """Return a connection to the pool"""
        self.connection_pool.put(conn)

    def execute_query(self, query, params=None):
        """Execute a SELECT query and return results"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()
        finally:
            self.return_connection(conn)

    def execute_update(self, query, params=None):
        """Execute an INSERT/UPDATE/DELETE query"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor.rowcount
        finally:
            self.return_connection(conn)

    def close_all_connections(self):
        """Close all connections in the pool"""
        while not self.connection_pool.empty():
            conn = self.connection_pool.get()
            conn.close()


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
                # Check server status
                response = requests.get(f"{self.server_url}/status", timeout=2)
                if response.status_code == 500:
                    status_data = response.json()
                    status_data['server_status'] = 'Online'
                    status_data['server_address'] = self.server_url
                else:
                    status_data = {
                        'server_status': 'Offline',
                        'server_address': self.server_url,
                        'active_connections': 0,
                        'registered_agents': 0,
                        'database_status': 'Unknown'
                    }
            except Exception:
                status_data = {
                    'server_status': 'Offline',
                    'server_address': self.server_url,
                    'active_connections': 0,
                    'registered_agents': 0,
                    'database_status': 'Unknown'
                }

            # Update GUI
            self.status_callback(status_data)
            time.sleep(3)  # Update every 3 seconds


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

        # Agent count
        ttk.Label(self.frame, textvariable=self.registered_agents).pack(side=tk.LEFT, padx=(0, 10))

        # Database status
        ttk.Label(self.frame, textvariable=self.database_status).pack(side=tk.LEFT, padx=(0, 10))

        # Server status
        ttk.Label(self.frame, textvariable=self.server_status).pack(side=tk.LEFT, padx=(0, 10))

        # Server address
        ttk.Label(self.frame, textvariable=self.server_address).pack(side=tk.RIGHT, padx=(10, 5))

    def update_status(self, status_data):
        """Update status bar with new data"""
        self.active_connections.set(f"Connections: {status_data.get('active_connections', 0)}")
        self.registered_agents.set(f"Agents: {status_data.get('registered_agents', 0)}")
        self.database_status.set(f"DB: {status_data.get('database_status', 'Unknown')}")
        self.server_status.set(f"Server: {status_data.get('server_status', 'Unknown')}")
        self.server_address.set(f"Address: {status_data.get('server_address', 'Unknown')}")

    def pack(self, **kwargs):
        """Pack the status bar frame"""
        self.frame.pack(**kwargs)


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
        # Data Format Instructions Tab
        instructions_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(instructions_frame, text="📋 Data Format Instructions")

        instructions_widget = DataFormatInstructionsTab(instructions_frame)
        instructions_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

        # Project & Sessions Tab
        project_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(project_frame, text="📁 Projects & Sessions")

        project_widget = ProjectSessionTab(project_frame, self.db_manager)
        project_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

        # Connection Assignment Tab
        connection_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(connection_frame, text="🔗 Connection Assignment")

        connection_widget = ConnectionAssignmentTab(connection_frame, self.db_manager)
        connection_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

        # Agent Management Tab
        agent_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(agent_frame, text="👥 Agent Management")

        agent_widget = AgentManagementTab(agent_frame, self.db_manager)
        agent_widget.create_widgets().pack(fill=tk.BOTH, expand=True)

        # Contexts Tab
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

            # Close database connections
            if hasattr(self, 'db_manager'):
                self.db_manager.close_all_connections()

        except Exception as e:
            print(f"Error during cleanup: {e}")
        finally:
            self.root.destroy()

    def run(self):
        """Start the GUI application"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.on_closing()


def main():
    """Main entry point"""
    app = RedesignedComprehensiveGUI()
    app.run()


if __name__ == "__main__":
    main()