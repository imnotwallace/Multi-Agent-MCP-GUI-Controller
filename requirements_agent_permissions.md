# Agent Access Permissions System Requirements

## Executive Summary

This document outlines the design and implementation requirements for a configurable agent access permissions system for the Multi-Agent MCP Context Manager. The system addresses critical security vulnerabilities in context isolation while enabling flexible multi-agent collaboration patterns.

## Current System Analysis

### Identified Security Vulnerability

**Critical Issue**: Context Isolation Breach in `mcp_server.py` lines 514-520:

```sql
SELECT c.id, c.title, c.content, c.created_at
FROM contexts c
JOIN agents a ON c.session_id = a.session_id
WHERE a.assigned_agent_id = ? AND c.deleted_at IS NULL
```

**Problem**: This query allows any agent to read ALL contexts from ALL agents within the same session, regardless of intended access controls. This creates a serious security and privacy violation.

### Current Database Schema

The existing schema includes:
- `projects` → `sessions` → `teams` → `agents`
- `contexts` linked to `project_id`, `session_id`, and `agent_id`
- No permission/access control fields

## Permission Model Design

### Three-Tier Access Control System

#### 1. Self-Only Access (Default)
- **Scope**: Agent can only read contexts it created
- **SQL Filter**: `WHERE contexts.agent_id = requesting_agent.id`
- **Use Case**: Isolated agent operations, sensitive data handling

#### 2. Team-Level Access
- **Scope**: Agent can read contexts from all agents in the same team within current session
- **SQL Filter**: `WHERE contexts.agent_id IN (SELECT id FROM agents WHERE team_id = requesting_agent.team_id AND session_id = requesting_agent.session_id)`
- **Use Case**: Collaborative team workflows, shared project contexts

#### 3. Session-Level Access
- **Scope**: Agent can read contexts from all agents within the current session
- **SQL Filter**: `WHERE contexts.session_id = requesting_agent.session_id`
- **Use Case**: Cross-team collaboration, session-wide knowledge sharing

### Permission Inheritance Rules

1. **Default Permission**: New agents inherit "Self-Only" access
2. **Team Assignment**: When agent joins team, permission can be elevated to "Team-Level"
3. **Session Elevation**: Session administrators can grant "Session-Level" access
4. **Permission Downgrade**: Always allowed for security
5. **Permission Upgrade**: Requires administrator approval

## Database Schema Changes

### 1. Add Permission Fields to Agents Table

```sql
ALTER TABLE agents ADD COLUMN access_level TEXT DEFAULT 'self_only' CHECK (access_level IN ('self_only', 'team_level', 'session_level'));
ALTER TABLE agents ADD COLUMN permission_granted_by TEXT;
ALTER TABLE agents ADD COLUMN permission_granted_at TIMESTAMP;
ALTER TABLE agents ADD COLUMN permission_expires_at TIMESTAMP;
```

### 2. New Permission Audit Table

```sql
CREATE TABLE agent_permission_history (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    old_access_level TEXT,
    new_access_level TEXT NOT NULL,
    granted_by TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);
```

### 3. New Permission Inheritance Rules Table

```sql
CREATE TABLE permission_rules (
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
);
```

### 4. Required Indexes

```sql
CREATE INDEX idx_agents_access_level ON agents(access_level);
CREATE INDEX idx_permission_history_agent ON agent_permission_history(agent_id, created_at DESC);
CREATE INDEX idx_permission_rules_session ON permission_rules(session_id);
CREATE INDEX idx_permission_rules_team ON permission_rules(team_id);
```

## GUI Design Requirements

### 1. Agent Registration Tab Enhancements

#### Permission Configuration Section
```
┌─ Agent Registration ─────────────────────────────────────────┐
│ Agent Name: [_______________]                                │
│ Session: [Dropdown____▼]                                    │
│ Team: [Dropdown____▼]                                       │
│                                                              │
│ ┌─ Access Permissions ─────────────────────────────────────┐ │
│ │ ○ Self-Only Access (Default)                            │ │
│ │   Agent can only read its own contexts                  │ │
│ │                                                          │ │
│ │ ○ Team-Level Access                                     │ │
│ │   Agent can read contexts from team members             │ │
│ │   [Requires team assignment above]                      │ │
│ │                                                          │ │
│ │ ○ Session-Level Access                                  │ │
│ │   Agent can read all contexts in session                │ │
│ │   [⚠️ Administrative approval required]                  │ │
│ │                                                          │ │
│ │ Reason for elevated access:                             │ │
│ │ [_____________________________________________________] │ │
│ │                                                          │ │
│ │ Permission expires: [Date picker] [Never ✓]            │ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                              │
│ [Register Agent]  [Cancel]                                  │
└──────────────────────────────────────────────────────────────┘
```

