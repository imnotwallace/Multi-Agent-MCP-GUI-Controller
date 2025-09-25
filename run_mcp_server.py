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
import socket
import ipaddress


def detect_local_host() -> str:
    """Try to determine a sensible local host/address to bind to.

    Preference order:
      1. Non-loopback address for the machine (IPv4) discovered from hostname resolution.
      2. Fallback to 127.0.0.1 if resolution yields loopback or fails.

    This is a lightweight heuristic intended for local development where the host
    may not be reachable via 127.0.0.1 (for example when using a different local DNS
    or container network).
    """
    try:
        hostname = socket.gethostname()
        # Prefer addresses discovered via getaddrinfo so we can pick IPv6 if available
        candidates = []
        try:
            for res in socket.getaddrinfo(hostname, None):
                family, _, _, _, sockaddr = res
                if family == socket.AF_INET6:
                    ip = sockaddr[0]
                    candidates.append((6, ip))
                elif family == socket.AF_INET:
                    ip = sockaddr[0]
                    candidates.append((4, ip))
        except Exception:
            logger.debug("getaddrinfo failed in detect_local_host")

        # Prefer non-loopback IPv6, then non-loopback IPv4
        for fam, ip in candidates:
            try:
                if ip and not ipaddress.ip_address(ip).is_loopback:
                    return ip
            except Exception:
                continue

        # Fallback: try simple hostname-to-IPv4
        try:
            addr = socket.gethostbyname(hostname)
            if addr and not addr.startswith("127."):
                return addr
        except Exception:
            pass
    except Exception:
        logger.debug("Hostname resolution failed when detecting local host")

    # Last resort: loopback
    return "127.0.0.1"


async def _run(host: str = None, port: int = 8765):
    if host is None:
        host = detect_local_host()

    config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    # Make the server accessible to the app so the /shutdown endpoint can set should_exit
    app.state._uvicorn_server = server

    logger.info(f"Starting programmatic uvicorn server on {host}:{port}")
    await server.serve()
    logger.info("Uvicorn server exited")

if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Interrupted")
