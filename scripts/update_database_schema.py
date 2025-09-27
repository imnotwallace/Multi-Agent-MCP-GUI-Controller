#!/usr/bin/env python3
"""
Database Schema Update Script
Updates existing database to include session_id field in agents table
"""

import sqlite3
import os
import sys
from datetime import datetime

def update_database_schema(db_path="multi-agent_mcp_context_manager.db"):
    """Update database schema to match new requirements"""

    if not os.path.exists(db_path):
        print(f"Database {db_path} not found. It will be created when the server starts.")
        return

    print(f"Updating database schema: {db_path}")

    # Create backup
    backup_path = f"{db_path}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

    try:
        # Copy database for backup
        with open(db_path, 'rb') as src, open(backup_path, 'wb') as dst:
            dst.write(src.read())
        print(f"Created backup: {backup_path}")
    except Exception as e:
        print(f"Warning: Could not create backup: {e}")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Check if session_id column exists in agents table
        cursor.execute("PRAGMA table_info(agents)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'session_id' not in columns:
            print("Adding session_id column to agents table...")
            try:
                cursor.execute('''
                    ALTER TABLE agents
                    ADD COLUMN session_id INTEGER
                ''')
                print("✅ Added session_id column")
            except Exception as e:
                print(f"❌ Failed to add session_id column: {e}")
        else:
            print("✅ session_id column already exists")

        # Check if projects table exists
        cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='projects'
        ''')

        if not cursor.fetchone():
            print("Creating projects table...")
            try:
                cursor.execute('''
                    CREATE TABLE projects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                print("✅ Created projects table")
            except Exception as e:
                print(f"❌ Failed to create projects table: {e}")
        else:
            print("✅ projects table already exists")

        # Check if sessions table exists
        cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='sessions'
        ''')

        if not cursor.fetchone():
            print("Creating sessions table...")
            try:
                cursor.execute('''
                    CREATE TABLE sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER,
                        name TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (project_id) REFERENCES projects (id)
                    )
                ''')
                print("✅ Created sessions table")
            except Exception as e:
                print(f"❌ Failed to create sessions table: {e}")
        else:
            print("✅ sessions table already exists")

        # Check if connections table exists
        cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='connections'
        ''')

        if not cursor.fetchone():
            print("Creating connections table...")
            try:
                cursor.execute('''
                    CREATE TABLE connections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        connection_id TEXT UNIQUE NOT NULL,
                        assigned_agent_id TEXT,
                        status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'assigned', 'rejected')),
                        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (assigned_agent_id) REFERENCES agents (assigned_agent_id)
                    )
                ''')
                print("✅ Created connections table")
            except Exception as e:
                print(f"❌ Failed to create connections table: {e}")
        else:
            print("✅ connections table already exists")

        # Check if contexts table exists
        cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='contexts'
        ''')

        if not cursor.fetchone():
            print("Creating contexts table...")
            try:
                cursor.execute('''
                    CREATE TABLE contexts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER,
                        agent_id TEXT NOT NULL,
                        context TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions (id),
                        FOREIGN KEY (agent_id) REFERENCES agents (assigned_agent_id)
                    )
                ''')
                print("✅ Created contexts table")
            except Exception as e:
                print(f"❌ Failed to create contexts table: {e}")
        else:
            print("✅ contexts table already exists")

        # Verify read_permission column has correct check constraint
        cursor.execute("PRAGMA table_info(agents)")
        agents_info = cursor.fetchall()

        # Check if read_permission column exists
        read_permission_exists = any(col[1] == 'read_permission' for col in agents_info)

        if not read_permission_exists:
            print("Adding read_permission column to agents table...")
            try:
                cursor.execute('''
                    ALTER TABLE agents
                    ADD COLUMN read_permission TEXT DEFAULT 'self_only'
                ''')
                print("✅ Added read_permission column")
            except Exception as e:
                print(f"❌ Failed to add read_permission column: {e}")
        else:
            print("✅ read_permission column already exists")

        # Create a default project and session if none exist
        cursor.execute("SELECT COUNT(*) FROM projects")
        project_count = cursor.fetchone()[0]

        if project_count == 0:
            print("Creating default project and session...")
            try:
                cursor.execute('''
                    INSERT INTO projects (name, description)
                    VALUES ('Default Project', 'Default project for multi-agent context management')
                ''')

                project_id = cursor.lastrowid

                cursor.execute('''
                    INSERT INTO sessions (project_id, name)
                    VALUES (?, 'Default Session')
                ''', (project_id,))

                print("✅ Created default project and session")
            except Exception as e:
                print(f"❌ Failed to create default project: {e}")

        conn.commit()
        print("✅ Database schema update completed successfully")

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "multi-agent_mcp_context_manager.db"
    update_database_schema(db_path)