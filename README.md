# Multi-Agent MCP Context Manager

A comprehensive context management system for Multi-Agent MCP (Model Context Protocol) interactions with advanced permission system, connection management, and Claude Code integration.

## 🎯 **CURRENT APPLICATION FEATURES**

This system provides a complete Multi-Agent MCP Context Manager with:

- **🔗 MCP Server Integration**: Direct Claude Code MCP server support with optimized schema
- **🔐 Three-Tier Permissions**: Admin/User/Guest permission system for context access
- **👥 Advanced Teams**: JSON-based team management with full CRUD operations
- **📁 Project & Session Management**: Hierarchical organization with full CRUD operations
- **🌐 Smart Connection Management**: Advanced connection assignment with validation
- **📄 Context Management**: Full CRUD operations for contexts with search and filtering
- **📊 Live Status Monitoring**: Real-time server and database status tracking
- **🔄 Auto Database Setup**: Automatic database initialization and schema management

## 🚀 Core Components

### **MCP Server** (`redesigned_mcp_server.py`)
- **Enhanced database schema** - supports teams, projects, sessions, and agents
- **Advanced permission system** with three levels:
  - `admin`: Full access to all contexts in the session
  - `user`: Access to contexts from agents in the same team(s) within the session
  - `guest`: Access only to own contexts within the session
- **Team-based access control** - JSON-stored team memberships for collaboration
- **Auto connection registration** - automatic registration and management of connections
- **Comprehensive REST API** - full endpoints for connection and agent management
- **Simplified JSON responses** - streamlined ReadDB/WriteDB communication formats

### **Comprehensive GUI** (`redesigned_comprehensive_gui.py`)

The GUI provides five main functional areas accessible through tabs:

#### **📋 Data Format Instructions Tab**
- **ReadDB/WriteDB Documentation**: Complete API documentation with updated JSON formats
- **Process Specifications**: Detailed explanations of ReadDB and WriteDB operations
- **Python Examples**: Working WebSocket client code examples
- **Response Format Guide**: Comprehensive examples of success and error responses

#### **📁 Projects & Sessions Tab**
- **Hierarchical Tree View**: Projects → Sessions → Agents structure display
- **Search & Filter**: Real-time filtering of projects and sessions by name or description
- **Sorting Options**: Sort by name, creation date, or agent count
- **Full CRUD Operations**: Create, rename, and delete projects and sessions with validation
- **Details & Editing**: Inline editing panel for project/session names and descriptions
- **Agent Assignment**: Assign agents to sessions with conflict detection and validation
- **Status Validation**: Real-time validation messages for assignment operations

#### **🔗 Connection Assignment Tab**
- **Dual Panel Interface**: Left panel for active connections, right panel for registered agents
- **Connection Management**: View active connections with IP addresses and timestamps
- **Agent Registration**: View and manage registered agents with permission levels and teams
- **Search & Filter**: Filter agents and connections with real-time search
- **Assignment Operations**: Assign connections to agents with validation

#### **👥 Agent Management Tab**
- **Agent Directory**: Full-width grid displaying all registered agents
- **Bulk Operations**: Multi-select agents for bulk permission changes and team assignments
- **Teams Management**: TreeView showing team structure and memberships
- **Import/Export**: CSV export and Markdown file import for agent data
- **Permission Control**: Set admin/user/guest permissions for agents

#### **📄 Contexts Tab**
- **Context Browser**: View all contexts with project and session information
- **Full CRUD Operations**: Create, view, edit, and delete context entries
- **Advanced Search**: Filter contexts by agent, project, session, or content
- **Export Functionality**: CSV export capabilities for context data
- **Real-time Updates**: Live updates as contexts are added or modified

#### **📊 Status Bar**
- **Live Monitoring**: Real-time display of active connections and registered agents
- **Database Status**: Connection status and health monitoring
- **Server Information**: Display of server IP address and port
- **Performance Metrics**: Real-time system performance indicators

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

## 📁 Current Application Structure

### **Core Application Files**
- `redesigned_mcp_server.py` - **Main MCP server with enhanced schema and permissions**
- `redesigned_comprehensive_gui.py` - **Complete GUI with 5-tab interface**
- `run_redesigned_system.py` - **Unified startup script (server + optional GUI)**
- `run_redesigned_mcp_server.py` - Server-only startup script
- `permission_aware_context.py` - Permission-aware context management utilities

### **Configuration & Data**
- `mcp_server_config.json` - Claude Code MCP configuration templates
- `multi-agent_mcp_context_manager.db` - SQLite database (auto-created)
- `requirements.txt` - Python dependencies

### **Documentation & Support**
- `README.md` - This comprehensive documentation
- `CHANGELOG.md` - Version history and changes
- `.claude/Instructions/` - Implementation specifications and guidelines
- `archive/` - Historical files and previous versions
- `tests/` - Comprehensive test suite

### **Database Schema**
The application automatically creates and manages the following tables:
- **projects** - Project definitions with descriptions
- **sessions** - Sessions within projects for organization
- **agents** - Agent registrations with permissions and team memberships
- **connections** - Active WebSocket connections and assignments
- **contexts** - Context data with timestamps and associations
- **teams** - Team definitions for collaboration

## 🚀 Quick Start

### **Installation**
```bash
# Install dependencies
pip install -r requirements.txt

# Or use virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### **Starting the Application**

#### **Option 1: Integrated System (Recommended)**
**Server Only:**
```bash
python run_redesigned_system.py
```

**Server + GUI:**
```bash
set LAUNCH_GUI=true
python run_redesigned_system.py
```

#### **Option 2: Components Separately**
```bash
# Terminal 1: Start MCP Server
python redesigned_mcp_server.py