### 2. Agent Management Tab Enhancements

#### Permission Management Section
```
┌─ Agent Management ───────────────────────────────────────────┐
│ ┌─ Agent List ─────────────────────────────────────────────┐ │
│ │ Name         │ Status │ Team │ Access Level │ Actions    │ │
│ │ Agent_001    │ ●      │ Dev  │ 🔒 Self      │ [Edit▼]   │ │
│ │ Agent_002    │ ●      │ QA   │ 👥 Team      │ [Edit▼]   │ │
│ │ Agent_003    │ ○      │ -    │ 🌐 Session   │ [Edit▼]   │ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                              │
│ [Bulk Permissions▼] [Select All] [Clear Selection]          │
│                                                              │
│ ┌─ Permission Details ─────────────────────────────────────┐ │
│ │ Selected Agent: Agent_001                                │ │
│ │ Current Access: 🔒 Self-Only                             │ │
│ │ Granted By: System (Default)                             │ │
│ │ Granted On: 2024-01-15 10:30:00                         │ │
│ │ Expires: Never                                           │ │
│ │                                                          │ │
│ │ Change Access Level:                                     │ │
│ │ ○ Self-Only   ○ Team-Level   ○ Session-Level            │ │
│ │                                                          │ │
│ │ Reason: [____________________________]                  │ │
│ │ [Apply Changes] [View History]                           │ │
│ └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 3. Visual Permission Indicators

#### Agent Status Icons
- 🔒 **Self-Only**: Lock icon (Default)
- 👥 **Team-Level**: Group icon
- 🌐 **Session-Level**: Globe icon
- ⚠️ **Pending Approval**: Warning icon
- ⏰ **Expiring Soon**: Clock icon

#### Color Coding
- **Green**: Normal operation
- **Yellow**: Permission expires within 7 days
- **Orange**: Elevated permissions requiring review
- **Red**: Permission violations or denials

## Updated MCP Server Logic

### 1. Permission-Aware Context Retrieval

```python
async def get_contexts_with_permissions(agent_id: str, limit: int = 10) -> List[dict]:
    """Retrieve contexts based on agent's permission level"""
    with get_connection() as conn:
        cur = conn.cursor()

        # Get agent's current permission level and session/team info
        cur.execute("""
            SELECT access_level, session_id, team_id, permission_expires_at
            FROM agents
            WHERE assigned_agent_id = ? AND deleted_at IS NULL
        """, (agent_id,))

        agent_info = cur.fetchone()
        if not agent_info:
            raise ValueError("Agent not found")

        access_level, session_id, team_id, expires_at = agent_info

        # Check if permission has expired
        if expires_at and datetime.fromisoformat(expires_at) < datetime.utcnow():
            # Downgrade to self_only and log
            await downgrade_expired_permission(agent_id)
            access_level = 'self_only'

        # Build context query based on permission level
        if access_level == 'self_only':
            query = """
                SELECT c.id, c.title, c.content, c.created_at, c.agent_id
                FROM contexts c
                JOIN agents a ON c.agent_id = a.assigned_agent_id
                WHERE a.assigned_agent_id = ? AND c.deleted_at IS NULL
                ORDER BY c.created_at DESC LIMIT ?
            """
            params = (agent_id, limit)

        elif access_level == 'team_level':
            if not team_id:
                # No team assigned, fall back to self_only
                return await get_contexts_with_permissions(agent_id, limit)

            query = """
                SELECT c.id, c.title, c.content, c.created_at, c.agent_id
                FROM contexts c
                JOIN agents a ON c.agent_id = a.assigned_agent_id
                WHERE a.team_id = ? AND a.session_id = ? AND c.deleted_at IS NULL
                ORDER BY c.created_at DESC LIMIT ?
            """
            params = (team_id, session_id, limit)

        elif access_level == 'session_level':
            query = """
                SELECT c.id, c.title, c.content, c.created_at, c.agent_id
                FROM contexts c
                JOIN agents a ON c.agent_id = a.assigned_agent_id
                WHERE a.session_id = ? AND c.deleted_at IS NULL
                ORDER BY c.created_at DESC LIMIT ?
            """
            params = (session_id, limit)

        else:
            raise ValueError(f"Invalid access level: {access_level}")

        cur.execute(query, params)
        results = [dict(r) for r in cur.fetchall()]

        # Log access for audit
        await log_context_access(agent_id, access_level, len(results))

        return results
