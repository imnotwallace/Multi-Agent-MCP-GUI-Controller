# This file has been removed after migration.
"""Lightweight MCP server for AI clients

Provides:
- REST endpoints to list projects/sessions/agents
- WebSocket endpoint for AI clients to connect and send/receive MCP-style messages

Run with:
    uvicorn mcp_server:app --host 127.0.0.1 --port 8765

The server uses the same SQLite database file used by the GUI app
("multi-agent_mcp_context_manager.db"). No authentication is implemented by default.
"""
from typing import Dict, Any
import json
import sqlite3
import asyncio
import logging
from contextlib import contextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi import Request, HTTPException
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_server")

app = FastAPI(title="MCP Server")
DB_PATH = "multi-agent_mcp_context_manager.db"


# Agent allowlist: if non-empty, only these agent IDs may announce themselves.
# Sources (checked in order): env MCP_AGENT_ALLOWLIST (comma-separated), file MCP_AGENT_ALLOWLIST_FILE or ~/.mcp_allowlist.txt
def _load_agent_allowlist():
    allow = set()
    env = os.environ.get('MCP_AGENT_ALLOWLIST', '')
    if env:
        for p in [x.strip() for x in env.split(',') if x.strip()]:
            allow.add(p)

    path = os.environ.get('MCP_AGENT_ALLOWLIST_FILE') or os.path.expanduser('~/.mcp_allowlist.txt')
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        allow.add(line)
    except Exception:
        logger.exception('Failed to read agent allowlist file')

    return allow


AGENT_ALLOWLIST = _load_agent_allowlist()


def _is_agent_allowed(agent_id: str) -> bool:
    if not AGENT_ALLOWLIST:
        return True
    return agent_id in AGENT_ALLOWLIST

# Exponential backoff timings in seconds: 100ms, 200ms, 500ms, 1000ms, 2000ms, 5000ms
BACKOFFS = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]


async def run_db_write_with_backoff(fn, *args, **kwargs):
    """Run a synchronous DB write function in a thread with exponential backoff retries.

    fn should be a callable that performs the DB write (expects to open/commit its own connection).
    This helper will retry on sqlite3.OperationalError/`database is locked`/`busy` errors.
    """
    last_exc = None
    for delay in BACKOFFS:
        try:
            # Run blocking DB work in a thread so event loop isn't blocked
            return await asyncio.to_thread(fn, *args, **kwargs)
        except sqlite3.OperationalError as e:
            last_exc = e
            msg = str(e).lower()
            if "locked" in msg or "busy" in msg:
                logger.warning(f"DB busy; retrying after {int(delay*1000)}ms: {e}")
                await asyncio.sleep(delay)
                continue
            raise
    # Exhausted retries
    raise last_exc


def run_db_write_with_backoff_sync(fn, *args, **kwargs):
    """Synchronous variant: useful for calling code that isn't async.

    Retries on sqlite3.OperationalError with the same backoff schedule.
    """
    import time

    last_exc = None
    for delay in BACKOFFS:
        try:
            return fn(*args, **kwargs)
        except sqlite3.OperationalError as e:
            last_exc = e
            msg = str(e).lower()
            if "locked" in msg or "busy" in msg:
                logger.warning(f"DB busy; retrying after {int(delay*1000)}ms: {e}")
                time.sleep(delay)
                continue
            raise
    raise last_exc

@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Improve concurrency for multiple readers/writers
        # Enable foreign keys, WAL mode and a busy timeout so writers retry instead of failing immediately
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA busy_timeout = 5000")
        except Exception:
            # If PRAGMA fails for any reason, continue with the connection (best-effort)
            logger.exception("Failed to set PRAGMA on connection")

        yield conn
    finally:
        conn.close()

# Simple REST endpoints
@app.get("/projects")
async def list_projects():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, description, created_at FROM projects WHERE deleted_at IS NULL ORDER BY name")
        rows = [dict(r) for r in cur.fetchall()]
    return JSONResponse(content={"projects": rows})

