"""Root-level OAuth endpoints for non-MCP clients."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from mcp.server.auth.handlers.authorize import AuthorizationHandler
from mcp.server.auth.handlers.register import RegistrationHandler
from mcp.server.auth.handlers.revoke import RevocationHandler
from mcp.server.auth.handlers.token import TokenHandler
from mcp.server.auth.middleware.client_auth import ClientAuthenticator
from mcp.shared.auth import OAuthMetadata, ProtectedResourceMetadata
from pydantic import AnyHttpUrl

router = APIRouter()


def _build_root_metadata(root_url: str) -> dict:
    base = root_url.rstrip("/")
    metadata = OAuthMetadata(
        issuer=AnyHttpUrl(base),
        authorization_endpoint=AnyHttpUrl(f"{base}/authorize"),
        token_endpoint=AnyHttpUrl(f"{base}/token"),
        registration_endpoint=AnyHttpUrl(f"{base}/register"),
        revocation_endpoint=AnyHttpUrl(f"{base}/revoke"),
        scopes_supported=["inbox"],
        response_types_supported=["code"],
        grant_types_supported=["authorization_code", "refresh_token"],
        token_endpoint_auth_methods_supported=["client_secret_post", "client_secret_basic"],
        code_challenge_methods_supported=["S256"],
        revocation_endpoint_auth_methods_supported=["client_secret_post", "client_secret_basic"],
    )
    return metadata.model_dump(exclude_none=True, mode="json")


@router.get("/.well-known/oauth-authorization-server")
async def oauth_metadata(request: Request):
    auth = request.app.state.auth_provider
    return JSONResponse(
        content=_build_root_metadata(auth.root_server_url),
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/.well-known/oauth-protected-resource/mcp/")
@router.get("/.well-known/oauth-protected-resource/mcp")
async def protected_resource_metadata(request: Request):
    auth = request.app.state.auth_provider
    base = auth.root_server_url.rstrip("/")
    metadata = ProtectedResourceMetadata(
        resource=AnyHttpUrl(f"{base}/mcp"),
        authorization_servers=[AnyHttpUrl(base)],
        scopes_supported=["inbox"],
    )
    return JSONResponse(
        content=metadata.model_dump(exclude_none=True, mode="json"),
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/authorize")
async def authorize(request: Request):
    auth = request.app.state.auth_provider
    handler = AuthorizationHandler(auth)
    return await handler.handle(request)


@router.post("/token")
async def token(request: Request):
    auth = request.app.state.auth_provider
    authenticator = ClientAuthenticator(auth)
    handler = TokenHandler(auth, authenticator)
    return await handler.handle(request)


@router.post("/register")
async def register(request: Request):
    from mcp.server.auth.settings import ClientRegistrationOptions

    auth = request.app.state.auth_provider
    handler = RegistrationHandler(
        auth,
        options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=["inbox"],
            default_scopes=["inbox"],
        ),
    )
    return await handler.handle(request)


@router.post("/revoke")
async def revoke(request: Request):
    auth = request.app.state.auth_provider
    authenticator = ClientAuthenticator(auth)
    handler = RevocationHandler(auth, authenticator)
    return await handler.handle(request)
