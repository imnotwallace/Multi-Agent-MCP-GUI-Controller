# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
# Start server only (recommended for MCP integration)
python run_redesigned_system.py

# Start server + GUI
set LAUNCH_GUI=true
python run_redesigned_system.py

# Alternative: Start components separately
python redesigned_mcp_server.py
python redesigned_comprehensive_gui.py
```

### Testing
```bash
# Run all tests
python tests/run_all_tests.py

# Run specific test modules
python -m unittest tests.test_data_model
python -m unittest tests.test_ui_functionality
python -m unittest tests.test_sorting_functionality
```

### Environment Setup
```bash
# Activate virtual environment
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Architecture Overview

This is a Multi-Agent MCP (Model Context Protocol) Context Manager with three main components:

### Core Files
- **`redesigned_mcp_server.py`** - Main MCP server with WebSocket endpoints and REST API
- **`redesigned_comprehensive_gui.py`** - 5-tab GUI for management (Projects, Sessions, Agents, Connections, Contexts)
- **`run_redesigned_system.py`** - Unified startup script with optional GUI launch

### Database Schema
The system uses SQLite with these key tables:
- **projects** - Top-level organization units
- **sessions** - Sub-units within projects
- **agents** - Registered agents with permission levels (full/team/self)
- **connections** - Active WebSocket connections
- **contexts** - Stored context data with timestamps
- **teams** - Team definitions for collaboration

### Permission System
Four-tier permission model:

- **project**: Access to all contexts within the project
- **session**: Access to all contexts in the session
- **team**: Access to contexts from agents in same team(s) as at the time of writing the context within session
- **self**: Access only to own contexts within session

### MCP Communication Protocol
The server accepts JSON messages via WebSocket:

**WriteDB (Save Context):**
```json
{
  "method": "WriteDB",
  "params": {
    "agent_id": "my_agent",
    "context": "Context content"
  }
}
```

**ReadDB (Get Contexts):**
```json
{
  "method": "ReadDB",
  "params": {
    "agent_id": "my_agent"
  }
}
```

### Claude Code Integration
Add to MCP settings:
```json
{
  "mcpServers": {
    "multi-agent-context-manager": {
      "command": "python",
      "args": ["run_redesigned_system.py"],
      "env": {
        "LAUNCH_GUI": "true"
      }
    }
  }
}
```

## Development Notes

- Server runs on `127.0.0.1:8765` with WebSocket endpoint `/ws/{connection_id}`
- Database auto-initializes on first run as `multi-agent_mcp_context_manager.db`
- GUI provides management interface for projects, sessions, agents, and contexts
- REST API available for connection and agent management
- Test suite covers data model, UI functionality, and sorting features