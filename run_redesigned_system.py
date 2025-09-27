#!/usr/bin/env python3
"""
Startup script for the redesigned Multi-Agent MCP Context Manager
Can launch server only or server + GUI based on environment variable
"""

import os
import sys
import subprocess
import threading
import time

def start_server():
    """Start the redesigned MCP server"""
    print("Starting Redesigned MCP Server...")
    try:
        subprocess.run([sys.executable, "redesigned_mcp_server.py"], check=True)
    except KeyboardInterrupt:
        print("Server stopped by user")
    except Exception as e:
        print(f"Server error: {e}")

def start_gui():
    """Start the redesigned comprehensive GUI"""
    print("Starting Redesigned Comprehensive GUI...")
    try:
        subprocess.run([sys.executable, "redesigned_comprehensive_gui.py"], check=True)
    except KeyboardInterrupt:
        print("GUI stopped by user")
    except Exception as e:
        print(f"GUI error: {e}")

def main():
    """Main entry point"""
    launch_gui = os.environ.get('LAUNCH_GUI', 'false').lower() == 'true'

    if launch_gui:
        print("=== Multi-Agent MCP Context Manager (Redesigned) ===")
        print("Starting server + GUI mode...")

        # Start server in background thread
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()

        # Wait a bit for server to start
        time.sleep(2)

        # Start GUI in main thread
        start_gui()
    else:
        print("=== Multi-Agent MCP Context Manager Server (Redesigned) ===")
        print("Starting server only mode...")
        start_server()

if __name__ == "__main__":
    main()