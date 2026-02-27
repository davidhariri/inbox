import bcrypt
import pytest
from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl

from inbox import db
from inbox.auth import InboxAuthProvider


class LazyAuthProvider(InboxAuthProvider):
    """Mirrors the lazy provider in server.py — no self.conn, only _get_conn()."""

    def __init__(self, conn_ref, server_url):
        self._conn_ref = conn_ref
        self.server_url = server_url

    async def _get_conn(self):
        return self._conn_ref


async def _setup_provider(conn, lazy=False) -> InboxAuthProvider:
    if lazy:
        provider = LazyAuthProvider(conn, "http://localhost:8000")
    else:
        provider = InboxAuthProvider(conn, "http://localhost:8000")
    await db.set_setting(conn, "setup_complete", "true")
    hashed = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode()
    await db.create_user(conn, "owner@test.com", hashed)
    await db.set_setting(conn, "owner_email", "owner@test.com")
    return provider


async def test_register_and_get_client(conn):
    provider = await _setup_provider(conn)
    client_info = OAuthClientInformationFull(
        redirect_uris=[AnyUrl("http://localhost/callback")],
    )
    await provider.register_client(client_info)
    assert client_info.client_id is not None

    loaded = await provider.get_client(client_info.client_id)
    assert loaded is not None
    assert loaded.client_id == client_info.client_id


async def test_get_client_not_found(conn):
    provider = await _setup_provider(conn)
    loaded = await provider.get_client("nonexistent")
    assert loaded is None


async def test_authorize_returns_login_url(conn):
    provider = await _setup_provider(conn)
    client_info = OAuthClientInformationFull(
        redirect_uris=[AnyUrl("http://localhost/callback")],
    )
    await provider.register_client(client_info)

    params = AuthorizationParams(
        state="test-state",
        scopes=["inbox"],
        code_challenge="test-challenge",
        redirect_uri=AnyUrl("http://localhost/callback"),
        redirect_uri_provided_explicitly=True,
    )

    redirect_url = await provider.authorize(client_info, params)
    assert "/login?session=" in redirect_url


async def test_full_auth_flow(conn):
    provider = await _setup_provider(conn)

    # Register client
    client_info = OAuthClientInformationFull(
        redirect_uris=[AnyUrl("http://localhost/callback")],
    )
    await provider.register_client(client_info)

    # Authorize
    params = AuthorizationParams(
        state="test-state",
        scopes=["inbox"],
        code_challenge="test-challenge",
        redirect_uri=AnyUrl("http://localhost/callback"),
        redirect_uri_provided_explicitly=True,
    )
    redirect_url = await provider.authorize(client_info, params)
    session_id = redirect_url.split("session=")[1]

    # Complete login
    callback_url = await provider.complete_authorization(
        session_id, "owner@test.com", "password123"
    )
    assert "code=" in callback_url
    assert "state=test-state" in callback_url

    # Extract code
    code = callback_url.split("code=")[1].split("&")[0]

    # Load authorization code
    auth_code = await provider.load_authorization_code(client_info, code)
    assert auth_code is not None

    # Exchange for tokens
    token = await provider.exchange_authorization_code(client_info, auth_code)
    assert token.access_token is not None
    assert token.refresh_token is not None

    # Verify access token
    access = await provider.load_access_token(token.access_token)
    assert access is not None

    # Refresh token
    refresh = await provider.load_refresh_token(client_info, token.refresh_token)
    assert refresh is not None

    new_token = await provider.exchange_refresh_token(client_info, refresh, ["inbox"])
    assert new_token.access_token != token.access_token

    # Revoke
    new_access = await provider.load_access_token(new_token.access_token)
    await provider.revoke_token(new_access)
    assert await provider.load_access_token(new_token.access_token) is None


# --- Lazy provider tests (mirrors production LazyAuthProvider) ---


async def test_lazy_provider_has_no_conn_attr(conn):
    """LazyAuthProvider must not have self.conn — that's the whole point."""
    provider = await _setup_provider(conn, lazy=True)
    assert not hasattr(provider, "conn")


async def test_lazy_full_auth_flow(conn):
    """Full auth flow through the lazy provider catches stray self.conn references."""
    provider = await _setup_provider(conn, lazy=True)

    client_info = OAuthClientInformationFull(
        redirect_uris=[AnyUrl("http://localhost/callback")],
    )
    await provider.register_client(client_info)

    params = AuthorizationParams(
        state="test-state",
        scopes=["inbox"],
        code_challenge="test-challenge",
        redirect_uri=AnyUrl("http://localhost/callback"),
        redirect_uri_provided_explicitly=True,
    )
    redirect_url = await provider.authorize(client_info, params)
    session_id = redirect_url.split("session=")[1]

    callback_url = await provider.complete_authorization(
        session_id, "owner@test.com", "password123"
    )
    assert "code=" in callback_url
    assert "state=test-state" in callback_url

    code = callback_url.split("code=")[1].split("&")[0]

    auth_code = await provider.load_authorization_code(client_info, code)
    assert auth_code is not None

    token = await provider.exchange_authorization_code(client_info, auth_code)
    assert token.access_token is not None
    assert token.refresh_token is not None

    access = await provider.load_access_token(token.access_token)
    assert access is not None

    refresh = await provider.load_refresh_token(client_info, token.refresh_token)
    assert refresh is not None

    new_token = await provider.exchange_refresh_token(client_info, refresh, ["inbox"])
    assert new_token.access_token != token.access_token

    new_access = await provider.load_access_token(new_token.access_token)
    await provider.revoke_token(new_access)
    assert await provider.load_access_token(new_token.access_token) is None


async def test_non_owner_rejected(conn):
    """Non-owner email gets rejected during login."""
    provider = await _setup_provider(conn, lazy=True)

    client_info = OAuthClientInformationFull(
        redirect_uris=[AnyUrl("http://localhost/callback")],
    )
    await provider.register_client(client_info)

    params = AuthorizationParams(
        state="s",
        scopes=["inbox"],
        code_challenge="challenge",
        redirect_uri=AnyUrl("http://localhost/callback"),
        redirect_uri_provided_explicitly=True,
    )
    redirect_url = await provider.authorize(client_info, params)
    session_id = redirect_url.split("session=")[1]

    from mcp.server.auth.provider import AuthorizeError

    with pytest.raises(AuthorizeError) as exc_info:
        await provider.complete_authorization(session_id, "stranger@test.com", "somepassword")
    assert "restricted to the owner" in str(exc_info.value.error_description)
