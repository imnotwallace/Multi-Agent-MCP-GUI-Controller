# Multi-Agent MCP Context Manager - Redesigned System Documentation

## Overview

This document describes the completely redesigned Multi-Agent MCP Context Manager system that implements all specifications from `.claude/Instructions/20250926_0003_instructions.md`.

## System Architecture

### Core Components

1. **Redesigned MCP Server** (`redesigned_mcp_server.py`)
   - File-based MCP Allow List (not global variable)
   - JSON configuration for Claude Code integration
   - Database initialization check and creation
   - Unknown connection registration system
   - 1-to-1 agent-connection assignment
   - Three-tier read permission system
   - ReadDB and WriteDB processes with permission checking

2. **Enhanced GUI Module** (`enhanced_gui_module.py`)
   - Clear data format instructions
   - Connection and agent assignment management
   - Visual permission configuration
   - Real-time status updates

3. **Configuration Files**
   - `mcp_server_config.json` - Claude Code MCP configuration
   - `mcp_allowlist.json` - File-based agent allow list

## Key Features Implemented

### 1. File-Based MCP Allow List
- **Location**: `mcp_allowlist.json` in server directory
- **Format**: JSON with allowed_agents array
- **No longer a global variable**

```json
{
  "allowed_agents": ["agent_1", "agent_2", "agent_3"],
  "description": "MCP Agent Allow List - Controls which agents can connect",
  "version": "1.0",
  "last_updated": "2025-09-28T00:00:00Z"
}
```

### 2. Claude Code Integration
- **Configuration file**: `mcp_server_config.json`
- **Direct MCP server support**
- **Proper JSON format for Claude Code**

```json
{
  "mcpServers": {
    "multi-agent-context-manager": {
      "command": "python",
      "args": ["run_redesigned_mcp_server.py"],
      "env": {
        "MCP_SERVER_PORT": "8765",
        "MCP_SERVER_HOST": "127.0.0.1"
      }
    }
  }
}
```

### 3. Database Initialization
- **Automatic check**: Server checks for database existence on startup
- **Auto-creation**: Creates `multi-agent_mcp_context_manager.db` if missing
- **Same schema**: Uses identical schema as main.py
- **No manual intervention required**

### 4. Unknown Connection Registration
- **Automatic registration**: First-time connections automatically registered as "pending"
- **Database tracking**: All unknown connections stored with timestamps
- **Status management**: pending → assigned → active workflow

### 5. 1-to-1 Agent Assignment
- **Strict relationship**: Each connection assigned to exactly one agent
- **Each agent**: Can only be assigned to one connection
- **GUI management**: Visual interface for assignment/unassignment
- **Bulk operations**: Support for bulk unassignment

### 6. GUI with Clear Instructions
- **Comprehensive tabs**: Connection setup, ReadDB, WriteDB, Examples
- **Data format guidance**: Exact JSON structures required
- **Live examples**: Working code samples
- **Visual assignment**: Drag-and-drop style interface

### 7. Three-Tier Read Permission System

#### Self-Only Permission
- **Access**: Agent can only read contexts it created
- **Use case**: Isolated agents, sensitive operations
- **Security**: Maximum isolation

#### Team-Level Permission
- **Access**: Agent can read contexts from same team_id
- **Use case**: Collaborative team work
- **Security**: Team-based isolation

#### Session-Level Permission
- **Access**: Agent can read all contexts in current session
- **Use case**: System oversight, coordination
- **Security**: Session-wide access

### 8. ReadDB Process
```json
{
  "method": "ReadDB",
  "params": {
    "agent_id": "your_agent_id"
  }
}
```

**Process Flow**:
1. Check current session
2. Validate agent_id in request
3. Verify connection assignment
4. Apply permission filtering
5. Return appropriate contexts

### 9. WriteDB Process
```json
{
  "method": "WriteDB",
  "params": {
    "agent_id": "your_agent_id",
    "context": "Context data here..."
  }
}
```

**Process Flow**:
1. Validate parameters
2. Check connection assignment
3. Verify agent ownership
4. Write to database with session_id
5. Return confirmation

## Database Schema

### Tables Created/Used

1. **projects** - Project management
2. **sessions** - Session tracking
3. **agents** - Agent definitions with permissions
4. **connections** - Unknown connection registration
5. **contexts** - Context data with permissions

### New Fields Added

- **agents.read_permission**: 'self_only', 'team_level', 'session_level'
- **agents.connection_id**: Links to active connection
- **connections.assigned_agent_id**: Links to assigned agent
- **connections.status**: 'pending', 'assigned', 'rejected'

