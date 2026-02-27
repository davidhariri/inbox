"""End-to-end auth tests through the real ASGI app."""

import time

import bcrypt
import httpx
import pytest

from inbox import db


@pytest.fixture
async def server_app(tmp_path):
    """Create a fully configured server app with a temp DB and seeded owner."""
    db_path = str(tmp_path / "test.db")
    conn = await db.get_db(db_path)

    # Seed owner
    hashed = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode()
    await db.create_user(conn, "owner@test.com", hashed)
    await db.set_setting(conn, "owner_email", "owner@test.com")
    await db.set_setting(conn, "setup_complete", "true")

    # Patch the module-level connection and DB path so the server uses our test DB
    import inbox.server as srv

    original_conn = srv._conn
    srv._conn = conn

    mcp = srv.create_server()
    app = mcp.streamable_http_app()

    yield app

    srv._conn = original_conn
    await conn.close()


@pytest.fixture
async def client(server_app):
    transport = httpx.ASGITransport(app=server_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def test_health_no_auth(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_unauthenticated_request_returns_401(client):
    resp = await client.post("/mcp", json={"jsonrpc": "2.0", "method": "initialize", "id": 1})
    assert resp.status_code == 401


async def test_invalid_token_returns_401(client):
    resp = await client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
        headers={"Authorization": "Bearer garbage-token-that-does-not-exist"},
    )
    assert resp.status_code == 401


async def test_expired_token_returns_401(server_app, tmp_path):
    """Insert a token that's already expired — must get 401, not a crash."""
    import inbox.server as srv

    conn = srv._conn

    # Register a fake client and insert an expired access token
    await db.save_oauth_client(conn, "test-client", "test-secret", '{"client_id": "test-client"}')
    await db.save_oauth_token(
        conn,
        token="expired-token",
        token_type="access",
        client_id="test-client",
        scopes=["inbox"],
        expires_at=int(time.time()) - 3600,  # expired 1 hour ago
    )

    transport = httpx.ASGITransport(app=server_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
            headers={"Authorization": "Bearer expired-token"},
        )
        assert resp.status_code == 401


async def test_valid_token_passes_auth(server_app, tmp_path):
    """A valid, non-expired token should not get 401 or 403."""
    import inbox.server as srv

    conn = srv._conn

    await db.save_oauth_client(conn, "real-client", "real-secret", '{"client_id": "real-client"}')
    await db.save_oauth_token(
        conn,
        token="valid-token",
        token_type="access",
        client_id="real-client",
        scopes=["inbox"],
        expires_at=int(time.time()) + 3600,
    )

    # raise_app_exceptions=False so the session manager RuntimeError becomes a 500
    # rather than propagating — we only care that auth didn't reject us
    transport = httpx.ASGITransport(app=server_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
            headers={"Authorization": "Bearer valid-token"},
        )
        assert resp.status_code not in (401, 403)