```

### 2. Permission Validation Middleware

```python
async def validate_permission_change(agent_id: str, new_level: str, requested_by: str) -> bool:
    """Validate if permission change is allowed"""
    with get_connection() as conn:
        cur = conn.cursor()

        # Get current permission info
        cur.execute("""
            SELECT access_level, session_id, team_id
            FROM agents
            WHERE assigned_agent_id = ? AND deleted_at IS NULL
        """, (agent_id,))

        current_info = cur.fetchone()
        if not current_info:
            return False

        current_level, session_id, team_id = current_info

        # Always allow downgrade
        if _is_permission_downgrade(current_level, new_level):
            return True

        # Check if team assignment exists for team_level
        if new_level == 'team_level' and not team_id:
            return False

        # Check if session assignment exists for session_level
        if new_level == 'session_level' and not session_id:
            return False

        # Additional business rules can be added here
        # For now, allow all upgrades with proper justification
        return True

def _is_permission_downgrade(current: str, new: str) -> bool:
    """Check if the permission change is a downgrade (always allowed)"""
    levels = {'self_only': 0, 'team_level': 1, 'session_level': 2}
    return levels.get(new, 0) < levels.get(current, 0)
```

### 3. Real-time Permission Updates

```python
async def update_agent_permission(agent_id: str, new_level: str, granted_by: str,
                                reason: str = None, expires_at: str = None):
    """Update agent permission with real-time notification"""

    if not await validate_permission_change(agent_id, new_level, granted_by):
        raise ValueError("Permission change not allowed")

    def update_permission():
        with get_connection() as conn:
            cur = conn.cursor()

            # Get current permission for audit
            cur.execute("SELECT access_level FROM agents WHERE assigned_agent_id = ?", (agent_id,))
            old_level = cur.fetchone()[0] if cur.fetchone() else None

            # Update agent permission
            cur.execute("""
                UPDATE agents
                SET access_level = ?, permission_granted_by = ?,
                    permission_granted_at = ?, permission_expires_at = ?
                WHERE assigned_agent_id = ?
            """, (new_level, granted_by, datetime.utcnow().isoformat(), expires_at, agent_id))

            # Log to audit table
            audit_id = f"audit_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
            cur.execute("""
                INSERT INTO agent_permission_history
                (id, agent_id, old_access_level, new_access_level, granted_by, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (audit_id, agent_id, old_level, new_level, granted_by, reason))

            conn.commit()

    await enqueue_write(update_permission)

    # Notify all connected clients
    await manager.broadcast({
        "type": "permission_changed",
        "agent_id": agent_id,
        "new_level": new_level,
        "granted_by": granted_by
    })
```

## API Message Schema Updates

### 1. Permission-Aware Read Response

```json
{
    "type": "read_response",
    "resource_type": "contexts",
    "agent_permission": "team_level",
    "access_scope": "team:dev_team",
    "data": [
        {
            "id": "ctx_001",
            "title": "Analysis Results",
            "content": "...",
            "created_at": "2024-01-15T10:30:00Z",
            "agent_id": "agent_002",
            "accessible_reason": "same_team"
        }
    ],
    "total_available": 25,
    "filtered_count": 15
}
```

### 2. Permission Status Messages

```json
{
    "type": "permission_status",
    "agent_id": "agent_001",
    "current_level": "self_only",
    "allowed_levels": ["self_only", "team_level"],
    "restrictions": {
        "team_level": "requires_team_assignment",
        "session_level": "requires_admin_approval"
    },
    "expires_at": null
}
```

### 3. Permission Violation Response

```json
{
    "type": "permission_violation",
    "requested_operation": "read_contexts",
    "required_level": "team_level",
    "current_level": "self_only",
    "message": "Insufficient permissions to access team-level contexts",
    "upgrade_request_url": "/api/request-permission-upgrade"
}
```

## Implementation Plan

### Phase 1: Database Migration (Week 1)
1. **Day 1-2**: Create migration script for new permission fields
2. **Day 3-4**: Add audit tables and indexes
3. **Day 5**: Test migration with existing data
4. **Day 6-7**: Implement rollback procedures

### Phase 2: Backend Logic (Week 2-3)
1. **Week 2**: Implement permission-aware context retrieval
2. **Day 8-10**: Add permission validation middleware
3. **Day 11-12**: Implement real-time permission updates
4. **Day 13-14**: Add audit logging and expiration handling

### Phase 3: GUI Implementation (Week 4-5)
1. **Day 15-17**: Update Agent Registration tab with permission controls
2. **Day 18-20**: Enhance Agent Management tab with permission editing
3. **Day 21**: Add visual permission indicators
4. **Day 22-23**: Implement bulk permission operations

### Phase 4: Integration & Testing (Week 6)
1. **Day 24-25**: Integration testing with existing workflow
2. **Day 26-27**: Permission isolation testing
3. **Day 28**: Performance testing with large datasets
4. **Day 29-30**: User acceptance testing and bug fixes

### Migration Strategy

#### Backward Compatibility Plan
1. **Existing Agents**: Automatically assigned "self_only" permission
2. **Legacy Queries**: Gradual migration with feature flags
3. **API Versioning**: Support both old and new message formats
4. **Graceful Degradation**: Fall back to restrictive permissions on errors

#### Data Migration Script
```sql
-- Phase 1: Add columns with safe defaults
ALTER TABLE agents ADD COLUMN access_level TEXT DEFAULT 'self_only';
ALTER TABLE agents ADD COLUMN permission_granted_by TEXT DEFAULT 'system_migration';
ALTER TABLE agents ADD COLUMN permission_granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Phase 2: Update existing agents based on current team assignments
UPDATE agents
SET access_level = 'team_level',
    permission_granted_by = 'migration_team_assignment'
WHERE team_id IS NOT NULL AND access_level = 'self_only';

-- Phase 3: Create audit entry for migration
INSERT INTO agent_permission_history (id, agent_id, old_access_level, new_access_level, granted_by, reason)
SELECT
    'migration_' || id,
    id,
    'unknown',
    access_level,
    'system_migration',
    'Migrated from legacy system'
FROM agents;
```

## Testing Requirements

### 1. Permission Isolation Tests
```python
def test_self_only_isolation():
    """Test that self_only agents can't access other agent contexts"""
    agent1_contexts = create_test_contexts(agent_id="agent_001", count=5)
    agent2_contexts = create_test_contexts(agent_id="agent_002", count=3)

    # Agent 1 should only see its own contexts
    response = get_contexts_for_agent("agent_001")
    assert len(response) == 5
    assert all(ctx["agent_id"] == "agent_001" for ctx in response)

def test_team_level_access():
    """Test that team_level agents can access team member contexts"""
    assign_agents_to_team(["agent_001", "agent_002"], team="dev_team")
    set_permission(["agent_001", "agent_002"], "team_level")

    agent1_contexts = create_test_contexts(agent_id="agent_001", count=3)
    agent2_contexts = create_test_contexts(agent_id="agent_002", count=2)

    # Agent 1 should see both its own and agent 2's contexts
    response = get_contexts_for_agent("agent_001")
    assert len(response) == 5
    agent_ids = {ctx["agent_id"] for ctx in response}
    assert agent_ids == {"agent_001", "agent_002"}

def test_session_level_access():
    """Test that session_level agents can access all session contexts"""
    assign_agents_to_session(["agent_001", "agent_002", "agent_003"], session="proj_session")
    set_permission(["agent_001"], "session_level")
    set_permission(["agent_002", "agent_003"], "self_only")

    create_test_contexts(agent_id="agent_001", count=2)
    create_test_contexts(agent_id="agent_002", count=3)
    create_test_contexts(agent_id="agent_003", count=1)

    # Agent 1 should see all contexts in session
    response = get_contexts_for_agent("agent_001")
    assert len(response) == 6

    # Agent 2 should only see its own
    response = get_contexts_for_agent("agent_002")
    assert len(response) == 3
    assert all(ctx["agent_id"] == "agent_002" for ctx in response)
```

### 2. Permission Change Tests
```python
def test_permission_upgrade_validation():
    """Test permission upgrade validation logic"""
    agent_id = "agent_001"

    # Should allow upgrade to team_level if team assigned
    assign_to_team(agent_id, "dev_team")
    assert can_upgrade_permission(agent_id, "team_level")

    # Should reject upgrade to team_level if no team
    remove_from_team(agent_id)
    assert not can_upgrade_permission(agent_id, "team_level")

def test_permission_expiration():
    """Test permission expiration handling"""
    agent_id = "agent_001"
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()

    set_permission(agent_id, "session_level", expires_at=expires_at)

    # Should have session access initially
    response = get_contexts_for_agent(agent_id)
    assert get_agent_permission(agent_id) == "session_level"

    # Simulate time passage
    mock_time_advance(hours=2)

    # Should be downgraded to self_only
    response = get_contexts_for_agent(agent_id)
    assert get_agent_permission(agent_id) == "self_only"
```

### 3. GUI Integration Tests
```python
def test_permission_gui_workflow():
    """Test complete permission management through GUI"""
    # Test registration with elevated permissions
    register_agent_with_permission("agent_001", "team_level", reason="Dev collaboration")

    # Test permission change through management tab
    change_agent_permission("agent_001", "session_level", reason="Cross-team project")

    # Test bulk permission operations
    select_multiple_agents(["agent_001", "agent_002", "agent_003"])
    bulk_change_permissions("team_level", reason="Team restructure")

    # Verify all changes reflected in GUI
    assert_permission_indicators_correct()
```

### 4. Performance Tests
```python
def test_permission_query_performance():
    """Test performance of permission-aware queries with large datasets"""
    # Create large dataset
    create_test_agents(count=1000)
    create_test_contexts(count=10000)

    # Test query performance for each permission level
    start_time = time.time()
    self_only_results = get_contexts_for_agent("agent_001", access_level="self_only")
    self_only_time = time.time() - start_time

    start_time = time.time()
    team_results = get_contexts_for_agent("agent_001", access_level="team_level")
    team_time = time.time() - start_time

    start_time = time.time()
    session_results = get_contexts_for_agent("agent_001", access_level="session_level")
    session_time = time.time() - start_time

    # Assert performance requirements
    assert self_only_time < 0.1  # 100ms
    assert team_time < 0.5       # 500ms
    assert session_time < 1.0    # 1 second
```

## Security Considerations

### 1. Permission Escalation Prevention
- All permission upgrades require explicit justification
- Audit trail for all permission changes
- Automatic downgrade on team/session removal
- Time-limited elevated permissions

### 2. Data Isolation Guarantees
- SQL injection prevention through parameterized queries
- Permission validation at multiple layers
- Fail-safe defaults (most restrictive permissions)
- Regular permission audit reports

### 3. Compliance Features
- Comprehensive audit logging
- Permission history retention
- Data access reports
- GDPR-compatible data isolation

## Performance Optimizations

### 1. Permission Caching
```python
# Cache agent permissions for 5 minutes
permission_cache = TTLCache(maxsize=1000, ttl=300)

async def get_cached_agent_permission(agent_id: str) -> dict:
    if agent_id in permission_cache:
        return permission_cache[agent_id]

    permission_info = await get_agent_permission_from_db(agent_id)
    permission_cache[agent_id] = permission_info
    return permission_info
```

### 2. Optimized Queries
- Pre-computed permission materialized views
- Indexed permission columns
- Query result caching for expensive operations
- Batch permission validation

### 3. Real-time Updates
- WebSocket-based permission change notifications
- Selective cache invalidation
- Background permission expiration checking

## Conclusion

This permission system provides a robust, scalable solution for multi-agent context access control while maintaining backward compatibility and performance. The three-tier permission model balances security with collaboration needs, and the comprehensive audit system ensures compliance and accountability.

The implementation plan provides a clear path from the current vulnerable system to a secure, permission-aware architecture that will scale with the organization's multi-agent collaboration requirements.