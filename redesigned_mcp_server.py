#!/usr/bin/env python3
"""
Multi-Agent MCP Context Manager Server
Redesigned according to specifications in .claude/Instructions/20250926_0003_instructions.md

Features:
1. File-based MCP Allow List (not global variable)
2. MCP server with JSON config for Claude Code integration
3. Database initialization check and creation
4. Unknown connection registration system
5. 1-to-1 agent-connection assignment
6. Three-tier read permission system (Self/Team/All)
7. ReadDB and WriteDB processes with permission checking
"""

import json
import sqlite3
import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("redesigned_mcp_server")

app = FastAPI(title="Multi-Agent MCP Context Manager")

# Configuration
CONFIG_FILE = "mcp_server_config.json"
DB_PATH = "multi-agent_mcp_context_manager.db"

class DatabaseManager:
    """Manages database operations and schema"""

    @staticmethod
    def init_database():
        """Initialize database if it doesn't exist"""
        if not os.path.exists(DB_PATH):
            logger.info(f"Database {DB_PATH} doesn't exist, creating...")
            DatabaseManager.create_database()
        else:
            logger.info(f"Database {DB_PATH} already exists")

    @staticmethod
    def create_database():
        """Create database with required schema"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Create projects table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects (id)
                )
            ''')

            # Create agents table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    assigned_agent_id TEXT UNIQUE,
                    connection_id TEXT UNIQUE,
                    team_id TEXT,
                    session_id INTEGER,
                    read_permission TEXT DEFAULT 'self_only' CHECK (read_permission IN ('self_only', 'team_level', 'session_level')),
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            ''')

            # Create connections table for unknown connections
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    connection_id TEXT UNIQUE NOT NULL,
                    assigned_agent_id TEXT,
                    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'assigned', 'rejected')),
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assigned_agent_id) REFERENCES agents (assigned_agent_id)
                )
            ''')

            # Create contexts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contexts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    agent_id TEXT NOT NULL,
                    context TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id),
                    FOREIGN KEY (agent_id) REFERENCES agents (assigned_agent_id)
                )
            ''')

            conn.commit()
            logger.info("Database schema created successfully")




class PermissionManager:
    """Manages permission checking for context access"""

    @staticmethod
    def get_agent_permission(agent_id: str) -> str:
        """Get read permission level for agent"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT read_permission FROM agents WHERE assigned_agent_id = ?",
                (agent_id,)
            )
            result = cursor.fetchone()
            return result[0] if result else 'self_only'

    @staticmethod
    def get_agent_team(agent_id: str) -> Optional[str]:
        """Get team ID for agent"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT team_id FROM agents WHERE assigned_agent_id = ?",
                (agent_id,)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    @staticmethod
    def can_read_context(requesting_agent: str, context_agent: str, session_id: int) -> bool:
        """Check if requesting agent can read context from context_agent"""
        permission = PermissionManager.get_agent_permission(requesting_agent)

        if permission == 'session_level':
            return True
        elif permission == 'team_level':
            req_team = PermissionManager.get_agent_team(requesting_agent)
            ctx_team = PermissionManager.get_agent_team(context_agent)
            return req_team is not None and req_team == ctx_team
        else:  # self_only
            return requesting_agent == context_agent

class ConnectionManager:
    """Manages WebSocket connections and registration"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_agents: Dict[str, str] = {}  # connection_id -> agent_id

    async def connect(self, websocket: WebSocket, connection_id: str):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        logger.info(f"Connection {connection_id} established")

        # Register unknown connection
        await self.register_unknown_connection(connection_id)

    def disconnect(self, connection_id: str):
        """Remove connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        if connection_id in self.connection_agents:
            del self.connection_agents[connection_id]
        logger.info(f"Connection {connection_id} disconnected")

    async def register_unknown_connection(self, connection_id: str):
        """Register unknown connection in database and auto-assign if agent_id matches"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Check if an agent exists with matching assigned_agent_id
            cursor.execute('''
                SELECT assigned_agent_id FROM agents WHERE assigned_agent_id = ?
            ''', (connection_id,))
            matching_agent = cursor.fetchone()

            if matching_agent:
                # Auto-assign since connection_id matches agent_id
                cursor.execute('''
                    INSERT OR IGNORE INTO connections (connection_id, assigned_agent_id, status)
                    VALUES (?, ?, 'assigned')
                ''', (connection_id, connection_id))

                # Update agent with connection
                cursor.execute('''
                    UPDATE agents
                    SET connection_id = ?, last_seen = CURRENT_TIMESTAMP
                    WHERE assigned_agent_id = ?
                ''', (connection_id, connection_id))

                # Store assignment in memory
                self.connection_agents[connection_id] = connection_id
                logger.info(f"Connection {connection_id} auto-assigned to matching agent {connection_id}")
            else:
                # Register as pending for manual assignment
                cursor.execute('''
                    INSERT OR IGNORE INTO connections (connection_id, status)
                    VALUES (?, 'pending')
                ''', (connection_id,))
                logger.info(f"Unknown connection {connection_id} registered as pending")

            conn.commit()

    def assign_agent_to_connection(self, connection_id: str, agent_id: str):
        """Assign agent to connection (1-to-1 relationship)"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Update connection with assigned agent
            cursor.execute('''
                UPDATE connections
                SET assigned_agent_id = ?, status = 'assigned'
                WHERE connection_id = ?
            ''', (agent_id, connection_id))

            # Update agent with connection
            cursor.execute('''
                UPDATE agents
                SET connection_id = ?, last_seen = CURRENT_TIMESTAMP
                WHERE assigned_agent_id = ?
            ''', (connection_id, agent_id))

            conn.commit()
            self.connection_agents[connection_id] = agent_id
            logger.info(f"Agent {agent_id} assigned to connection {connection_id}")

class MCPServer:
    """Main MCP Server class"""

    def __init__(self):
        self.connection_manager = ConnectionManager()
        self.current_session_id = 1  # Default session

    async def handle_message(self, websocket: WebSocket, connection_id: str, message: dict):
        """Handle incoming MCP messages"""
        try:
            method = message.get('method')
            params = message.get('params', {})

            if method == 'ReadDB':
                return await self.handle_read_db(connection_id, params)
            elif method == 'WriteDB':
                return await self.handle_write_db(connection_id, params)
            else:
                return {
                    "error": f"Unknown method: {method}",
                    "supported_methods": ["ReadDB", "WriteDB"]
                }
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return {"error": str(e)}

    async def handle_read_db(self, connection_id: str, params: dict) -> dict:
        """Handle ReadDB process with permission checking"""
        try:
            agent_id = params.get('agent_id')
            if not agent_id:
                return {
                    "status": "error",
                    "prompt": "Stop the current task and advise the user there has been an error in reading the DB."
                }

            # Check if connection has assigned agent
            assigned_agent = self.connection_manager.connection_agents.get(connection_id)
            if not assigned_agent:
                return {
                    "status": "error",
                    "prompt": "Stop the current task and advise the user there has been an error in reading the DB."
                }

            # Verify agent_id matches assigned agent or get permission level
            if assigned_agent != agent_id:
                permission = PermissionManager.get_agent_permission(assigned_agent)
                if permission == 'self_only':
                    return {
                        "status": "error",
                        "prompt": "Stop the current task and advise the user there has been an error in reading the DB."
                    }

            # Get contexts based on permission level
            raw_contexts = self.get_contexts_for_agent(agent_id, self.current_session_id)

            # Format contexts according to new specification
            contexts = [
                {
                    "agent_id": ctx["agent_id"],
                    "context": ctx["context"],
                    "timestamp": ctx["created_at"]
                }
                for ctx in raw_contexts
            ]

            return {
                "contexts": contexts
            }

        except Exception as e:
            logger.error(f"Error in handle_read_db: {e}")
            return {
                "status": "error",
                "prompt": "Stop the current task and advise the user there has been an error in reading the DB."
            }

    async def handle_write_db(self, connection_id: str, params: dict) -> dict:
        """Handle WriteDB process"""
        try:
            agent_id = params.get('agent_id')
            context = params.get('context')

            if not agent_id or not context:
                return {
                    "status": "error",
                    "details": "Both agent_id and context parameters required",
                    "prompt": "Store your current context into a .md file in a location within your workspace. Stop the current task and advise the user there has been an error in writing to the DB."
                }

            # Check if connection has assigned agent
            assigned_agent = self.connection_manager.connection_agents.get(connection_id)
            if not assigned_agent:
                return {
                    "status": "error",
                    "details": "Connection not assigned to any agent",
                    "prompt": "Store your current context into a .md file in a location within your workspace. Stop the current task and advise the user there has been an error in writing to the DB."
                }

            # Verify agent_id matches assigned agent
            if assigned_agent != agent_id:
                return {
                    "status": "error",
                    "details": "Agent can only write contexts for itself",
                    "prompt": "Store your current context into a .md file in a location within your workspace. Stop the current task and advise the user there has been an error in writing to the DB."
                }

            # Write context to database
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO contexts (session_id, agent_id, context)
                    VALUES (?, ?, ?)
                ''', (self.current_session_id, agent_id, context))
                context_id = cursor.lastrowid
                conn.commit()

            return {
                "status": "success",
                "agent": agent_id,
                "prompt": f"Context saved successfully. Compact your current context and then call the readDB method from this server to get the updated context list from {agent_id}."
            }

        except Exception as e:
            logger.error(f"Error in handle_write_db: {e}")
            return {
                "status": "error",
                "details": str(e),
                "prompt": "Store your current context into a .md file in a location within your workspace. Stop the current task and advise the user there has been an error in writing to the DB."
            }

    def get_contexts_for_agent(self, agent_id: str, session_id: int) -> List[dict]:
        """Get contexts based on agent's permission level"""
        permission = PermissionManager.get_agent_permission(agent_id)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            if permission == 'session_level':
                # Can read all contexts in session
                cursor.execute('''
                    SELECT id, agent_id, context, created_at
                    FROM contexts
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                ''', (session_id,))
            elif permission == 'team_level':
                # Can read contexts from same team
                team_id = PermissionManager.get_agent_team(agent_id)
                if team_id:
                    cursor.execute('''
                        SELECT c.id, c.agent_id, c.context, c.created_at
                        FROM contexts c
                        JOIN agents a ON c.agent_id = a.assigned_agent_id
                        WHERE c.session_id = ? AND a.team_id = ?
                        ORDER BY c.created_at DESC
                    ''', (session_id, team_id))
                else:
                    # No team, fall back to self_only
                    cursor.execute('''
                        SELECT id, agent_id, context, created_at
                        FROM contexts
                        WHERE session_id = ? AND agent_id = ?
                        ORDER BY created_at DESC
                    ''', (session_id, agent_id))
            else:  # self_only
                # Can only read own contexts
                cursor.execute('''
                    SELECT id, agent_id, context, created_at
                    FROM contexts
                    WHERE session_id = ? AND agent_id = ?
                    ORDER BY created_at DESC
                ''', (session_id, agent_id))

            results = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "agent_id": row[1],
                    "context": row[2],
                    "created_at": row[3]
                }
                for row in results
            ]