# Terminal 2: Start GUI (optional)
python redesigned_comprehensive_gui.py
```

#### **Option 3: Direct Server Start**
```bash
# Just the MCP server for Claude Code integration
python run_redesigned_mcp_server.py
```

**Server Details:**
- **Host**: `127.0.0.1`
- **Port**: `8765`
- **WebSocket Endpoint**: `/ws/{connection_id}`
- **REST API**: Available at `http://127.0.0.1:8765/`

### **Claude Code Integration**

Add one of these configurations to your Claude Code MCP settings:

#### **Server Only (Recommended)**
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

#### **Server + Auto-Launch GUI**
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

#### **Direct Server (Minimal)**
```json
{
  "mcpServers": {
    "mcp-context-manager": {
      "command": "python",
      "args": ["redesigned_mcp_server.py"]
    }
  }
}
```

## 🧪 Testing & Validation

### **Quick System Test**
```bash
# Start the complete system
python run_redesigned_system.py

# Or start server and GUI separately
python redesigned_mcp_server.py &
python redesigned_comprehensive_gui.py
```

### **API Endpoint Testing**
```bash
# Test REST API endpoints (server must be running)
curl http://127.0.0.1:8765/status
curl http://127.0.0.1:8765/connections
curl http://127.0.0.1:8765/agents
```

### **WebSocket Testing**
Use the examples provided in the GUI "Data Format Instructions" tab, or test manually:

```python
import asyncio
import websockets
import json

async def test_mcp_communication():
    uri = "ws://127.0.0.1:8765/ws/test_connection"

    async with websockets.connect(uri) as websocket:
        # Test WriteDB
        write_message = {
            "method": "WriteDB",
            "params": {
                "agent_id": "test_agent",
                "context": "Testing context write operation"
            }
        }
        await websocket.send(json.dumps(write_message))
        write_response = await websocket.recv()
        print("Write Response:", json.loads(write_response))

        # Test ReadDB
        read_message = {
            "method": "ReadDB",
            "params": {"agent_id": "test_agent"}
        }
        await websocket.send(json.dumps(read_message))
        read_response = await websocket.recv()
        print("Read Response:", json.loads(read_response))

# Run the test
# asyncio.run(test_mcp_communication())
```

### **GUI Feature Testing**
1. **Start the GUI**: `python redesigned_comprehensive_gui.py`
2. **Test Each Tab**:
   - **Data Format Instructions**: Review API documentation and examples
   - **Projects & Sessions**: Create projects, add sessions, assign agents
   - **Connection Assignment**: Monitor connections and assign to agents
   - **Agent Management**: Add agents, set permissions, manage teams
   - **Contexts**: View, edit, and manage context data

### **Database Testing**
```bash
# Check database schema and data
sqlite3 multi-agent_mcp_context_manager.db ".schema"
sqlite3 multi-agent_mcp_context_manager.db "SELECT * FROM projects;"
```

## 📋 Usage Workflows

### **For Claude Code Users**
1. **Add MCP Configuration**: Use one of the provided JSON configurations in your Claude Code settings
2. **Auto-Start**: Server automatically starts when Claude Code connects
3. **Use ReadDB/WriteDB**: Follow the formats documented in the GUI's "Data Format Instructions" tab
4. **Context Management**: Contexts are automatically organized by projects and sessions

### **For GUI Management**
1. **Start System**: `python run_redesigned_system.py` or `set LAUNCH_GUI=true && python run_redesigned_system.py`
2. **Project Setup**:
   - Use "Projects & Sessions" tab to create organizational structure
   - Create projects for different workflows or clients
   - Add sessions within projects for specific tasks or time periods
3. **Agent Management**:
   - Use "Agent Management" tab to register and configure agents
   - Set permission levels (admin/user/guest) based on access requirements
   - Organize agents into teams for collaboration
4. **Connection Monitoring**:
   - Use "Connection Assignment" tab to monitor active connections
   - Assign connections to registered agents
   - View connection history and status
5. **Context Review**:
   - Use "Contexts" tab to review all stored context data
   - Search and filter contexts by project, session, or agent
   - Export context data for reporting or analysis

### **For API Integration**
1. **Start Server**: `python redesigned_mcp_server.py`
2. **WebSocket Connection**: Connect to `ws://127.0.0.1:8765/ws/{your_connection_id}`
3. **API Communication**: Send ReadDB/WriteDB messages using documented JSON formats
4. **REST API**: Use HTTP endpoints for connection and agent management
5. **Database Access**: Direct SQLite access for advanced queries and reporting

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

### **Permission Levels**
Configure agent permissions via GUI or direct database access:
- **admin**: Full access to all contexts in the session
- **user**: Access to contexts from agents in the same team(s) within the session
- **guest**: Access only to own contexts within the session

### **Server Configuration**
Environment variables (optional):
```bash
export MCP_SERVER_HOST=127.0.0.1
export MCP_SERVER_PORT=8765
export LAUNCH_GUI=true  # Auto-launch GUI with server
```

### **Database Configuration**
The application automatically creates `multi-agent_mcp_context_manager.db` with the following configuration:
- **Auto-initialization**: Creates all required tables on first run
- **Schema migration**: Automatically updates existing databases
- **Foreign key constraints**: Maintains data integrity
- **Soft deletes**: Preserves historical data

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