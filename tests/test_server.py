"""End-to-end tests through the FastAPI app."""

import secrets
import time

import bcrypt
import httpx
import pytest

from inbox import db


@pytest.fixture
async def server_app(tmp_path):
    """Create a fully configured FastAPI app with a temp DB and seeded owner."""
    db_path = str(tmp_path / "test.db")
    conn = await db.get_db(db_path)

    # Seed owner
    hashed = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode()
    await db.create_user(conn, "owner@test.com", hashed)
    await db.set_setting(conn, "owner_email", "owner@test.com")
    await db.set_setting(conn, "setup_complete", "true")

    from inbox.app import create_app

    app = create_app()
    app.state.conn = conn

    # Wire up MCP module-level conn
    import inbox.server as srv

    original_conn = srv._conn
    srv._conn = conn

    # Wire up the auth provider that's already embedded in the app/MCP
    app.state.auth_provider.conn = conn

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


async def test_unauthenticated_rest_returns_401(client):
    resp = await client.get("/api/todos")
    assert resp.status_code in (401, 403)


async def test_oauth_token_grants_rest_access(server_app, client):
    conn = server_app.state.conn
    token = secrets.token_hex(32)
    await db.save_oauth_client(conn, "rest-client", "s", '{"client_id": "rest-client"}')
    await db.save_oauth_token(
        conn,
        token=token,
        token_type="access",
        client_id="rest-client",
        scopes=["inbox"],
        expires_at=int(time.time()) + 3600,
    )

    resp = await client.get(
        "/api/todos",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


async def test_invalid_oauth_token_returns_401(client):
    resp = await client.get(
        "/api/todos",
        headers={"Authorization": "Bearer garbage-token"},
    )
    assert resp.status_code in (401, 403)


async def test_expired_oauth_token_returns_401(server_app, client):
    conn = server_app.state.conn
    await db.save_oauth_client(conn, "exp-client", "s", '{"client_id": "exp-client"}')
    await db.save_oauth_token(
        conn,
        token="expired-rest-token",
        token_type="access",
        client_id="exp-client",
        scopes=["inbox"],
        expires_at=int(time.time()) - 3600,
    )

    resp = await client.get(
        "/api/todos",
        headers={"Authorization": "Bearer expired-rest-token"},
    )
    assert resp.status_code in (401, 403)


async def test_mcp_unauthenticated_returns_401(client):
    resp = await client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
    )
    assert resp.status_code == 401


async def test_mcp_invalid_token_returns_401(client):
    resp = await client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
        headers={"Authorization": "Bearer garbage-token-that-does-not-exist"},
    )
    assert resp.status_code == 401


async def test_mcp_expired_token_returns_401(server_app, tmp_path):
    conn = server_app.state.conn
    await db.save_oauth_client(conn, "test-client", "test-secret", '{"client_id": "test-client"}')
    await db.save_oauth_token(
        conn,
        token="expired-token",
        token_type="access",
        client_id="test-client",
        scopes=["inbox"],
        expires_at=int(time.time()) - 3600,
    )

    transport = httpx.ASGITransport(app=server_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
            headers={"Authorization": "Bearer expired-token"},
        )
        assert resp.status_code == 401


async def test_mcp_valid_token_passes_auth(server_app, tmp_path):
    conn = server_app.state.conn
    await db.save_oauth_client(conn, "real-client", "real-secret", '{"client_id": "real-client"}')
    await db.save_oauth_token(
        conn,
        token="valid-token",
        token_type="access",
        client_id="real-client",
        scopes=["inbox"],
        expires_at=int(time.time()) + 3600,
    )

    transport = httpx.ASGITransport(app=server_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
            headers={"Authorization": "Bearer valid-token"},
        )
        assert resp.status_code not in (401, 403)
