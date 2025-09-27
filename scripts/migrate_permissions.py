#!/usr/bin/env python3
"""
Database Migration Script for Agent Permission System
Migrates from current schema to permission-aware schema
"""

import sqlite3
import json
import logging
from datetime import datetime
from contextlib import contextmanager
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "multi-agent_mcp_context_manager.db"
BACKUP_SUFFIX = "_backup_before_permissions"

@contextmanager
def get_connection():
    """Get database connection with proper configuration"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        yield conn
    finally:
        conn.close()

def backup_database() -> str:
    """Create backup of current database"""
    backup_path = f"{DB_PATH}{BACKUP_SUFFIX}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

    logger.info(f"Creating backup: {backup_path}")

    with get_connection() as source_conn:
        backup_conn = sqlite3.connect(backup_path)
        try:
            source_conn.backup(backup_conn)
            logger.info("Backup created successfully")
        finally:
            backup_conn.close()

    return backup_path

def check_current_schema() -> dict:
    """Check current database schema and collect stats"""
    with get_connection() as conn:
        cur = conn.cursor()

        # Check if permission columns already exist
        cur.execute("PRAGMA table_info(agents)")
        columns = {row[1] for row in cur.fetchall()}

        has_permissions = 'access_level' in columns

        # Get current counts
        cur.execute("SELECT COUNT(*) FROM agents WHERE deleted_at IS NULL")
        agent_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM agents WHERE team_id IS NOT NULL AND deleted_at IS NULL")
        agents_with_teams = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM contexts WHERE deleted_at IS NULL")
        context_count = cur.fetchone()[0]

        stats = {
            'has_permissions': has_permissions,
            'agent_count': agent_count,
            'agents_with_teams': agents_with_teams,
            'context_count': context_count
        }

        logger.info(f"Current schema stats: {stats}")
        return stats

def add_permission_columns():
    """Add permission-related columns to agents table"""
    logger.info("Adding permission columns to agents table")

    with get_connection() as conn:
        cur = conn.cursor()

        # Add permission columns if they don't exist
        try:
            cur.execute('''
                ALTER TABLE agents ADD COLUMN access_level TEXT DEFAULT 'self_only'
                CHECK (access_level IN ('self_only', 'team_level', 'session_level'))
            ''')
            logger.info("Added access_level column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                logger.info("access_level column already exists")
            else:
                raise

        try:
            cur.execute('ALTER TABLE agents ADD COLUMN permission_granted_by TEXT')
            logger.info("Added permission_granted_by column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                logger.info("permission_granted_by column already exists")
            else:
                raise

        try:
            cur.execute('ALTER TABLE agents ADD COLUMN permission_granted_at TIMESTAMP')
            logger.info("Added permission_granted_at column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                logger.info("permission_granted_at column already exists")
            else:
                raise

        try:
            cur.execute('ALTER TABLE agents ADD COLUMN permission_expires_at TIMESTAMP')
            logger.info("Added permission_expires_at column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                logger.info("permission_expires_at column already exists")
            else:
                raise

        conn.commit()

def create_audit_table():
    """Create agent permission history table"""
    logger.info("Creating agent permission history table")

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute('''
            CREATE TABLE IF NOT EXISTS agent_permission_history (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                old_access_level TEXT,
                new_access_level TEXT NOT NULL,
                granted_by TEXT NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            )
        ''')

        logger.info("Created agent_permission_history table")
        conn.commit()

def create_permission_rules_table():
    """Create permission rules table for inheritance settings"""
    logger.info("Creating permission rules table")

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute('''
            CREATE TABLE IF NOT EXISTS permission_rules (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                team_id TEXT,
                default_access_level TEXT DEFAULT 'self_only',
                auto_grant_team_level BOOLEAN DEFAULT 0,
                auto_grant_session_level BOOLEAN DEFAULT 0,
                created_by TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
            )
        ''')

        logger.info("Created permission_rules table")
        conn.commit()

def create_indexes():
    """Create performance indexes for permission queries"""
    logger.info("Creating permission-related indexes")

    with get_connection() as conn:
        cur = conn.cursor()

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_agents_access_level ON agents(access_level)",
            "CREATE INDEX IF NOT EXISTS idx_agents_permission_expires ON agents(permission_expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_permission_history_agent ON agent_permission_history(agent_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_permission_rules_session ON permission_rules(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_permission_rules_team ON permission_rules(team_id)",
            # Enhanced context query indexes
            "CREATE INDEX IF NOT EXISTS idx_contexts_agent_session ON contexts(agent_id, session_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_agents_team_session ON agents(team_id, session_id, deleted_at)",
        ]

        for index_sql in indexes:
            try:
                cur.execute(index_sql)
                logger.info(f"Created index: {index_sql.split()[-3]}")
            except sqlite3.OperationalError as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"Failed to create index: {e}")

        conn.commit()

def migrate_existing_permissions():
    """Migrate existing agents to appropriate permission levels"""
    logger.info("Migrating existing agent permissions")

    with get_connection() as conn:
        cur = conn.cursor()

        # First, set default values for all agents that don't have permissions set
        cur.execute('''
            UPDATE agents
            SET access_level = 'self_only',
                permission_granted_by = 'system_migration',
                permission_granted_at = ?
            WHERE access_level IS NULL AND deleted_at IS NULL
        ''', (datetime.utcnow().isoformat(),))

        migrated_to_default = cur.rowcount
        logger.info(f"Set default permissions for {migrated_to_default} agents")

        # Upgrade agents with team assignments to team_level if they're still self_only
        cur.execute('''
            UPDATE agents
            SET access_level = 'team_level',
                permission_granted_by = 'migration_team_assignment',
                permission_granted_at = ?
            WHERE team_id IS NOT NULL
              AND access_level = 'self_only'
              AND deleted_at IS NULL
        ''', (datetime.utcnow().isoformat(),))

        migrated_to_team = cur.rowcount
        logger.info(f"Upgraded {migrated_to_team} agents to team_level based on team assignment")

        # Create audit entries for all migrated agents
        cur.execute('''
            INSERT INTO agent_permission_history (id, agent_id, old_access_level, new_access_level, granted_by, reason)
            SELECT
                'migration_' || a.id || '_' || strftime('%Y%m%d_%H%M%S', 'now'),
                a.id,
                'unknown',
                a.access_level,
                'system_migration',
                CASE
                    WHEN a.team_id IS NOT NULL THEN 'Migrated with team assignment'
                    ELSE 'Migrated with default permissions'
                END
            FROM agents a
            WHERE a.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM agent_permission_history h
                  WHERE h.agent_id = a.id AND h.granted_by = 'system_migration'
              )
        ''')

        audit_entries = cur.rowcount
        logger.info(f"Created {audit_entries} audit entries for migration")

        conn.commit()

        return {
            'migrated_to_default': migrated_to_default,
            'migrated_to_team': migrated_to_team,
            'audit_entries': audit_entries
        }

def create_default_permission_rules():
    """Create default permission rules for existing sessions and teams"""
    logger.info("Creating default permission rules")

    with get_connection() as conn:
        cur = conn.cursor()

        # Create session-level default rules
        cur.execute('''
            INSERT INTO permission_rules (id, session_id, default_access_level, created_by)
            SELECT
                'default_session_' || s.id,
                s.id,
                'self_only',
                'system_migration'
            FROM sessions s
            WHERE s.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM permission_rules pr
                  WHERE pr.session_id = s.id
              )
        ''')

        session_rules = cur.rowcount
        logger.info(f"Created {session_rules} default session permission rules")

        # Create team-level rules with auto-grant for team members
        cur.execute('''
            INSERT INTO permission_rules (id, team_id, session_id, default_access_level, auto_grant_team_level, created_by)
            SELECT
                'default_team_' || t.id,
                t.id,
                t.session_id,
                'team_level',
                1,
                'system_migration'
            FROM teams t
            WHERE t.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM permission_rules pr
                  WHERE pr.team_id = t.id
              )
        ''')

        team_rules = cur.rowcount
        logger.info(f"Created {team_rules} default team permission rules")

        conn.commit()

        return {
            'session_rules': session_rules,
            'team_rules': team_rules
        }

def validate_migration():
    """Validate that migration was successful"""
    logger.info("Validating migration results")

    with get_connection() as conn:
        cur = conn.cursor()

        # Check all agents have valid permissions
        cur.execute('''
            SELECT COUNT(*) FROM agents
            WHERE deleted_at IS NULL
              AND (access_level IS NULL OR access_level NOT IN ('self_only', 'team_level', 'session_level'))
        ''')
        invalid_permissions = cur.fetchone()[0]

        # Check audit trail exists
        cur.execute('SELECT COUNT(*) FROM agent_permission_history')
        audit_count = cur.fetchone()[0]

        # Check permission rules exist
        cur.execute('SELECT COUNT(*) FROM permission_rules')
        rules_count = cur.fetchone()[0]

        # Validate team permission consistency
        cur.execute('''
            SELECT COUNT(*) FROM agents a
            WHERE a.deleted_at IS NULL
              AND a.access_level = 'team_level'
              AND a.team_id IS NULL
        ''')
        inconsistent_team_perms = cur.fetchone()[0]

        validation_results = {
            'invalid_permissions': invalid_permissions,
            'audit_count': audit_count,
            'rules_count': rules_count,
            'inconsistent_team_perms': inconsistent_team_perms
        }

        logger.info(f"Validation results: {validation_results}")

        # Determine if migration is valid
        is_valid = (
            invalid_permissions == 0 and
            audit_count > 0 and
            inconsistent_team_perms == 0
        )

        return is_valid, validation_results

def rollback_migration(backup_path: str):
    """Rollback migration by restoring from backup"""
    logger.warning(f"Rolling back migration from backup: {backup_path}")

    import shutil
    import os

    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    # Restore from backup
    shutil.copy2(backup_path, DB_PATH)
    logger.info("Database restored from backup")

def run_migration(dry_run: bool = False) -> dict:
    """
    Main migration function

    Args:
        dry_run: If True, only validate current state without making changes

    Returns:
        Dictionary with migration results
    """
    results = {
        'success': False,
        'backup_path': None,
        'validation_results': None,
        'migration_stats': None,
        'error': None
    }

    try:
        logger.info(f"Starting permission system migration (dry_run={dry_run})")

        # Check current schema
        current_stats = check_current_schema()

        if current_stats['has_permissions']:
            logger.info("Permission columns already exist - running validation only")
            is_valid, validation_results = validate_migration()
            results['validation_results'] = validation_results
            results['success'] = is_valid
            return results

        if dry_run:
            logger.info("Dry run completed - no changes made")
            results['success'] = True
            results['migration_stats'] = {'dry_run': True, 'current_stats': current_stats}
            return results

        # Create backup
        backup_path = backup_database()
        results['backup_path'] = backup_path

        # Run migration steps
        add_permission_columns()
        create_audit_table()
        create_permission_rules_table()
        create_indexes()

        migration_stats = migrate_existing_permissions()
        permission_rules_stats = create_default_permission_rules()

        # Validate migration
        is_valid, validation_results = validate_migration()

        if not is_valid:
            logger.error("Migration validation failed - rolling back")
            rollback_migration(backup_path)
            results['error'] = "Migration validation failed"
            return results

        results['success'] = True
        results['validation_results'] = validation_results
        results['migration_stats'] = {
            **migration_stats,
            **permission_rules_stats,
            'current_stats': current_stats
        }

        logger.info("Permission system migration completed successfully")

    except Exception as e:
        logger.exception(f"Migration failed: {e}")
        results['error'] = str(e)

        if results['backup_path'] and not dry_run:
            try:
                rollback_migration(results['backup_path'])
                logger.info("Rollback completed")
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")
                results['error'] += f" | Rollback failed: {rollback_error}"

    return results

def main():
    """Command line interface for migration"""
    import argparse

    parser = argparse.ArgumentParser(description='Migrate database to permission-aware schema')
    parser.add_argument('--dry-run', action='store_true',
                       help='Validate current state without making changes')
    parser.add_argument('--force', action='store_true',
                       help='Force migration even if validation warnings exist')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        results = run_migration(dry_run=args.dry_run)

        if results['success']:
            print("Migration completed successfully")
            if results['migration_stats']:
                stats = results['migration_stats']
                print(f"Migration Statistics:")
                for key, value in stats.items():
                    print(f"   {key}: {value}")
        else:
            print("Migration failed")
            if results['error']:
                print(f"Error: {results['error']}")

        if results['validation_results']:
            val = results['validation_results']
            print(f"Validation Results:")
            for key, value in val.items():
                status = "✅" if value == 0 or (key == 'audit_count' and value > 0) else "⚠️"
                print(f"   {status} {key}: {value}")

        if results['backup_path']:
            print(f"Backup created: {results['backup_path']}")

    except KeyboardInterrupt:
        print("\nMigration cancelled by user")
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise

if __name__ == '__main__':
    main()