@app.get("/sessions")
async def list_sessions():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, project_id, description, created_at FROM sessions WHERE deleted_at IS NULL ORDER BY project_id, name")
        rows = [dict(r) for r in cur.fetchall()]
    return JSONResponse(content={"sessions": rows})

@app.get("/agents")
async def list_agents():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, session_id, status, last_active FROM agents WHERE deleted_at IS NULL")
        rows = [dict(r) for r in cur.fetchall()]
    return JSONResponse(content={"agents": rows})

# WebSocket endpoint - simple echo / broker for MCP messages
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.lock = asyncio.Lock()

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.active_connections[client_id] = websocket
        logger.info(f"Client connected: {client_id}")

    async def disconnect(self, client_id: str):
        async with self.lock:
            ws = self.active_connections.pop(client_id, None)
            if ws:
                try:
                    # Check if the connection is still open before attempting to close
                    if not ws.client_state.name == 'DISCONNECTED':
                        await ws.close()
                except Exception:
                    pass  # Ignore close errors as connection may already be closed
        logger.info(f"Client disconnected: {client_id}")

    async def send_json(self, client_id: str, message: Dict[str, Any]):
        ws = self.active_connections.get(client_id)
        if ws:
            await ws.send_json(message)

    async def broadcast(self, message: Dict[str, Any]):
        async with self.lock:
            for ws in list(self.active_connections.values()):
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

manager = ConnectionManager()


# Single-writer queue to serialize DB writes and avoid SQLITE_BUSY under contention
write_queue: asyncio.Queue


async def writer_worker():
    """Background worker that consumes write jobs from write_queue.

    Each job is a tuple: (fn, args, kwargs, future)
    fn is a synchronous callable; we use run_db_write_with_backoff (async) which will run it in a thread.
    """
    global write_queue
    while True:
        job = await write_queue.get()
        if job is None:
            # Shutdown sentinel
            write_queue.task_done()
            break

        fn, args, kwargs, fut = job
        try:
            result = await run_db_write_with_backoff(fn, *args, **kwargs)
            if fut and not fut.done():
                fut.set_result(result)
        except Exception as e:
            logger.exception(f"Writer worker failed for job {fn}: {e}")
            if fut and not fut.done():
                fut.set_exception(e)
        finally:
            write_queue.task_done()


async def enqueue_write(fn, *args, **kwargs):
    """Enqueue a DB write job and await its completion.

    Returns the result of fn when the write completes, or raises the exception from fn.
    """
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    await write_queue.put((fn, args, kwargs, fut))
    return await fut


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    global write_queue
    write_queue = asyncio.Queue()
    # Start the writer worker
    loop = asyncio.get_running_loop()
    app.state._writer_task = loop.create_task(writer_worker())
    logger.info("Writer worker started")
    try:
        yield
    finally:
        # Send shutdown sentinel and wait for worker to finish
        if write_queue is not None:
            await write_queue.put(None)
            await write_queue.join()
        # Cancel task if still running
        task = getattr(app.state, "_writer_task", None)
        if task:
            task.cancel()
            try:
                await task
            except Exception:
                pass
        logger.info("Writer worker stopped")

