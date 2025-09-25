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
                await ws.close()
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
    """Clients should connect to ws://host:port/ws/<client_id>

    A simple MCP message format (JSON) is expected, e.g.:
    {"type": "announce", "agent_id": "agent_x", "capabilities": {...}}
    {"type": "request_context", "session_id": "sess_proj_x_x", "max_tokens": 1024}

    The server will echo the message back and can be extended to broker messages between clients.
    """
    await manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except Exception:
                msg = {"type": "raw", "payload": data}

            logger.info(f"Received from {client_id}: {msg}")

            # Very small example: if client asks for latest contexts for an agent
            if isinstance(msg, dict) and msg.get("type") == "request_contexts":
                agent_id = msg.get("agent_id")
                limit = int(msg.get("limit", 5))
                with get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT id, title, created_at FROM contexts WHERE agent_id = ? AND deleted_at IS NULL ORDER BY created_at DESC LIMIT ?",
                        (agent_id, limit),
                    )
                    rows = [dict(r) for r in cur.fetchall()]
                await manager.send_json(client_id, {"type": "contexts", "agent_id": agent_id, "results": rows})
                continue

            # Persist announce messages via the writer queue
            if isinstance(msg, dict) and msg.get("type") == "announce":
                agent_id = msg.get("agent_id")
                name = msg.get("name") or msg.get("agent_id")

                def upsert_agent(aid, aname):
                    with get_connection() as conn:
                        cur = conn.cursor()
                        # Simple upsert: insert or update status/last_active
                        cur.execute(
                            "INSERT INTO agents (id, name, status, last_active) VALUES (?, ?, 'connected', ?)"
                            " ON CONFLICT(id) DO UPDATE SET name=excluded.name, status='connected', last_active=excluded.last_active",
                            (aid, aname, datetime.utcnow().isoformat()),
                        )
                        conn.commit()

                # Enqueue and don't block other websocket operations while waiting
                try:
                    await enqueue_write(upsert_agent, agent_id, name)
                except Exception as e:
                    logger.exception(f"Failed to persist announce for {agent_id}: {e}")
                # Also notify other clients about agent connect
                await manager.broadcast({"type": "agent_status", "agent_id": agent_id, "status": "connected"})
                # Echo acknowledgement
                await manager.send_json(client_id, {"type": "announce_ack", "agent_id": agent_id})
                continue

            # Echo back for now
            await manager.send_json(client_id, {"type": "echo", "original": msg})

    except WebSocketDisconnect:
        await manager.disconnect(client_id)
    except Exception as e:
        logger.exception(f"WebSocket error for {client_id}: {e}")
        await manager.disconnect(client_id)

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
