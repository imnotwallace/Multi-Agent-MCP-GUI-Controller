"""Database migration script for agent registration redesign"""
import sqlite3
import json
from datetime import datetime

def migrate_database(db_path: str = "multi-agent_mcp_context_manager.db"):
    """Migrate existing database to support new agent registration system"""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Add new columns to agents table
        new_columns = [
            ("registration_status", "TEXT DEFAULT 'assigned'"),  # Existing agents are considered assigned
            ("selected_tool", "TEXT DEFAULT 'write'"),  # Existing agents get write access
            ("assigned_agent_id", "TEXT"),
            ("connection_id", "TEXT"),
            ("capabilities", "TEXT DEFAULT '{}'")
        ]

        for column_name, column_def in new_columns:
            try:
                cursor.execute(f"ALTER TABLE agents ADD COLUMN {column_name} {column_def}")
                print(f"Added column {column_name} to agents table")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"Column {column_name} already exists")
                else:
                    raise

        # For existing agents, set assigned_agent_id to their current id
        cursor.execute("UPDATE agents SET assigned_agent_id = id WHERE assigned_agent_id IS NULL")
        print("Updated existing agents with assigned_agent_id")

        # Create contexts table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contexts (
                id TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                project_id TEXT,
                session_id TEXT,
                agent_id TEXT,
                sequence_number INTEGER,
                metadata TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                deleted_at TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            )
        ''')
        print("Created contexts table")

        # Create agent_tools table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_tools (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                permissions TEXT,
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')

        # Insert default tools
        tools = [
            ('register', 'Register', 'Register as a new agent in the system',
             '{"read": ["agent_registration"], "write": ["agent_registration"]}'),
            ('read', 'Read', 'Read data from assigned contexts and sessions',
             '{"read": ["contexts", "sessions", "projects"], "write": []}'),
            ('write', 'Write', 'Read and write data to assigned contexts and sessions',
             '{"read": ["contexts", "sessions", "projects"], "write": ["contexts"]}')
        ]

        now = datetime.utcnow().isoformat()
        for tool_id, name, desc, perms in tools:
            cursor.execute('''
                INSERT OR REPLACE INTO agent_tools (id, name, description, permissions, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (tool_id, name, desc, perms, now, now))

        print("Created agent_tools table and inserted default tools")

        # Create new indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_agents_registration_status ON agents(registration_status)",
            "CREATE INDEX IF NOT EXISTS idx_agents_assigned_agent_id ON agents(assigned_agent_id)",
            "CREATE INDEX IF NOT EXISTS idx_agents_connection_id ON agents(connection_id)",
            "CREATE INDEX IF NOT EXISTS idx_contexts_agent_recent ON contexts(agent_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_contexts_session_recent ON contexts(session_id, created_at DESC)"
        ]

        for index_sql in indexes:
            cursor.execute(index_sql)

        print("Created new indexes")

        conn.commit()
        print("Migration completed successfully")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()