app = FastAPI(title="MCP Server", lifespan=lifespan)


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Enhanced MCP endpoint with tool selection and registration workflow

    Expected message format: [agent, action, data]

    Initial workflow:
    1. Agent connects and receives tool selection prompt
    2. Agent responds with tool selection
    3. If "register" selected, registration process begins
    4. If "read" or "write" selected, agent must provide assigned_agent_id
    """
    await manager.connect(client_id, websocket)

    # Send initial tool selection prompt
    await manager.send_json(client_id, {
        "type": "tool_selection_prompt",
        "available_tools": ["register", "read", "write"],
        "message": "Please select a tool to continue: register (new agent), read (read-only access), write (read-write access)"
    })

    try:
        while True:
            data = await websocket.receive_text()
            try:
                # Parse new message schema [agent, action, data]
                if data.startswith('[') and data.endswith(']'):
                    msg_array = json.loads(data)
                    if len(msg_array) == 3:
                        agent, action, msg_data = msg_array
                        msg = {"agent": agent, "action": action, "data": msg_data}
                    else:
                        raise ValueError("Invalid message format")
                else:
                    # Fallback for legacy messages
                    msg = json.loads(data)
                    # Convert to new format if possible
                    if "agent_id" in msg:
                        agent = msg.get("agent_id", client_id)
                        action = msg.get("type", "unknown")
                        msg = {"agent": agent, "action": action, "data": msg}
                    else:
                        msg = {"agent": client_id, "action": "legacy", "data": msg}
            except Exception:
                msg = {"agent": client_id, "action": "raw", "data": {"payload": data}}

            logger.info(f"Received from {client_id}: {msg}")

            # Handle tool selection
            if msg.get("action") == "select_tool":
                await handle_tool_selection(client_id, websocket, msg)
                continue

            # Handle registration process
            if msg.get("action") == "register":
                await handle_agent_registration(client_id, websocket, msg)
                continue

            # Handle authentication for existing agents
            if msg.get("action") == "authenticate":
                await handle_agent_authentication(client_id, websocket, msg)
                continue

            # Handle read/write operations
            if msg.get("action") in ["read", "write"]:
                await handle_agent_operation(client_id, websocket, msg)
                continue

            # Legacy support for announce messages
            if msg.get("action") == "announce" or (isinstance(msg.get("data"), dict) and msg["data"].get("type") == "announce"):
                await handle_legacy_announce(client_id, websocket, msg)
                continue

            # Handle context requests (legacy support)
            if msg.get("action") == "request_contexts" or (isinstance(msg.get("data"), dict) and msg["data"].get("type") == "request_contexts"):
                await handle_context_request(client_id, websocket, msg)
                continue

            # Echo for unhandled messages
            await manager.send_json(client_id, {"type": "echo", "original": msg})

    except WebSocketDisconnect:
        await handle_agent_disconnect(client_id)
    except Exception as e:
        logger.exception(f"WebSocket error for {client_id}: {e}")
        await manager.disconnect(client_id)

async def handle_tool_selection(client_id: str, websocket: WebSocket, msg: dict):
    """Handle agent tool selection"""
    selected_tool = msg.get("data", {}).get("tool")
    agent_name = msg.get("data", {}).get("name", f"Agent_{client_id}")

    if selected_tool not in ["register", "read", "write"]:
        await manager.send_json(client_id, {
            "type": "error",
            "message": "Invalid tool selection. Must be 'register', 'read', or 'write'"
        })
        return

    if selected_tool == "register":
        # Start registration process
        await handle_agent_registration(client_id, websocket, msg)
    else:
        # For read/write, require existing agent_id
        await manager.send_json(client_id, {
            "type": "agent_id_required",
            "message": f"To use '{selected_tool}' tool, provide your assigned agent_id",
            "expected_format": f'["{client_id}", "authenticate", {{"agent_id": "your_assigned_id"}}]'
        })

async def handle_agent_registration(client_id: str, websocket: WebSocket, msg: dict):
    """Handle new agent registration"""
    agent_name = msg.get("data", {}).get("name", f"Agent_{client_id}")
    capabilities = msg.get("data", {}).get("capabilities", {})

    def create_pending_agent(name: str, connection_id: str, caps: dict):
        with get_connection() as conn:
            cur = conn.cursor()
            agent_id = f"pending_{connection_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            timestamp = datetime.utcnow().strftime('%H%M%S')
            unique_name = f"{name}_{timestamp}"

            # Use INSERT OR REPLACE to handle duplicate names
            cur.execute(
                """INSERT OR REPLACE INTO agents
                   (id, name, connection_id, registration_status, selected_tool, capabilities, status, last_active, access_level, permission_granted_at)
                   VALUES (?, ?, ?, 'pending', 'register', ?, 'connected', ?, 'self_only', ?)""",
                (agent_id, unique_name, connection_id, json.dumps(caps), datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
            )
            conn.commit()
            return agent_id

    try:
        agent_id = await enqueue_write(create_pending_agent, agent_name, client_id, capabilities)
        await manager.send_json(client_id, {
            "type": "registration_success",
            "agent_id": agent_id,
            "status": "pending",
            "message": "Registration successful. Waiting for human assignment of permanent agent_id."
        })

        # Notify GUI of new pending agent
        await manager.broadcast({
            "type": "new_pending_agent",
            "agent_id": agent_id,
            "name": agent_name,
            "connection_id": client_id
        })

    except Exception as e:
        logger.exception(f"Registration failed for {client_id}: {e}")
        await manager.send_json(client_id, {
            "type": "error",
            "message": "Registration failed"
        })

async def handle_agent_authentication(client_id: str, websocket: WebSocket, msg: dict):
    """Handle agent authentication with assigned agent_id"""
    assigned_agent_id = msg.get("data", {}).get("agent_id")

    if not assigned_agent_id:
        await manager.send_json(client_id, {
            "type": "error",
            "message": "agent_id required for authentication"
        })
        return

    # Verify agent exists and is assigned
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT registration_status, selected_tool, name FROM agents WHERE assigned_agent_id = ? AND deleted_at IS NULL",
            (assigned_agent_id,)
        )
        result = cur.fetchone()

        if not result:
            await manager.send_json(client_id, {
                "type": "error",
                "message": "Invalid agent_id or agent not found"
            })
            return

        if result[0] != "assigned":
            await manager.send_json(client_id, {
                "type": "error",
                "message": "Agent not yet assigned by human administrator"
            })
            return

        # Update connection status
        cur.execute(
            "UPDATE agents SET status = 'connected', last_active = ?, connection_id = ? WHERE assigned_agent_id = ?",
            (datetime.utcnow().isoformat(), client_id, assigned_agent_id)
        )
        conn.commit()

        await manager.send_json(client_id, {
            "type": "authentication_success",
            "agent_id": assigned_agent_id,
            "agent_name": result[2],
            "tool": result[1],
            "message": f"Authentication successful. You can now use {result[1]} operations."
        })

async def handle_agent_operation(client_id: str, websocket: WebSocket, msg: dict):
    """Handle read/write operations from authenticated agents"""
    assigned_agent_id = msg.get("data", {}).get("agent_id") or msg.get("agent")
    action = msg.get("action")

    if not assigned_agent_id:
        await manager.send_json(client_id, {
            "type": "error",
            "message": "agent_id required for read/write operations"
        })
        return

    # Verify agent exists and is assigned
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT registration_status, selected_tool FROM agents WHERE assigned_agent_id = ? AND deleted_at IS NULL",
            (assigned_agent_id,)
        )
        result = cur.fetchone()

        if not result:
            await manager.send_json(client_id, {
                "type": "error",
                "message": "Invalid agent_id or agent not found"
            })
            return

        if result[0] != "assigned":
            await manager.send_json(client_id, {
                "type": "error",
                "message": "Agent not yet assigned by human administrator"
            })
            return

    # Handle specific operations based on action
    if action == "read":
        await handle_read_operation(client_id, assigned_agent_id, msg.get("data", {}))
    elif action == "write":
        await handle_write_operation(client_id, assigned_agent_id, msg.get("data", {}))

async def handle_read_operation(client_id: str, agent_id: str, data: dict):
    """Handle read operations with permission-aware context retrieval"""
    resource_type = data.get("resource_type", "contexts")
    limit = data.get("limit", 10)

    with get_connection() as conn:
        cur = conn.cursor()
        if resource_type == "contexts":
            # First get the requesting agent's information and access level
            cur.execute(
                """SELECT a.id, a.access_level, a.session_id, a.team_id
                   FROM agents a
                   WHERE a.assigned_agent_id = ? AND a.deleted_at IS NULL""",
                (agent_id,)
            )
            agent_info = cur.fetchone()

            if not agent_info:
                await manager.send_json(client_id, {
                    "type": "error",
                    "message": "Agent not found or not authorized",
                    "access_level": None
                })
                return

            requesting_agent_id, access_level, session_id, team_id = agent_info

            # Build query based on access level
            if access_level == "session_level":
                # Can read contexts from all agents in the session
                query = """
                    SELECT c.id, c.title, c.content, c.created_at, c.agent_id
                    FROM contexts c
                    JOIN agents a ON c.agent_id = a.id
                    WHERE a.session_id = ? AND c.deleted_at IS NULL
                    ORDER BY c.created_at DESC LIMIT ?
                """
                params = (session_id, limit)
            elif access_level == "team_level" and team_id:
                # Can read contexts from agents in the same team within the session
                query = """
                    SELECT c.id, c.title, c.content, c.created_at, c.agent_id
                    FROM contexts c
                    JOIN agents a ON c.agent_id = a.id
                    WHERE a.team_id = ? AND a.session_id = ? AND c.deleted_at IS NULL
                    ORDER BY c.created_at DESC LIMIT ?
                """
                params = (team_id, session_id, limit)
            else:
                # Default: self_only - can only read own contexts
                query = """
                    SELECT c.id, c.title, c.content, c.created_at, c.agent_id
                    FROM contexts c
                    WHERE c.agent_id = ? AND c.deleted_at IS NULL
                    ORDER BY c.created_at DESC LIMIT ?
                """
                params = (requesting_agent_id, limit)

            cur.execute(query, params)
            results = [dict(r) for r in cur.fetchall()]

            await manager.send_json(client_id, {
                "type": "read_response",
                "resource_type": resource_type,
                "access_level": access_level,
                "data": results,
                "count": len(results)
            })

async def handle_write_operation(client_id: str, agent_id: str, data: dict):
    """Handle write operations"""
    resource_type = data.get("resource_type", "contexts")
    content = data.get("content", {})

    if resource_type == "contexts":
        def write_context():
            with get_connection() as conn:
                cur = conn.cursor()
                # Get agent's session
                cur.execute(
                    "SELECT session_id, project_id FROM agents a JOIN sessions s ON a.session_id = s.id WHERE a.assigned_agent_id = ?",
                    (agent_id,)
                )
                result = cur.fetchone()
                if not result:
                    raise ValueError("Agent not assigned to a session")

                session_id, project_id = result
                context_id = f"ctx_{session_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"

                cur.execute(
                    """INSERT INTO contexts (id, title, content, project_id, session_id, agent_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (context_id, content.get("title", ""), content.get("content", ""),
                     project_id, session_id, agent_id, datetime.utcnow().isoformat())
                )
                conn.commit()
                return context_id

        try:
            context_id = await enqueue_write(write_context)
            await manager.send_json(client_id, {
                "type": "write_response",
                "resource_type": resource_type,
                "context_id": context_id,
                "status": "success"
            })
        except Exception as e:
            await manager.send_json(client_id, {
                "type": "error",
                "message": f"Write operation failed: {str(e)}"
            })

