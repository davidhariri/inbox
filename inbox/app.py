import os
import secrets
import sqlite3
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from inbox import db
from inbox.auth import InboxAuthProvider
from inbox.routes import health, oauth, pages, projects, tags, todos
from inbox.server import create_mcp


def _get_server_url() -> str:
    port = os.environ.get("PORT", "8000")
    host = os.environ.get("HOST", "localhost")
    scheme = "https" if os.environ.get("RAILWAY_ENVIRONMENT") else "http"
    if os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
        return f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}"
    return f"{scheme}://{host}:{port}"


def _print_setup_banner():
    db_path = db.DATABASE_PATH
    sync_conn = sqlite3.connect(db_path)
    try:
        sync_conn.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        row = sync_conn.execute(
            "SELECT value FROM settings WHERE key = 'setup_complete'"
        ).fetchone()
        if row and row[0] == "true":
            return

        setup_code = secrets.token_hex(4).upper()
        sync_conn.execute(
            "INSERT INTO settings (key, value) VALUES ('setup_code', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = ?",
            (setup_code, setup_code),
        )
        sync_conn.commit()

        url = _get_server_url()
        print("\n┌─────────────────────────────────────────────┐")
        print("│  Inbox is ready for setup.                  │")
        print("│                                             │")
        print(f"│  Visit: {url}/setup")
        print(f"│  Setup code: {setup_code}")
        print("│                                             │")
        print("│  This code expires when setup is complete.  │")
        print("└─────────────────────────────────────────────┘\n")
        sys.stdout.flush()
    finally:
        sync_conn.close()


def create_app() -> FastAPI:
    server_url = _get_server_url()

    _print_setup_banner()

    # Create MCP server with OAuth auth and its ASGI sub-app
    auth_provider = InboxAuthProvider(
        conn=None, server_url=server_url + "/mcp", root_server_url=server_url
    )
    mcp = create_mcp(auth=auth_provider)
    mcp_app = mcp.http_app(path="/", transport="streamable-http")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Initialize DB
        conn = await db.get_db()
        app.state.conn = conn
        # Wire up auth provider's lazy connection
        auth_provider.conn = conn
        app.state.auth_provider = auth_provider

        # Also set module-level conn for MCP tools
        import inbox.server as srv

        srv._conn = conn

        # Enter MCP sub-app lifespan
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

        await conn.close()

    app = FastAPI(
        title="Inbox",
        description="MCP-native todo manager with REST API",
        lifespan=lifespan,
    )

    # Store auth provider on app for test access
    app.state.auth_provider = auth_provider

    # Mount MCP at /mcp
    app.mount("/mcp", mcp_app)

    # Include REST API routers
    app.include_router(health.router)
    app.include_router(oauth.router)
    app.include_router(todos.router)
    app.include_router(projects.router)
    app.include_router(tags.router)
    app.include_router(pages.router)

    return app
