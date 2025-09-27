#!/usr/bin/env python3
"""
Startup script for the redesigned Multi-Agent MCP Context Manager Server
"""

import sys
import os
import logging
import uvicorn
import subprocess
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import the redesigned server
from redesigned_mcp_server import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_server_runner")

def launch_gui():
    """Launch the enhanced GUI if requested"""
    if os.getenv("LAUNCH_GUI", "false").lower() in ("true", "1", "yes", "on"):
        gui_script = current_dir / "comprehensive_enhanced_gui.py"
        if gui_script.exists():
            try:
                logger.info("Launching Enhanced GUI...")
                # Use Popen to start GUI in background without blocking server
                gui_process = subprocess.Popen(
                    [sys.executable, str(gui_script)],
                    cwd=str(current_dir),
                    creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                )
                logger.info(f"Enhanced GUI launched with PID: {gui_process.pid}")
                return gui_process
            except Exception as e:
                logger.warning(f"Failed to launch GUI: {e}")
        else:
            logger.warning(f"GUI script not found: {gui_script}")
    return None

def main():
    """Main entry point"""
    logger.info("Starting Multi-Agent MCP Context Manager Server (Redesigned)")

    # Server configuration
    host = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_SERVER_PORT", "8765"))
    launch_gui_flag = os.getenv("LAUNCH_GUI", "false").lower() in ("true", "1", "yes", "on")

    logger.info(f"Server will start on {host}:{port}")
    logger.info("Database will be initialized if it doesn't exist")
    logger.info("WebSocket endpoint: /ws/{connection_id}")
    logger.info("Status endpoint: /status")
    logger.info("Connections endpoint: /connections")
    logger.info("Agents endpoint: /agents")

    if launch_gui_flag:
        logger.info("GUI auto-launch enabled (LAUNCH_GUI=true)")
    else:
        logger.info("GUI auto-launch disabled (set LAUNCH_GUI=true to enable)")

    # Launch GUI if requested
    gui_process = launch_gui()

    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        if gui_process:
            logger.info("Terminating GUI process...")
            try:
                gui_process.terminate()
                gui_process.wait(timeout=5)
            except:
                gui_process.kill()
    except Exception as e:
        logger.error(f"Server error: {e}")
        if gui_process:
            logger.info("Terminating GUI process due to server error...")
            try:
                gui_process.terminate()
            except:
                pass
        sys.exit(1)

if __name__ == "__main__":
    main()