async def handle_legacy_announce(client_id: str, websocket: WebSocket, msg: dict):
    """Handle legacy announce messages for backward compatibility"""
    data = msg.get("data", {}) if isinstance(msg.get("data"), dict) else msg
    agent_id = data.get("agent_id")
    name = data.get("name") or agent_id

    if not agent_id:
        await manager.send_json(client_id, {
            "type": "error",
            "message": "agent_id required for announce"
        })
        return

    # Enforce allowlist if configured
    if not _is_agent_allowed(agent_id):
        logger.info(f"Rejected announce from non-allowlisted agent: {agent_id}")
        await manager.send_json(client_id, {
            "type": "announce_rejected",
            "agent_id": agent_id,
            "reason": "not_allowlisted"
        })
        await websocket.close()
        await manager.disconnect(client_id)
        return

    def upsert_agent(aid, aname):
        with get_connection() as conn:
            cur = conn.cursor()
            # Legacy agents get assigned status with their ID as assigned_agent_id
            cur.execute(
                """INSERT INTO agents (id, name, status, last_active, registration_status, selected_tool, assigned_agent_id, access_level, permission_granted_at)
                   VALUES (?, ?, 'connected', ?, 'assigned', 'write', ?, 'self_only', ?)
                   ON CONFLICT(name) DO UPDATE SET
                   status='connected',
                   last_active=excluded.last_active,
                   connection_id=?""",
                (aid, aname, datetime.utcnow().isoformat(), aid, datetime.utcnow().isoformat(), client_id)
            )
            conn.commit()

    try:
        await enqueue_write(upsert_agent, agent_id, name)
        await manager.broadcast({"type": "agent_status", "agent_id": agent_id, "status": "connected"})
        await manager.send_json(client_id, {"type": "announce_ack", "agent_id": agent_id})
    except Exception as e:
        logger.exception(f"Failed to persist announce for {agent_id}: {e}")

