# Multi-Agent MCP Context Manager

A comprehensive context management system for Multi-Agent MCP (Model Context Protocol) interactions with advanced permission system, connection management, and Claude Code integration.

## 🎯 **COMPLETELY REDESIGNED SYSTEM** (September 28, 2025)

This system has been completely redesigned according to the latest specifications to include:

- **🚫 No Allowlist**: Removed allowlist functionality as per requirements
- **🔗 Enhanced MCP Server**: Direct Claude Code MCP server support with improved schema
- **🔐 Three-Tier Permissions**: Admin/User/Guest permission system
- **👥 Advanced Teams**: JSON-based team management with full CRUD operations
- **🌐 Smart Connection Management**: Redesigned connection assignment with dual-panel interface
- **📄 Context Management**: Full CRUD operations for contexts with search and export
- **📊 Live Status Bar**: Real-time server and database monitoring
- **🔄 Auto Database Setup**: Automatic database initialization and schema management

## 🚀 Key Features

### **Redesigned MCP Server** (`redesigned_mcp_server.py`)
- **No allowlist functionality** - removed as per specifications
- **Enhanced database schema** - supports teams, projects, sessions
- **Advanced permission system** with three levels:
  - `admin`: Can see all contexts in the same session
  - `user`: Can see contexts from agents in the same team(s) within the same session
  - `guest`: Can only see own contexts within the same session
- **Team-based access control** - JSON-stored team memberships
- **Auto connection registration** - registers and manages connections
- **Improved API endpoints** - comprehensive REST API for management
- **Simplified JSON responses** - Streamlined ReadDB/WriteDB formats

### **Redesigned Comprehensive GUI** (`redesigned_comprehensive_gui.py`)
- **📋 Data Format Instructions**:
  - Complete ReadDB/WriteDB documentation with examples
  - Updated format specifications with simplified JSON responses
  - Python client examples for WebSocket communication
- **📁 Enhanced Project & Sessions Management**:
  - Tree view with projects→sessions→agents hierarchy
  - Search and filter functionality for projects and sessions
  - Sorting by name, creation date, or agent count
  - Create/rename/delete projects and sessions with validation
  - Details & Management panel with inline editing
  - Agent assignment with conflict detection and validation
  - Auto-generated integer IDs with unique name enforcement
  - Agent filtering (show unassigned only, search by name/team)
- **🔗 Connection Assignment (Redesigned)**:
  - Left panel: Active connections with IP, timestamp, disconnect button
  - Right panel: Registered agents with permission levels and teams
  - Search/filter functionality, sortable columns
- **👥 Enhanced Agent Management**:
  - Agent List tab: Full-width grid with bulk operations
  - Teams tab: TreeView showing teams and members
  - Add/delete/permission changes with bulk selection
  - CSV export and Markdown file import functionality
- **📄 New Contexts Screen**:
  - View all contexts with project→session info
  - Full CRUD operations (view, edit, delete)
  - Search/filter and CSV export capabilities
- **📊 Live Status Bar**: Real-time monitoring of:
  - Active connections count, registered agents count
  - Database connection status, server status
  - Server IP address and port

### **Claude Code Integration**
Ready-to-use MCP configuration in `mcp_server_config.json`:

**Option 1: Server Only (Recommended)**
```json
{
  "mcpServers": {
    "multi-agent-context-manager": {
      "command": "python",
      "args": ["run_redesigned_mcp_server.py"],
      "env": {
        "MCP_SERVER_PORT": "8765",
        "MCP_SERVER_HOST": "127.0.0.1",
        "LAUNCH_GUI": "false"
      }
    }
  }
}
```

**Option 2: Server + Auto-Launch GUI**
```json
{
  "mcpServers": {
    "multi-agent-context-manager-with-gui": {
      "command": "python",
      "args": ["run_redesigned_mcp_server.py"],
      "env": {
        "MCP_SERVER_PORT": "8765",
        "MCP_SERVER_HOST": "127.0.0.1",
        "LAUNCH_GUI": "true"
      }
    }
  }
}
```

