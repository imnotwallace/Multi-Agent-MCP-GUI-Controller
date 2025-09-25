"""Programmatic runner for the MCP FastAPI app.

Use this to start the server from Python so the app can request a programmatic shutdown
via setting server.should_exit = True (the /shutdown endpoint will attempt this).

Run with:
    python run_mcp_server.py

"""
import asyncio
import logging
from mcp_server import app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_mcp_server")

import uvicorn

async def _run():
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8765, log_level="info")
    server = uvicorn.Server(config)

    # Make the server accessible to the app so the /shutdown endpoint can set should_exit
    app.state._uvicorn_server = server

    logger.info("Starting programmatic uvicorn server")
    await server.serve()
    logger.info("Uvicorn server exited")

if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Interrupted")