async def handle_context_request(client_id: str, websocket: WebSocket, msg: dict):
    """Handle context requests for backward compatibility"""
    data = msg.get("data", {}) if isinstance(msg.get("data"), dict) else msg
    agent_id = data.get("agent_id")
    limit = int(data.get("limit", 5))

    if not agent_id:
        await manager.send_json(client_id, {
            "type": "error",
            "message": "agent_id required for context request"
        })
        return

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, created_at FROM contexts WHERE agent_id = ? AND deleted_at IS NULL ORDER BY created_at DESC LIMIT ?",
            (agent_id, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
    await manager.send_json(client_id, {"type": "contexts", "agent_id": agent_id, "results": rows})

async def handle_agent_disconnect(client_id: str):
    """Handle agent disconnection with proper cleanup"""
    def update_agent_status():
        with get_connection() as conn:
            cur = conn.cursor()
            # Update status and clear connection_id for proper cleanup
            cur.execute(
                "UPDATE agents SET status = 'disconnected', last_active = ?, connection_id = NULL WHERE connection_id = ?",
                (datetime.utcnow().isoformat(), client_id)
            )
            conn.commit()

    try:
        await enqueue_write(update_agent_status)
        logger.info(f"Updated disconnect status for client {client_id}")
    except Exception:
        logger.exception(f"Failed to update disconnect status for {client_id}")

    try:
        await manager.disconnect(client_id)
    except Exception:
        logger.exception(f"Failed to disconnect client {client_id} from manager")

# Health check
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/shutdown")
async def shutdown(request: Request):
    """Shutdown the server. Only allowed from localhost to avoid remote abuse.

    This endpoint will schedule the lifespan shutdown by cancelling the writer worker
    and returning a confirmation. It is purposely simple and intended for local
    development only. For production, protect with authentication.
    """
    # Local-only guard
    client = request.client
    if not client or client.host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Optional shutdown token: if MCP_SHUTDOWN_TOKEN is set in environment, require it.
    expected_token = os.environ.get("MCP_SHUTDOWN_TOKEN")
    if expected_token:
        # Accept either Authorization: Bearer <token> or X-Admin-Token header
        auth = request.headers.get("authorization", "")
        token_header = request.headers.get("x-admin-token", "")
        token = ""
        if auth.lower().startswith("bearer "):
            token = auth[7:]
        elif token_header:
            token = token_header

        if token != expected_token:
            raise HTTPException(status_code=403, detail="Forbidden - invalid token")

    # Graceful shutdown: enqueue sentinel and wait for writer to drain
    try:
        if write_queue is not None:
            # Enqueue sentinel to indicate no more work
            await write_queue.put(None)
            # Wait until all queued jobs are processed
            await write_queue.join()

        # If the server was started programmatically via `run_mcp_server.py`,
        # the running uvicorn.Server instance is stored in app.state._uvicorn_server.
        # Set its should_exit flag so the server stops gracefully.
        server = getattr(app.state, "_uvicorn_server", None)
        if server is not None:
            try:
                server.should_exit = True
                logger.info("Programmatic server stop requested (server.should_exit=True)")
            except Exception:
                logger.exception("Failed to set server.should_exit")

    except Exception as e:
        logger.exception("Shutdown request failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    return JSONResponse(content={"status": "drained"})
