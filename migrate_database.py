#!/usr/bin/env python3
"""
Database Migration Script for Multi-Agent MCP Context Manager
Handles migration from old schema to new chunk-based schema
"""

import sqlite3
import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("database_migration")

# Database configuration
DB_PATH = "multi-agent_mcp_context_manager.db"
BACKUP_PATH = f"multi-agent_mcp_context_manager_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

# Chunking configuration
CHUNK_SIZE = 3500
OVERLAP_PERCENTAGE = 0.15
CHUNK_OVERLAP = int(CHUNK_SIZE * OVERLAP_PERCENTAGE)


class DatabaseMigrator:
    """Handles database migration to new schema"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.backup_path = BACKUP_PATH

    def migrate(self):
        """Run the complete migration process"""
        logger.info("Starting database migration...")

        if not os.path.exists(self.db_path):
            logger.error(f"Database file {self.db_path} not found")
            return False

        try:
            # 1. Create backup
            self.create_backup()

            # 2. Check current schema
            schema_version = self.check_schema_version()
            logger.info(f"Current schema version: {schema_version}")

            if schema_version == "new":
                logger.info("Database already uses new schema")
                return True

            # 3. Migrate based on current schema
            if schema_version == "old":
                self.migrate_from_old_schema()
            elif schema_version == "mixed":
                self.complete_partial_migration()
            else:
                logger.error(f"Unknown schema version: {schema_version}")
                return False

            # 4. Verify migration
            if self.verify_migration():
                logger.info("Migration completed successfully")
                return True
            else:
                logger.error("Migration verification failed")
                self.restore_backup()
                return False

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            self.restore_backup()
            return False

    def create_backup(self):
        """Create a backup of the database"""
        logger.info(f"Creating backup: {self.backup_path}")

        with sqlite3.connect(self.db_path) as source:
            with sqlite3.connect(self.backup_path) as backup:
                source.backup(backup)

        logger.info("Backup created successfully")

    def restore_backup(self):
        """Restore database from backup"""
        logger.info("Restoring from backup...")

        if os.path.exists(self.backup_path):
            # Remove current database
            if os.path.exists(self.db_path):
                os.remove(self.db_path)

            # Restore backup
            with sqlite3.connect(self.backup_path) as backup:
                with sqlite3.connect(self.db_path) as target:
                    backup.backup(target)

            logger.info("Database restored from backup")
        else:
            logger.error("Backup file not found")

    def check_schema_version(self) -> str:
        """Check the current schema version"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if old contexts table exists with old structure
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contexts'")
            contexts_exists = cursor.fetchone()

            if not contexts_exists:
                return "none"

            # Check if contexts table has old structure (context column)
            cursor.execute("PRAGMA table_info(contexts)")
            context_columns = [col[1] for col in cursor.fetchall()]

            # Check if context_chunks table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='context_chunks'")
            chunks_exists = cursor.fetchone()

            if 'context' in context_columns and not chunks_exists:
                return "old"
            elif 'context' not in context_columns and chunks_exists:
                return "new"
            elif 'context' in context_columns and chunks_exists:
                return "mixed"
            else:
                return "unknown"

    def migrate_from_old_schema(self):
        """Migrate from old schema to new chunk-based schema"""
        logger.info("Migrating from old schema...")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 1. Create new tables
            self.create_new_tables(cursor)

            # 2. Migrate contexts data
            self.migrate_contexts_data(cursor)

            # 3. Update indexes
            self.create_indexes(cursor)

            # 4. Create vector tables if possible
            self.create_vector_tables(cursor)

            conn.commit()

    def complete_partial_migration(self):
        """Complete a partially migrated database"""
        logger.info("Completing partial migration...")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check what needs to be completed
            cursor.execute("PRAGMA table_info(contexts)")
            context_columns = [col[1] for col in cursor.fetchall()]

            if 'context' in context_columns:
                # Still has old data, need to migrate
                self.migrate_contexts_data(cursor)

            # Ensure all indexes exist
            self.create_indexes(cursor)

            # Ensure vector tables exist
            self.create_vector_tables(cursor)

            conn.commit()

    def create_new_tables(self, cursor):
        """Create new table structure"""
        logger.info("Creating new tables...")

        # Create new contexts table (metadata only)
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

        # Create context_chunks table
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

    def migrate_contexts_data(self, cursor):
        """Migrate context data from old to new structure"""
        logger.info("Migrating context data...")

        # Get all old contexts
        try:
            cursor.execute("SELECT context_id, agent_id, context, timestamp FROM contexts WHERE context IS NOT NULL")
            old_contexts = cursor.fetchall()
        except sqlite3.OperationalError:
            # If old column names don't exist, try alternative names
            try:
                cursor.execute("SELECT id, agent_id, context, created_at FROM contexts WHERE context IS NOT NULL")
                old_contexts = cursor.fetchall()
            except sqlite3.OperationalError:
                logger.warning("Could not find old context data to migrate")
                return

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
        )

        migrated_count = 0
        for old_context in old_contexts:
            old_id, agent_id, context_text, timestamp = old_context

            if not context_text:
                continue

            try:
                # Insert into new contexts table (metadata only)
                cursor.execute('''
                    INSERT INTO contexts_new (agent_id, session_id, project_id, created_at)
                    VALUES (?, 1, 1, ?)
                ''', (agent_id, timestamp))
                new_context_id = cursor.lastrowid

                # Split context into chunks
                chunks = text_splitter.split_text(context_text)

                # Insert chunks
                for chunk_index, chunk_content in enumerate(chunks):
                    cursor.execute('''
                        INSERT INTO context_chunks
                        (context_id, chunk_index, chunk_content, agent_id, session_id, project_id, created_at)
                        VALUES (?, ?, ?, ?, 1, 1, ?)
                    ''', (new_context_id, chunk_index, chunk_content, agent_id, timestamp))

                migrated_count += 1

            except Exception as e:
                logger.error(f"Failed to migrate context {old_id}: {e}")

        logger.info(f"Migrated {migrated_count} contexts into chunked format")

        # Drop old table and rename new one
        cursor.execute("DROP TABLE contexts")
        cursor.execute("ALTER TABLE contexts_new RENAME TO contexts")

    def create_indexes(self, cursor):
        """Create all necessary indexes"""
        logger.info("Creating indexes...")

        indexes = [
            # Agent indexes
            'CREATE INDEX IF NOT EXISTS idx_agents_agent_id ON agents(agent_id)',
            'CREATE INDEX IF NOT EXISTS idx_agents_session_id ON agents(session_id)',
            'CREATE INDEX IF NOT EXISTS idx_agents_permission_level ON agents(permission_level)',
            'CREATE INDEX IF NOT EXISTS idx_agents_teams ON agents(teams)',
            'CREATE INDEX IF NOT EXISTS idx_agents_is_active ON agents(is_active)',

            # Context indexes
            'CREATE INDEX IF NOT EXISTS idx_contexts_agent_id ON contexts(agent_id)',
            'CREATE INDEX IF NOT EXISTS idx_contexts_session_id ON contexts(session_id)',
            'CREATE INDEX IF NOT EXISTS idx_contexts_project_id ON contexts(project_id)',
            'CREATE INDEX IF NOT EXISTS idx_contexts_created_at ON contexts(created_at)',

            # Context chunks indexes
            'CREATE INDEX IF NOT EXISTS idx_context_chunks_context_id ON context_chunks(context_id)',
            'CREATE INDEX IF NOT EXISTS idx_context_chunks_agent_id ON context_chunks(agent_id)',
            'CREATE INDEX IF NOT EXISTS idx_context_chunks_session_id ON context_chunks(session_id)',
            'CREATE INDEX IF NOT EXISTS idx_context_chunks_project_id ON context_chunks(project_id)',
            'CREATE INDEX IF NOT EXISTS idx_context_chunks_created_at ON context_chunks(created_at)',
            'CREATE INDEX IF NOT EXISTS idx_context_chunks_chunk_index ON context_chunks(chunk_index)',

            # Connection indexes
            'CREATE INDEX IF NOT EXISTS idx_connections_connection_id ON connections(connection_id)',
            'CREATE INDEX IF NOT EXISTS idx_connections_assigned_agent_id ON connections(assigned_agent_id)',
            'CREATE INDEX IF NOT EXISTS idx_connections_status ON connections(status)',

            # Session indexes
            'CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id)',
            'CREATE INDEX IF NOT EXISTS idx_sessions_name ON sessions(name)',

            # Project indexes
            'CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)',

            # Team indexes
            'CREATE INDEX IF NOT EXISTS idx_teams_team_id ON teams(team_id)',
        ]

        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except Exception as e:
                logger.warning(f"Failed to create index: {e}")

    def create_vector_tables(self, cursor):
        """Create vector embedding tables if sqlite-vec is available"""
        logger.info("Attempting to create vector tables...")

        try:
            # Test if sqlite-vss is available
            cursor.connection.enable_load_extension(True)
            cursor.connection.load_extension("vss0")

            # Create virtual table for vector embeddings
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS context_chunk_embeddings USING vss0(
                    chunk_id INTEGER PRIMARY KEY,
                    embedding(256)
                )
            ''')

            # Create index for vector similarity search
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_embeddings_vector
                ON context_chunk_embeddings(embedding)
            ''')

            logger.info("Vector embedding tables created successfully")

        except Exception as e:
            logger.warning(f"Could not create vector tables (sqlite-vss not available): {e}")

    def verify_migration(self) -> bool:
        """Verify that migration was successful"""
        logger.info("Verifying migration...")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            try:
                # Check that new tables exist
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contexts'")
                contexts_exists = cursor.fetchone()

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='context_chunks'")
                chunks_exists = cursor.fetchone()

                if not contexts_exists or not chunks_exists:
                    logger.error("Required tables missing after migration")
                    return False

                # Check that contexts table has new structure
                cursor.execute("PRAGMA table_info(contexts)")
                context_columns = [col[1] for col in cursor.fetchall()]

                expected_columns = ['id', 'agent_id', 'session_id', 'project_id', 'created_at']
                for col in expected_columns:
                    if col not in context_columns:
                        logger.error(f"Missing column '{col}' in contexts table")
                        return False

                # Check that old 'context' column is gone
                if 'context' in context_columns:
                    logger.error("Old 'context' column still exists in contexts table")
                    return False

                # Check that chunks table has correct structure
                cursor.execute("PRAGMA table_info(context_chunks)")
                chunk_columns = [col[1] for col in cursor.fetchall()]

                expected_chunk_columns = ['id', 'context_id', 'chunk_index', 'chunk_content',
                                         'agent_id', 'session_id', 'project_id', 'created_at']
                for col in expected_chunk_columns:
                    if col not in chunk_columns:
                        logger.error(f"Missing column '{col}' in context_chunks table")
                        return False

                # Check that data exists
                cursor.execute("SELECT COUNT(*) FROM contexts")
                context_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM context_chunks")
                chunk_count = cursor.fetchone()[0]

                logger.info(f"Migration verification: {context_count} contexts, {chunk_count} chunks")

                return True

            except Exception as e:
                logger.error(f"Migration verification failed: {e}")
                return False


def main():
    """Main migration function"""
    migrator = DatabaseMigrator()

    print("Multi-Agent MCP Context Manager - Database Migration")
    print("=" * 50)

    if not os.path.exists(DB_PATH):
        print(f"Database file {DB_PATH} not found.")
        print("No migration needed - database will be created with new schema on first run.")
        return

    print(f"Database found: {DB_PATH}")

    # Ask for confirmation
    response = input("Do you want to proceed with migration? This will create a backup. (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        return

    # Run migration
    success = migrator.migrate()

    if success:
        print("\n✅ Migration completed successfully!")
        print(f"Backup created: {migrator.backup_path}")
        print("\nYou can now run the MCP server with the new schema.")
    else:
        print("\n❌ Migration failed!")
        print("Database has been restored from backup.")
        print("Please check the logs and try again.")


if __name__ == "__main__":
    main()