## Features

- **Hierarchical Organization**: Projects → Sessions → Teams → Agents
- **Advanced Team System**: Named teams with session association
- **Bulk Agent Management**: Multi-select and bulk operations
- **Database Management**: SQLite with soft deletes and foreign key constraints
- **Performance Optimizations**: Caching, connection pooling, lazy loading
- **Modern GUI**: Multi-tab interface with Agent Management and Team Management

## 📁 System Files

### **Core System**
- `redesigned_mcp_server.py` - **New MCP server with all specifications**
- `run_redesigned_mcp_server.py` - Server startup script
- `enhanced_gui_module.py` - Enhanced GUI with instructions
- `mcp_server_config.json` - Claude Code MCP configuration
- `mcp_allowlist.json` - File-based agent allow list

### **Legacy System** (maintained for compatibility)
- `main.py` - Original GUI application
- `mcp_server.py` - Original MCP server
- `multi_agent_mcp_server.py` - Legacy multi-agent server

### **System Files**
- **Core Redesigned System**:
  - `redesigned_mcp_server.py` - Main MCP server with new schema and no allowlist
  - `redesigned_comprehensive_gui.py` - Complete GUI redesign with all specifications
  - `run_redesigned_system.py` - Startup script for server + optional GUI
- **Legacy System** (maintained for compatibility):
  - `comprehensive_enhanced_gui.py` - Previous GUI version
  - `redesigned_mcp_server.py` - Previous server version
- **Documentation & Support**:
  - `docs/` - Comprehensive documentation
  - `scripts/` - Migration and utility scripts
  - `archive/` - Historical files and backups
  - `tests/` - Test suite

## 🚀 Quick Start

### **Redesigned System** (Latest - Recommended)

#### 1. Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Or use virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

#### 2. Start Redesigned System
**Server Only:**
```bash
python run_redesigned_system.py
```

**Server + GUI:**
```bash
set LAUNCH_GUI=true
python run_redesigned_system.py
```

**OR Start Components Separately:**
```bash
# Start server
python redesigned_mcp_server.py

# Start GUI (in another terminal)
python redesigned_comprehensive_gui.py
```

Server starts on `http://127.0.0.1:8765` with WebSocket endpoint `/ws/{connection_id}`

#### 3. Configure Claude Code
Choose one of these configurations:

**Server Only (Recommended):**
```json
{
  "mcpServers": {
    "multi-agent-context-manager": {
      "command": "python",
      "args": ["run_redesigned_system.py"],
      "env": {
        "LAUNCH_GUI": "false"
      }
    }
  }
}
```

**Server + Auto-Launch GUI:**
```json
{
  "mcpServers": {
    "multi-agent-context-manager-with-gui": {
      "command": "python",
      "args": ["run_redesigned_system.py"],
      "env": {
        "LAUNCH_GUI": "true"
      }
    }
  }
}
```

### **Legacy System**
```bash
python main.py
```

## 🧪 Testing

### **Test Redesigned System**
```bash
# Start server in one terminal
python run_redesigned_mcp_server.py

# Test API endpoints
curl http://127.0.0.1:8765/status
curl http://127.0.0.1:8765/connections
curl http://127.0.0.1:8765/agents

# Test with enhanced GUI
python enhanced_gui_module.py
```

### **WebSocket Testing**
Use the examples provided in the Enhanced GUI "Examples" tab, or:

```python
import asyncio
import websockets
import json

async def test_connection():
    uri = "ws://127.0.0.1:8765/ws/test_connection"
    async with websockets.connect(uri) as websocket:
        # Test ReadDB
        message = {
            "method": "ReadDB",
            "params": {"agent_id": "test_agent"}
        }
        await websocket.send(json.dumps(message))
        response = await websocket.recv()
        print("Response:", json.loads(response))

# asyncio.run(test_connection())
```

