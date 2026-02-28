import secrets
import time

import bcrypt
import httpx
import pytest

from inbox import db


@pytest.fixture
async def conn():
    """Fresh in-memory database for each test."""
    connection = await db.get_db(":memory:")
    # Mark setup as complete so tools work without auth flow
    await db.set_setting(connection, "setup_complete", "true")
    yield connection
    await connection.close()


@pytest.fixture
async def api_client(conn):
    """FastAPI test client with an OAuth access token."""
    from inbox.app import create_app

    app = create_app()
    app.state.conn = conn
    app.state.auth_provider.conn = conn

    # Also wire up module-level conn for MCP tools
    import inbox.server as srv

    srv._conn = conn

    # Seed owner
    hashed = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode()
    await db.create_user(conn, "owner@test.com", hashed)
    await db.set_setting(conn, "owner_email", "owner@test.com")

    # Seed an OAuth access token
    token = secrets.token_hex(32)
    await db.save_oauth_client(conn, "test-client", "test-secret", '{"client_id": "test-client"}')
    await db.save_oauth_token(
        conn,
        token=token,
        token_type="access",
        client_id="test-client",
        scopes=["inbox"],
        expires_at=int(time.time()) + 3600,
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client
