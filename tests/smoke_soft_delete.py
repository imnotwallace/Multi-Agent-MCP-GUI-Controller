import sqlite3
from datetime import datetime
import os

DB = 'test_mcp.db'
if os.path.exists(DB):
    os.remove(DB)

conn = sqlite3.connect(DB)
cur = conn.cursor()

# Minimal schema for the smoke test
cur.execute('''
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT,
    deleted_at TIMESTAMP
)
''')
cur.execute('''
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    name TEXT,
    project_id TEXT,
    deleted_at TIMESTAMP
)
''')
cur.execute('''
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT,
    deleted_at TIMESTAMP
)
''')
cur.execute('''
CREATE TABLE contexts (
    id TEXT PRIMARY KEY,
    title TEXT,
    content TEXT,
    project_id TEXT,
    session_id TEXT,
    agent_id TEXT,
    deleted_at TIMESTAMP
)
''')
conn.commit()

# Insert test rows
now = datetime.now().isoformat()
cur.execute('INSERT INTO projects (id, name) VALUES (?, ?)', ('proj1', 'Project 1'))
cur.execute('INSERT INTO sessions (id, name, project_id) VALUES (?, ?, ?)', ('sess1', 'Session 1', 'proj1'))
cur.execute('INSERT INTO agents (id, name) VALUES (?, ?)', ('agent1', 'Agent 1'))
cur.execute('INSERT INTO contexts (id, title, content, project_id, session_id, agent_id) VALUES (?, ?, ?, ?, ?, ?)',
            ('ctx1', 'Title 1', 'Content 1', 'proj1', 'sess1', 'agent1'))
conn.commit()

print('Before soft-delete:')
print('projects (visible):', cur.execute("SELECT id, name, deleted_at FROM projects WHERE deleted_at IS NULL").fetchall())
print('sessions (visible):', cur.execute("SELECT id, name, project_id, deleted_at FROM sessions WHERE deleted_at IS NULL").fetchall())
print('agents (visible):', cur.execute("SELECT id, name, deleted_at FROM agents WHERE deleted_at IS NULL").fetchall())
print('contexts (visible):', cur.execute("SELECT id, title, deleted_at FROM contexts WHERE deleted_at IS NULL").fetchall())

# Perform soft-delete of project proj1 (same SQL as app)
now = datetime.now().isoformat()
cur.execute('UPDATE projects SET deleted_at = ? WHERE id = ?', (now, 'proj1'))
cur.execute('UPDATE sessions SET deleted_at = ? WHERE project_id = ?', (now, 'proj1'))
cur.execute('UPDATE contexts SET deleted_at = ? WHERE project_id = ?', (now, 'proj1'))
conn.commit()

print('\nAfter soft-delete:')
print('projects (visible):', cur.execute("SELECT id, name, deleted_at FROM projects WHERE deleted_at IS NULL").fetchall())
print('projects (all):', cur.execute("SELECT id, name, deleted_at FROM projects").fetchall())
print('sessions (visible):', cur.execute("SELECT id, name, project_id, deleted_at FROM sessions WHERE deleted_at IS NULL").fetchall())
print('sessions (all):', cur.execute("SELECT id, name, project_id, deleted_at FROM sessions").fetchall())
print('contexts (visible):', cur.execute("SELECT id, title, deleted_at FROM contexts WHERE deleted_at IS NULL").fetchall())
print('contexts (all):', cur.execute("SELECT id, title, deleted_at FROM contexts").fetchall())

conn.close()
print('\nSmoke test completed successfully')