### **Legacy System Testing**
```bash
python test_new_features.py  # Test original features
```

## 📋 Usage Workflows

### **For Claude Code Users**
1. Add MCP configuration to Claude Code
2. Server auto-starts when Claude Code connects
3. Use ReadDB/WriteDB methods as documented in GUI

### **For GUI Users**
1. Start server: `python run_redesigned_mcp_server.py`
2. Launch comprehensive GUI: `python comprehensive_enhanced_gui.py`
3. **Allow List Management**: Add/remove agents from server allow list
4. **Agent Management**: Create agents, set permissions, assign teams
5. **Project & Session Setup**: Create projects and sessions
6. **Agent Assignment**: Assign agents to sessions and connections
7. **Monitor**: Real-time status and connection monitoring

### **For API Users**
1. Start server: `python run_redesigned_mcp_server.py`
2. Connect via WebSocket: `ws://127.0.0.1:8765/ws/{your_connection_id}`
3. Send JSON messages with ReadDB/WriteDB methods (see format below)
4. Manage assignments via REST API

## 📝 **Updated JSON Communication Formats**

The system now uses **simplified JSON formats** as specified in the latest requirements:

### **WriteDB (Save Context)**
**Send to server:**
```json
{
  "method": "WriteDB",
  "params": {
    "agent_id": "my_agent",
    "context": "I completed task X"
  }
}
```

**Success Response:**
```json
{
  "status": "success",
  "agent": "my_agent",
  "prompt": "Context saved successfully. Compact your current context and then call the readDB method from this server to get the updated context list from my_agent."
}
```

### **ReadDB (Get Contexts)**
**Send to server:**
```json
{
  "method": "ReadDB",
  "params": {
    "agent_id": "my_agent"
  }
}
```

**Success Response:**
```json
{
  "contexts": [
    {
      "context": "I completed task X",
      "timestamp": "2025-09-28T12:00:00"
    },
    {
      "context": "Working on feature Y",
      "timestamp": "2025-09-28T13:00:00"
    }
  ]
}
```

**Error Response (both methods):**
```json
{
  "status": "error",
  "prompt": "Stop the current task and advise the user there has been an error in reading the DB."
}
```

### **Key Improvements:**
- ✅ **Simplified responses** - Only essential data returned
- ✅ **Standardized errors** - Consistent error format with guidance
- ✅ **Action prompts** - Server tells client what to do next
- ✅ **Clean timestamps** - ISO format timestamps for context ordering

## 🔧 Configuration

### **Allow List Management**
Edit `mcp_allowlist.json`:
```json
{
  "allowed_agents": ["agent_1", "agent_2", "your_agent"],
  "description": "Controls which agents can connect",
  "version": "1.0",
  "last_updated": "2025-09-28T00:00:00Z"
}
```

### **Permission Levels**
Configure via GUI or direct database:
- **self_only**: Maximum security, agent isolation
- **team_level**: Team collaboration
- **session_level**: Full session access

### **Server Configuration**
Environment variables:
```bash
export MCP_SERVER_HOST=127.0.0.1
export MCP_SERVER_PORT=8765
```

## Database Schema

- **projects**: Project definitions with soft delete
- **sessions**: Sessions within projects
- **agents**: Agent instances with status tracking
- **contexts**: Context data with sequence tracking

## Architecture Versions

### 1. Original (Fixed)
- Fixed duplicate method issues
- Added input validation
- Improved error handling
- Added logging

### 2. MVC Refactored
- Separated Model, View, Controller
- Clean data access layer
- Better error handling
- Modular design

### 3. Performance Enhanced
- TTL caching system
- Connection pooling
- Lazy loading UI
- Background operations
- Performance monitoring

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit pull request

## License

MIT License - see LICENSE file for details