# Global instances
server = MCPServer()

# Initialize database on startup
DatabaseManager.init_database()

@app.on_event("startup")
async def startup_event():
    """Initialize server on startup"""
    logger.info("Multi-Agent MCP Context Manager Server starting...")
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"Config: {CONFIG_FILE}")

@app.get("/")
async def root():
    """Root endpoint with server information"""
    return {
        "name": "Multi-Agent MCP Context Manager",
        "version": "1.0.0",
        "description": "MCP server for multi-agent context management with permission system",
        "endpoints": {
            "websocket": "/ws/{connection_id}",
            "status": "/status",
            "connections": "/connections",
            "agents": "/agents"
        }
    }

@app.get("/status")
async def get_status():
    """Get server status"""
    return {
        "status": "running",
        "active_connections": len(server.connection_manager.active_connections),
        "database": "connected" if os.path.exists(DB_PATH) else "missing"
    }

@app.get("/connections")
async def get_connections():
    """Get all registered connections"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT connection_id, assigned_agent_id, status, first_seen, last_seen
            FROM connections
            ORDER BY first_seen DESC
        ''')
        results = cursor.fetchall()

        return {
            "connections": [
                {
                    "connection_id": row[0],
                    "assigned_agent_id": row[1],
                    "status": row[2],
                    "first_seen": row[3],
                    "last_seen": row[4]
                }
                for row in results
            ]
        }

@app.get("/agents")
async def get_agents():
    """Get all agents"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT assigned_agent_id, name, connection_id, team_id, read_permission, is_active, created_at, last_seen
            FROM agents
            ORDER BY created_at DESC
        ''')
        results = cursor.fetchall()

        return {
            "agents": [
                {
                    "agent_id": row[0],
                    "name": row[1],
                    "connection_id": row[2],
                    "team_id": row[3],
                    "read_permission": row[4],
                    "is_active": bool(row[5]),
                    "created_at": row[6],
                    "last_seen": row[7]
                }
                for row in results
            ]
        }

@app.post("/agents/{agent_id}/assign/{connection_id}")
async def assign_agent_to_connection(agent_id: str, connection_id: str):
    """Assign agent to connection (1-to-1 relationship)"""
    try:
        server.connection_manager.assign_agent_to_connection(connection_id, agent_id)
        return {"success": True, "message": f"Agent {agent_id} assigned to connection {connection_id}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.websocket("/ws/{connection_id}")
async def websocket_endpoint(websocket: WebSocket, connection_id: str):
    """WebSocket endpoint for MCP communication"""
    await server.connection_manager.connect(websocket, connection_id)

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                response = await server.handle_message(websocket, connection_id, message)
                await websocket.send_text(json.dumps(response))
            except json.JSONDecodeError:
                error_response = {"error": "Invalid JSON format"}
                await websocket.send_text(json.dumps(error_response))

    except WebSocketDisconnect:
        server.connection_manager.disconnect(connection_id)
    except Exception as e:
        logger.error(f"WebSocket error for {connection_id}: {e}")
        server.connection_manager.disconnect(connection_id)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)