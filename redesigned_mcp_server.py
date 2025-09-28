#!/usr/bin/env python3
"""
Multi-Agent MCP Context Manager Server
Redesigned according to specifications in .claude/Instructions/20250928_0159_instructions.md

Features:
1. No allowlist functionality (removed as per requirements)
2. MCP server with JSON config for Claude Code integration
3. Database initialization with proper schema
4. Connection registration and management
5. Agent-connection assignment system
6. Three-tier permission system (all/team/self)
7. ReadDB and WriteDB processes with permission checking
8. Teams and project management
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

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError:
        RecursiveCharacterTextSplitter = None
        
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("redesigned_mcp_server")

# Try to load sqlite-vec extension
try:
    import sqlite_vec
    VEC_AVAILABLE = True
    logger.info("sqlite-vec extension available")
except ImportError:
    VEC_AVAILABLE = False
    logger.warning("sqlite-vec not available. Vector search will be disabled.")

# Try to load nomic embedding model
try:
    from nomic import embed
    import numpy as np
    NOMIC_AVAILABLE = True
    logger.info("nomic.ai embedding model available")
except ImportError:
    NOMIC_AVAILABLE = False
    logger.warning("nomic.ai not installed. Vector embeddings will be disabled.")



app = FastAPI(title="Multi-Agent MCP Context Manager")

# Configuration
CONFIG_FILE = "mcp_server_config.json"
DB_PATH = "multi-agent_mcp_context_manager.db"

# Chunking configuration (4025 chars as per instructions)
CHUNK_SIZE = 3500  # 3500 characters as specified in instructions
OVERLAP_PERCENTAGE = 0.15
CHUNK_OVERLAP = int(CHUNK_SIZE * OVERLAP_PERCENTAGE)  # 525 characters

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
            DatabaseManager.update_schema()

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

            # Create teams table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teams (
                    team_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create agents table with updated schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT UNIQUE NOT NULL,
                    name TEXT,
                    permission_level TEXT DEFAULT 'team' CHECK (permission_level IN ('project', 'session', 'team', 'self')),
                    teams TEXT,  -- JSON array of team IDs
                    connection_id TEXT UNIQUE,
                    session_id INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            ''')

            # Create connections table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    connection_id TEXT UNIQUE NOT NULL,
                    ip_address TEXT,
                    assigned_agent_id TEXT,
                    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'assigned', 'rejected')),
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assigned_agent_id) REFERENCES agents (agent_id)
                )
            ''')

            # Create contexts table with updated schema (metadata table)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contexts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    session_id INTEGER NOT NULL,
                    project_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id),
                    FOREIGN KEY (session_id) REFERENCES sessions (id),
                    FOREIGN KEY (project_id) REFERENCES projects (id)
                )
            ''')

            # Create context-chunks table for individual chunks
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS context_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    context_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_content TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    session_id INTEGER NOT NULL,
                    project_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (context_id) REFERENCES contexts (id),
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id),
                    FOREIGN KEY (session_id) REFERENCES sessions (id),
                    FOREIGN KEY (project_id) REFERENCES projects (id)
                )
            ''')

            # Create default project and session
            cursor.execute('''
                INSERT OR IGNORE INTO projects (id, name, description)
                VALUES (1, 'Default Project', 'Default project for context management')
            ''')

            cursor.execute('''
                INSERT OR IGNORE INTO sessions (id, project_id, name)
                VALUES (1, 1, 'Default Session')
            ''')

            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_agent_id ON agents(agent_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_session_id ON agents(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_permission_level ON agents(permission_level)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_teams ON agents(teams)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_is_active ON agents(is_active)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_contexts_agent_id ON contexts(agent_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_contexts_session_id ON contexts(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_contexts_project_id ON contexts(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_contexts_created_at ON contexts(created_at)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_context_chunks_context_id ON context_chunks(context_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_context_chunks_agent_id ON context_chunks(agent_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_context_chunks_session_id ON context_chunks(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_context_chunks_project_id ON context_chunks(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_context_chunks_created_at ON context_chunks(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_context_chunks_chunk_index ON context_chunks(chunk_index)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_connections_connection_id ON connections(connection_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_connections_assigned_agent_id ON connections(assigned_agent_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_connections_status ON connections(status)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_name ON sessions(name)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_teams_team_id ON teams(team_id)')

            # Create vector embeddings table if sqlite-vec is available
            if VEC_AVAILABLE:
                DatabaseManager._create_vector_tables(cursor)

            conn.commit()
            logger.info("Database schema and indexes created successfully")

    @staticmethod
    def _create_vector_tables(cursor):
        """Create vector embedding tables using sqlite-vec"""
        try:
            # Enable extension loading and load sqlite-vec extension
            cursor.connection.enable_load_extension(True)
            cursor.connection.load_extension(sqlite_vec.loadable_path())

            # Create table for vector embeddings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS context_chunk_embeddings (
                    chunk_id INTEGER PRIMARY KEY,
                    embedding BLOB,
                    FOREIGN KEY (chunk_id) REFERENCES context_chunks (id)
                )
            ''')

            # Create vector index using sqlite-vec
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS context_chunk_embeddings_vec
                USING vec0(
                    embedding float[256]
                )
            ''')

            logger.info("Vector embedding tables created successfully")

        except Exception as e:
            logger.error(f"Failed to create vector tables: {e}")
            raise

    @staticmethod
    def update_schema():
        """Update existing database schema if needed"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Check if teams table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='teams'")
            if not cursor.fetchone():
                cursor.execute('''
                    CREATE TABLE teams (
                        team_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                logger.info("Created teams table")

            # Check if agents table exists and update if needed
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agents'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(agents)")
                columns = [col[1] for col in cursor.fetchall()]

                if 'permission_level' not in columns:
                    cursor.execute("ALTER TABLE agents ADD COLUMN permission_level TEXT DEFAULT 'team'")
                    logger.info("Added permission_level column")

                if 'teams' not in columns:
                    cursor.execute("ALTER TABLE agents ADD COLUMN teams TEXT")
                    logger.info("Added teams column")

                if 'session_id' not in columns:
                    cursor.execute("ALTER TABLE agents ADD COLUMN session_id INTEGER")
                    logger.info("Added session_id column")

            # Check if contexts table exists and update if needed
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contexts'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(contexts)")
                context_columns = [col[1] for col in cursor.fetchall()]

                # Check if this is old schema and needs migration
                has_old_structure = 'context' in context_columns and 'project' in context_columns

                if has_old_structure:
                    # Migrate to new structure
                    logger.info("Migrating contexts table to new chunked structure")

                    # Create new tables
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS contexts_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            agent_id TEXT NOT NULL,
                            session_id INTEGER NOT NULL,
                            project_id INTEGER NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (agent_id) REFERENCES agents (agent_id),
                            FOREIGN KEY (session_id) REFERENCES sessions (id),
                            FOREIGN KEY (project_id) REFERENCES projects (id)
                        )
                    ''')

                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS context_chunks (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            context_id INTEGER NOT NULL,
                            chunk_index INTEGER NOT NULL,
                            chunk_content TEXT NOT NULL,
                            agent_id TEXT NOT NULL,
                            session_id INTEGER NOT NULL,
                            project_id INTEGER NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (context_id) REFERENCES contexts (id),
                            FOREIGN KEY (agent_id) REFERENCES agents (agent_id),
                            FOREIGN KEY (session_id) REFERENCES sessions (id),
                            FOREIGN KEY (project_id) REFERENCES projects (id)
                        )
                    ''')

                    # Migrate old data
                    cursor.execute("SELECT context_id, agent_id, context, timestamp FROM contexts")
                    old_contexts = cursor.fetchall()

                    for old_context in old_contexts:
                        old_id, agent_id, context_text, timestamp = old_context

                        # Insert into new contexts table (metadata only)
                        cursor.execute('''
                            INSERT INTO contexts_new (agent_id, session_id, project_id, created_at)
                            VALUES (?, 1, 1, ?)
                        ''', (agent_id, timestamp))
                        new_context_id = cursor.lastrowid

                        # Insert into context_chunks table
                        cursor.execute('''
                            INSERT INTO context_chunks
                            (context_id, chunk_index, chunk_content, agent_id, session_id, project_id, created_at)
                            VALUES (?, 0, ?, ?, 1, 1, ?)
                        ''', (new_context_id, context_text, agent_id, timestamp))

                    # Drop old table and rename new one
                    cursor.execute("DROP TABLE contexts")
                    cursor.execute("ALTER TABLE contexts_new RENAME TO contexts")

                    logger.info("Migration completed successfully")
            else:
                # Create new tables if they don't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS contexts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id TEXT NOT NULL,
                        session_id INTEGER NOT NULL,
                        project_id INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (agent_id) REFERENCES agents (agent_id),
                        FOREIGN KEY (session_id) REFERENCES sessions (id),
                        FOREIGN KEY (project_id) REFERENCES projects (id)
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS context_chunks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        context_id INTEGER NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        chunk_content TEXT NOT NULL,
                        agent_id TEXT NOT NULL,
                        session_id INTEGER NOT NULL,
                        project_id INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (context_id) REFERENCES contexts (id),
                        FOREIGN KEY (agent_id) REFERENCES agents (agent_id),
                        FOREIGN KEY (session_id) REFERENCES sessions (id),
                        FOREIGN KEY (project_id) REFERENCES projects (id)
                    )
                ''')

                logger.info("Created new contexts and context_chunks tables")

            # Ensure indexes exist (idempotent operation)
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_agent_id ON agents(agent_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_session_id ON agents(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_permission_level ON agents(permission_level)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_teams ON agents(teams)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_is_active ON agents(is_active)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_contexts_agent_id ON contexts(agent_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_contexts_session_id ON contexts(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_contexts_project_id ON contexts(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_contexts_created_at ON contexts(created_at)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_context_chunks_context_id ON context_chunks(context_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_context_chunks_agent_id ON context_chunks(agent_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_context_chunks_session_id ON context_chunks(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_context_chunks_project_id ON context_chunks(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_context_chunks_created_at ON context_chunks(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_context_chunks_chunk_index ON context_chunks(chunk_index)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_connections_connection_id ON connections(connection_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_connections_assigned_agent_id ON connections(assigned_agent_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_connections_status ON connections(status)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_name ON sessions(name)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_teams_team_id ON teams(team_id)')

            # Create vector embeddings table if sqlite-vec is available and not exists
            if VEC_AVAILABLE:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='context_chunk_embeddings'")
                if not cursor.fetchone():
                    try:
                        DatabaseManager._create_vector_tables(cursor)
                        logger.info("Added vector embedding tables during schema update")
                    except Exception as e:
                        logger.warning(f"Failed to add vector tables during update: {e}")

            conn.commit()


class TextChunkingUtility:
    """Utility class for text chunking with langchain or fallback"""

    @staticmethod
    def chunk_text(text: str) -> List[str]:
        """Split text into chunks using langchain or simple fallback"""
        if RecursiveCharacterTextSplitter:
            # Use langchain for smart chunking
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
                length_function=len,
            )
            chunks = text_splitter.split_text(text)
        else:
            # Fallback: simple chunking with overlap
            chunks = TextChunkingUtility._simple_chunk_text(text)

        return chunks

    @staticmethod
    def _simple_chunk_text(text: str) -> List[str]:
        """Simple text chunking fallback when langchain is not available"""
        if len(text) <= CHUNK_SIZE:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + CHUNK_SIZE

            # If this is not the last chunk, try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings within the last 100 characters
                last_period = text.rfind('.', start, end)
                last_exclamation = text.rfind('!', start, end)
                last_question = text.rfind('?', start, end)

                # Use the latest sentence ending if found
                sentence_end = max(last_period, last_exclamation, last_question)
                if sentence_end > start + (CHUNK_SIZE * 0.5):  # Don't make chunks too small
                    end = sentence_end + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start forward with overlap consideration
            start = max(start + 1, end - CHUNK_OVERLAP)

            # Prevent infinite loop
            if start >= len(text):
                break

        return chunks


class VectorEmbeddingUtility:
    """Utility class for vector embeddings using nomic.ai"""

    _model_initialized = False

    @staticmethod
    def initialize_model():
        """Initialize the nomic embedding model"""
        if not NOMIC_AVAILABLE:
            logger.warning("Cannot initialize nomic model - not available")
            return False

        try:
            # Initialize the model with a test embedding
            output = embed.text(
                texts=["Initialise nomic embedding model"],
                model='nomic-embed-text-v1.5',
                task_type="search_document",
                inference_mode='local',
                dimensionality=256,
            )
            logger.info(f"Nomic model initialized successfully: {output.get('usage', {})}")
            VectorEmbeddingUtility._model_initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize nomic model: {e}")
            return False

    @staticmethod
    def vectorise_text_chunks(chunks: List[str]) -> np.ndarray:
        """Vectorise text chunks using nomic embedding model"""
        if not NOMIC_AVAILABLE or not VectorEmbeddingUtility._model_initialized:
            raise RuntimeError("Nomic model not available or not initialized")

        try:
            output = embed.text(
                texts=chunks,
                model='nomic-embed-text-v1.5',
                task_type="search_document",
                inference_mode='local',
                dimensionality=256,
            )

            logger.info(f"Vectorized {len(chunks)} chunks: {output.get('usage', {})}")
            embeddings = np.array(output['embeddings'])
            return embeddings

        except Exception as e:
            logger.error(f"Failed to vectorize chunks: {e}")
            raise

    @staticmethod
    def store_embeddings(chunk_ids: List[int], embeddings: np.ndarray):
        """Store embeddings in the vector database"""
        if not VEC_AVAILABLE:
            logger.warning("Cannot store embeddings - sqlite-vec not available")
            return

        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.enable_load_extension(True)
                conn.load_extension(sqlite_vec.loadable_path())
                cursor = conn.cursor()

                for chunk_id, embedding in zip(chunk_ids, embeddings):
                    # Convert numpy array to bytes for storage
                    embedding_bytes = embedding.astype(np.float32).tobytes()

                    # Store in the regular table
                    cursor.execute('''
                        INSERT OR REPLACE INTO context_chunk_embeddings (chunk_id, embedding)
                        VALUES (?, ?)
                    ''', (chunk_id, embedding_bytes))

                    # Also store in the vector table for searching
                    cursor.execute('''
                        INSERT OR REPLACE INTO context_chunk_embeddings_vec (rowid, embedding)
                        VALUES (?, ?)
                    ''', (chunk_id, embedding.astype(np.float32).tobytes()))

                conn.commit()
                logger.info(f"Stored {len(chunk_ids)} embeddings in vector database")

        except Exception as e:
            logger.error(f"Failed to store embeddings: {e}")
            raise


class PermissionManager:
    """Manages permission checking for context access"""

    @staticmethod
    def get_agent_permission(agent_id: str) -> str:
        """Get permission level for agent"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT permission_level FROM agents WHERE agent_id = ?",
                (agent_id,)
            )
            result = cursor.fetchone()
            return result[0] if result else 'guest'

    @staticmethod
    def get_agent_teams(agent_id: str) -> List[str]:
        """Get team IDs for agent"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT teams FROM agents WHERE agent_id = ?",
                (agent_id,)
            )
            result = cursor.fetchone()
            if result and result[0]:
                try:
                    return json.loads(result[0])
                except json.JSONDecodeError:
                    return []
            return []

    @staticmethod
    def get_agent_session(agent_id: str) -> Optional[str]:
        """Get current session for agent based on project/session context"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT session_id FROM agents WHERE agent_id = ?",
                (agent_id,)
            )
            result = cursor.fetchone()
            return str(result[0]) if result and result[0] else None

    @staticmethod
    def get_agent_project(agent_id: str) -> Optional[str]:
        """Get current project for agent based on session"""
        session_id = PermissionManager.get_agent_session(agent_id)
        if not session_id:
            return None

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT project_id FROM sessions WHERE id = ?",
                (session_id,)
            )
            result = cursor.fetchone()
            return str(result[0]) if result and result[0] else None

    @staticmethod
    def get_context_project(context_agent: str, context_session: str) -> Optional[str]:
        """Get project for a context based on session"""
        if not context_session:
            return None

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT project_id FROM sessions WHERE id = ?",
                (context_session,)
            )
            result = cursor.fetchone()
            return str(result[0]) if result and result[0] else None

    @staticmethod
    def can_read_context(requesting_agent: str, context_agent: str, context_session: str) -> bool:
        """Check if requesting agent can read context from context_agent"""
        permission = PermissionManager.get_agent_permission(requesting_agent)
        requesting_session = PermissionManager.get_agent_session(requesting_agent)

        if permission == 'session':
            # Session can see all contexts in the same session
            return context_session == requesting_session
        elif permission == 'project':
            # Project can see all contexts in the same project
            requesting_project = PermissionManager.get_agent_project(requesting_agent)
            context_project = PermissionManager.get_context_project(context_agent, context_session)
            return context_project == requesting_project
        elif permission == 'team':
            # Team can see contexts from agents in the same team(s) within the same session
            if context_session != requesting_session:
                return False
            req_teams = PermissionManager.get_agent_teams(requesting_agent)
            ctx_teams = PermissionManager.get_agent_teams(context_agent)
            return bool(set(req_teams) & set(ctx_teams)) or requesting_agent == context_agent
        else:  # self
            # Self can only see own contexts within the same session
            return requesting_agent == context_agent and context_session == requesting_session

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

            # Check if an agent exists with matching agent_id
            cursor.execute('''
                SELECT agent_id FROM agents WHERE agent_id = ?
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
                    WHERE agent_id = ?
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
                WHERE agent_id = ?
            ''', (connection_id, agent_id))

            conn.commit()
            self.connection_agents[connection_id] = agent_id
            logger.info(f"Agent {agent_id} assigned to connection {connection_id}")

class MCPServer:
    """Main MCP Server class"""

    def __init__(self):
        self.connection_manager = ConnectionManager()
        self.current_session_id = 1  # Default session
        # Initialize vector embedding model
        if NOMIC_AVAILABLE:
            VectorEmbeddingUtility.initialize_model()

    async def handle_message(self, websocket: WebSocket, connection_id: str, message: dict):
        """Handle incoming MCP messages"""
        try:
            method = message.get('method')
            params = message.get('params', {})

            if method == 'ReadDB':
                return await self.handle_read_db(connection_id, params)
            elif method == 'WriteDB':
                return await self.handle_write_db(connection_id, params)
            elif method == 'VectoriseChunks':
                return await self.handle_vectorise_chunks(connection_id, params)
            else:
                return {
                    "error": f"Unknown method: {method}",
                    "supported_methods": ["ReadDB", "WriteDB", "VectoriseChunks"]
                }
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return {"error": str(e)}

    async def handle_read_db(self, connection_id: str, params: dict) -> dict:
        """Handle ReadDB process with chunk retrieval and permission checking"""
        try:
            agent_id = params.get('agent_id')
            since_timestamp = params.get('since')  # Optional ISO 8601 timestamp
            permission_level_override = params.get('permission_level')  # Optional permission override

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

            # Verify agent_id matches assigned agent or check permission
            if assigned_agent != agent_id:
                permission = PermissionManager.get_agent_permission(assigned_agent)
                if permission == 'self':
                    return {
                        "status": "error",
                        "prompt": "Stop the current task and advise the user there has been an error in reading the DB."
                    }

            # Get chunks based on permission level
            chunks = self.get_chunks_for_agent(agent_id, since_timestamp, permission_level_override)

            return {
                "contexts": chunks
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

            # Get agent's current session and project
            session_id = 1  # Default session for now
            project_id = 1  # Default project for now

            # Chunk the context text
            chunks = TextChunkingUtility.chunk_text(context)

            # Write context metadata and chunks to database
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                # Insert context metadata
                cursor.execute('''
                    INSERT INTO contexts (agent_id, session_id, project_id)
                    VALUES (?, ?, ?)
                ''', (agent_id, session_id, project_id))
                context_id = cursor.lastrowid

                # Insert all chunks
                chunk_ids = []
                for chunk_index, chunk_content in enumerate(chunks):
                    cursor.execute('''
                        INSERT INTO context_chunks
                        (context_id, chunk_index, chunk_content, agent_id, session_id, project_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (context_id, chunk_index, chunk_content, agent_id, session_id, project_id))
                    chunk_ids.append(cursor.lastrowid)

                conn.commit()

            # Schedule asynchronous vectorization (non-blocking)
            asyncio.create_task(self.vectorise_chunks_async(chunk_ids))

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

    async def vectorise_chunks_async(self, chunk_ids: List[int]):
        """Asynchronously vectorise chunks"""
        try:
            logger.info(f"Starting vectorization for {len(chunk_ids)} chunks")

            if not NOMIC_AVAILABLE or not VectorEmbeddingUtility._model_initialized:
                logger.warning("Vectorization skipped - nomic model not available")
                return

            # Get chunk contents
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                placeholders = ','.join(['?' for _ in chunk_ids])
                cursor.execute(f'''
                    SELECT id, chunk_content FROM context_chunks
                    WHERE id IN ({placeholders})
                ''', chunk_ids)
                results = cursor.fetchall()

            if not results:
                logger.warning("No chunks found for vectorization")
                return

            # Extract texts and maintain ID mapping
            chunk_texts = [row[1] for row in results]
            chunk_id_order = [row[0] for row in results]

            # Vectorize chunks
            embeddings = VectorEmbeddingUtility.vectorise_text_chunks(chunk_texts)

            # Store embeddings
            VectorEmbeddingUtility.store_embeddings(chunk_id_order, embeddings)

            logger.info(f"Vectorization completed for {len(chunk_ids)} chunks")

        except Exception as e:
            logger.error(f"Error in vectorization: {e}")

    async def handle_vectorise_chunks(self, connection_id: str, params: dict) -> dict:
        """Handle VectoriseChunks method call"""
        try:
            chunk_ids = params.get('chunk_ids', [])

            if not chunk_ids:
                return {
                    "status": "error",
                    "message": "chunk_ids parameter required"
                }

            # Validate chunk_ids are integers
            try:
                chunk_ids = [int(cid) for cid in chunk_ids]
            except (ValueError, TypeError):
                return {
                    "status": "error",
                    "message": "chunk_ids must be a list of integers"
                }

            # Start vectorization
            await self.vectorise_chunks_async(chunk_ids)

            return {
                "status": "success",
                "message": f"Vectorized {len(chunk_ids)} chunks"
            }

        except Exception as e:
            logger.error(f"Error in handle_vectorise_chunks: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def get_contexts_for_agent(self, agent_id: str) -> List[dict]:
        """Get contexts based on agent's permission level"""
        permission = PermissionManager.get_agent_permission(agent_id)
        agent_session = PermissionManager.get_agent_session(agent_id)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            if permission == 'project':
                # Project can read all contexts in the project
                agent_project = PermissionManager.get_agent_project(agent_id)
                cursor.execute('''
                    SELECT c.context_id, c.agent_id, c.context, c.timestamp
                    FROM contexts c
                    JOIN sessions s ON c.session = s.id
                    WHERE s.project_id = ?
                    ORDER BY c.timestamp DESC
                ''', (agent_project,))
            elif permission == 'session':
                # Session can read all contexts in the session
                cursor.execute('''
                    SELECT context_id, agent_id, context, timestamp
                    FROM contexts
                    WHERE session = ?
                    ORDER BY timestamp DESC
                ''', (agent_session,))
            elif permission == 'team':
                # Team can read contexts from agents in the same team(s)
                agent_teams = PermissionManager.get_agent_teams(agent_id)
                if agent_teams:
                    # Get contexts from team members or own contexts
                    team_placeholders = ','.join(['?' for _ in agent_teams])
                    cursor.execute(f'''
                        SELECT DISTINCT c.context_id, c.agent_id, c.context, c.timestamp
                        FROM contexts c
                        JOIN agents a ON c.agent_id = a.agent_id
                        WHERE c.session = ? AND (
                            c.agent_id = ? OR
                            json_extract(a.teams, '$') IN ({team_placeholders})
                        )
                        ORDER BY c.timestamp DESC
                    ''', [agent_session, agent_id] + agent_teams)
                else:
                    # No team, only own contexts
                    cursor.execute('''
                        SELECT context_id, agent_id, context, timestamp
                        FROM contexts
                        WHERE session = ? AND agent_id = ?
                        ORDER BY timestamp DESC
                    ''', (agent_session, agent_id))
            else:  # self
                # Self can only read own contexts
                cursor.execute('''
                    SELECT context_id, agent_id, context, timestamp
                    FROM contexts
                    WHERE session = ? AND agent_id = ?
                    ORDER BY timestamp DESC
                ''', (agent_session, agent_id))

            results = cursor.fetchall()
            return [
                {
                    "context_id": row[0],
                    "agent_id": row[1],
                    "context": row[2],
                    "timestamp": row[3]
                }
                for row in results
            ]

    def get_chunks_for_agent(self, agent_id: str, since_timestamp: Optional[str] = None, permission_level_override: Optional[str] = None) -> List[dict]:
        """Get the last 10 chunks based on agent's permission level"""
        # Determine effective permission level
        permission = permission_level_override or PermissionManager.get_agent_permission(agent_id)
        agent_session = PermissionManager.get_agent_session(agent_id)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Base query parts
            base_query = '''
                SELECT cc.chunk_content, cc.created_at, cc.agent_id, cc.session_id, c.id as context_id
                FROM context_chunks cc
                JOIN contexts c ON cc.context_id = c.id
                JOIN agents a ON cc.agent_id = a.agent_id
            '''

            # Permission filtering
            where_conditions = []
            params = []

            if permission == 'project':
                # Project can read all chunks in the project
                agent_project = PermissionManager.get_agent_project(agent_id)
                where_conditions.append("cc.project_id = ?")
                params.append(agent_project)
            elif permission == 'session':
                # Session can read all chunks in the session
                where_conditions.append("cc.session_id = ?")
                params.append(agent_session)
            elif permission == 'team':
                # Team can read chunks from agents in the same team(s) within session
                agent_teams = PermissionManager.get_agent_teams(agent_id)
                if agent_teams:
                    where_conditions.append("cc.session_id = ?")
                    params.append(agent_session)

                    team_placeholders = ','.join(['?' for _ in agent_teams])
                    where_conditions.append(f"(cc.agent_id = ? OR json_extract(a.teams, '$') IN ({team_placeholders}))")
                    params.extend([agent_id] + agent_teams)
                else:
                    # No team, only own chunks
                    where_conditions.extend(["cc.session_id = ?", "cc.agent_id = ?"])
                    params.extend([agent_session, agent_id])
            else:  # self
                # Self can only read own chunks within session
                where_conditions.extend(["cc.session_id = ?", "cc.agent_id = ?"])
                params.extend([agent_session, agent_id])

            # Time filtering
            if since_timestamp:
                where_conditions.append("cc.created_at > ?")
                params.append(since_timestamp)

            # Construct full query
            query = base_query
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)

            query += " ORDER BY cc.created_at DESC, c.id, cc.chunk_index LIMIT 10"

            cursor.execute(query, params)
            results = cursor.fetchall()

            return [
                {
                    "context": row[0],
                    "timestamp": row[1]
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
            SELECT connection_id, ip_address, assigned_agent_id, status, first_seen, last_seen
            FROM connections
            ORDER BY first_seen DESC
        ''')
        results = cursor.fetchall()

        return {
            "connections": [
                {
                    "connection_id": row[0],
                    "ip_address": row[1],
                    "assigned_agent_id": row[2],
                    "status": row[3],
                    "first_seen": row[4],
                    "last_seen": row[5]
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
            SELECT agent_id, name, permission_level, teams, connection_id, is_active, created_at, last_seen
            FROM agents
            ORDER BY created_at DESC
        ''')
        results = cursor.fetchall()

        return {
            "agents": [
                {
                    "agent_id": row[0],
                    "name": row[1],
                    "permission_level": row[2],
                    "teams": json.loads(row[3]) if row[3] else [],
                    "connection_id": row[4],
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

@app.get("/contexts")
async def get_contexts():
    """Get all contexts with chunk information"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.id, c.created_at, p.name as project_name, s.name as session_name, c.agent_id,
                   (SELECT COUNT(*) FROM context_chunks cc WHERE cc.context_id = c.id) as chunk_count,
                   (SELECT substr(cc.chunk_content, 1, 100) FROM context_chunks cc
                    WHERE cc.context_id = c.id ORDER BY cc.chunk_index LIMIT 1) as context_summary
            FROM contexts c
            LEFT JOIN projects p ON c.project_id = p.id
            LEFT JOIN sessions s ON c.session_id = s.id
            ORDER BY c.created_at DESC
        ''')
        results = cursor.fetchall()

        return {
            "contexts": [
                {
                    "context_id": row[0],
                    "timestamp": row[1],
                    "project_session": f"{row[2] or 'Unknown'} -> {row[3] or 'Unknown'}",
                    "agent_id": row[4],
                    "chunk_count": row[5] or 0,
                    "context_summary": row[6] or ""
                }
                for row in results
            ]
        }

@app.delete("/contexts/{context_id}")
async def delete_context(context_id: int):
    """Delete a context and all its chunks"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Delete chunks first due to foreign key constraint
            cursor.execute("DELETE FROM context_chunks WHERE context_id = ?", (context_id,))
            # Delete the context metadata
            cursor.execute("DELETE FROM contexts WHERE id = ?", (context_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Context not found")
            conn.commit()
        return {"success": True, "message": f"Context {context_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/teams")
async def get_teams():
    """Get all teams"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT team_id, name, description, created_at
            FROM teams
            ORDER BY name
        ''')
        results = cursor.fetchall()

        return {
            "teams": [
                {
                    "team_id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "created_at": row[3]
                }
                for row in results
            ]
        }

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