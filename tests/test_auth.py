import bcrypt
from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl

from inbox import db
from inbox.auth import InboxAuthProvider


async def _setup_provider(conn) -> InboxAuthProvider:
    provider = InboxAuthProvider(conn, "http://localhost:8000")
    await db.set_setting(conn, "setup_complete", "true")
    hashed = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode()
    await db.create_user(conn, "owner@test.com", hashed)
    await db.set_setting(conn, "owner_email", "owner@test.com")
    await db.set_setting(conn, "sign_in_policy", "only_me")
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