## API Endpoints

### REST Endpoints
- `GET /` - Server information
- `GET /status` - Server status
- `GET /connections` - List all connections
- `GET /agents` - List all agents
- `POST /agents/{agent_id}/assign/{connection_id}` - Assign agent to connection

### WebSocket Endpoint
- `WS /ws/{connection_id}` - MCP communication endpoint

## Permission System Implementation

### Permission Checking Logic
```python
def can_read_context(requesting_agent: str, context_agent: str, session_id: int) -> bool:
    permission = get_agent_permission(requesting_agent)

    if permission == 'session_level':
        return True
    elif permission == 'team_level':
        return same_team(requesting_agent, context_agent)
    else:  # self_only
        return requesting_agent == context_agent
```

### Context Filtering
- **Database queries** filter at source
- **No post-processing** required
- **Efficient performance** with proper indexing

## Usage Instructions

### For Claude Code Integration

1. **Copy configuration** to Claude Code MCP settings:
```json
{
  "mcpServers": {
    "multi-agent-context-manager": {
      "command": "python",
      "args": ["run_redesigned_mcp_server.py"]
    }
  }
}
```

2. **Start server**: `python run_redesigned_mcp_server.py`

3. **Connect via WebSocket**: `ws://127.0.0.1:8765/ws/{your_connection_id}`

### For GUI Management

1. **Start enhanced GUI**: `python enhanced_gui_module.py`
2. **View instructions** in "Data Format Instructions" tab
3. **Manage assignments** in "Agent Assignment" tab

### For Direct API Access

1. **Check status**: `GET http://127.0.0.1:8765/status`
2. **List connections**: `GET http://127.0.0.1:8765/connections`
3. **Assign agent**: `POST http://127.0.0.1:8765/agents/{agent_id}/assign/{connection_id}`

## Security Features

### Connection Security
- **Registration required**: All connections must be registered
- **Assignment verification**: Only assigned connections can read/write
- **Agent isolation**: Agents cannot impersonate others

### Permission Enforcement
- **Database-level filtering**: Permissions enforced at query level
- **Real-time checking**: Permission verification on every request
- **Audit trail**: All access attempts logged

### Data Isolation
- **Session boundaries**: Data partitioned by session
- **Team boundaries**: Team-level access control
- **Agent boundaries**: Self-only access when required

## Testing the System

### Manual Testing Steps

1. **Start server**: `python run_redesigned_mcp_server.py`
2. **Check status**: Visit `http://127.0.0.1:8765/status`
3. **Open GUI**: `python enhanced_gui_module.py`
4. **Test WebSocket**: Use provided Python client example
5. **Verify permissions**: Test with different permission levels

### Automated Testing
- Integration with existing test suite
- Permission-specific test cases
- Connection assignment testing
- Data isolation verification

## Migration from Original System

### Compatibility
- **Database schema**: Compatible with existing database
- **Data preservation**: All existing data maintained
- **Permission defaults**: Existing agents get 'self_only' permission

### Migration Steps
1. Backup existing database
2. Run redesigned server
3. Database will auto-update schema if needed
4. Assign agents to connections via GUI
5. Configure permissions as needed

## Performance Considerations

### Optimizations
- **Connection pooling**: Efficient database connections
- **Query optimization**: Indexed permission queries
- **Caching**: Permission cache for frequently accessed data
- **Async operations**: Non-blocking WebSocket handling

### Scalability
- **Horizontal scaling**: Multiple server instances possible
- **Database optimization**: Proper indexing for large datasets
- **Memory management**: Efficient connection handling

## Troubleshooting

### Common Issues

**Connection not assigned**
- Solution: Use GUI to assign agent to connection

**Permission denied**
- Solution: Check agent's read_permission level

**Database not found**
- Solution: Server will auto-create on startup

**WebSocket connection failed**
- Solution: Ensure server is running on correct port

### Logging
- **Comprehensive logging**: All operations logged
- **Debug mode**: Available for troubleshooting
- **Error tracking**: Detailed error messages

## Future Enhancements

### Planned Features
- **Authentication system**: User-based access control
- **Advanced permissions**: Role-based permissions
- **Performance monitoring**: Real-time performance metrics
- **Clustering support**: Multi-server deployments

### Extensibility
- **Plugin system**: Modular permission plugins
- **Custom permissions**: User-defined permission levels
- **Integration APIs**: Third-party system integration
- **Monitoring hooks**: Custom monitoring solutions

This redesigned system fully implements all requirements from the original specification while maintaining compatibility with existing functionality and providing a foundation for future enhancements.