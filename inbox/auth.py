import json
import secrets
import time

import bcrypt
from fastmcp.server.auth.auth import ClientRegistrationOptions, OAuthProvider, RevocationOptions
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl

from inbox import db


class InboxAuthProvider(OAuthProvider):
    def __init__(self, conn, server_url: str):
        super().__init__(
            base_url=server_url,
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=["inbox"],
                default_scopes=["inbox"],
            ),
            revocation_options=RevocationOptions(enabled=True),
            required_scopes=[],
        )
        self.conn = conn
        self.server_url = server_url

    async def _get_conn(self):
        return self.conn

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        row = await db.get_oauth_client(await self._get_conn(), client_id)
        if not row:
            return None
        return OAuthClientInformationFull(**json.loads(row["client_info"]))

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        await db.save_oauth_client(
            await self._get_conn(),
            client_info.client_id,
            client_info.client_secret,
            client_info.model_dump_json(),
        )

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        setup_done = await db.is_setup_complete(await self._get_conn())
        if not setup_done:
            raise AuthorizeError(
                error="temporarily_unavailable",
                error_description="Setup not complete",
            )

        session_id = secrets.token_hex(16)
        await db.set_setting(
            await self._get_conn(),
            f"auth_session:{session_id}",
            json.dumps(
                {
                    "client_id": client.client_id,
                    "redirect_uri": str(params.redirect_uri),
                    "code_challenge": params.code_challenge,
                    "state": params.state,
                    "scopes": params.scopes or [],
                    "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
                    "resource": params.resource,
                }
            ),
        )
        return f"{self.server_url}/login?session={session_id}"

    async def complete_authorization(self, session_id: str, email: str, password: str) -> str:
        session_data = await db.get_setting(await self._get_conn(), f"auth_session:{session_id}")
        if not session_data:
            raise AuthorizeError(
                error="invalid_request",
                error_description="Invalid or expired session",
            )

        session = json.loads(session_data)

        owner = await db.get_setting(await self._get_conn(), "owner_email")
        if email.lower() != owner.lower():
            raise AuthorizeError(
                error="access_denied",
                error_description="Sign-in is restricted to the owner",
            )

        user = await db.get_user_by_email(await self._get_conn(), email)
        if not user:
            raise AuthorizeError(
                error="access_denied",
                error_description="Account not found",
            )

        if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            raise AuthorizeError(error="access_denied", error_description="Invalid password")

        code = secrets.token_hex(20)
        await db.save_authorization_code(
            await self._get_conn(),
            code=code,
            client_id=session["client_id"],
            redirect_uri=session["redirect_uri"],
            code_challenge=session["code_challenge"],
            scopes=session["scopes"],
            expires_at=time.time() + 600,
            redirect_uri_provided_explicitly=session["redirect_uri_provided_explicitly"],
            resource=session.get("resource"),
        )

        await db.set_setting(await self._get_conn(), f"auth_session:{session_id}", "")

        return construct_redirect_uri(
            session["redirect_uri"], code=code, state=session.get("state")
        )

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        row = await db.get_authorization_code(await self._get_conn(), authorization_code)
        if not row:
            return None
        if row["client_id"] != client.client_id:
            return None
        if row["expires_at"] < time.time():
            await db.delete_authorization_code(await self._get_conn(), authorization_code)
            return None
        return AuthorizationCode(
            code=row["code"],
            client_id=row["client_id"],
            redirect_uri=AnyUrl(row["redirect_uri"]),
            code_challenge=row["code_challenge"],
            scopes=row["scopes"],
            expires_at=row["expires_at"],
            redirect_uri_provided_explicitly=row["redirect_uri_provided_explicitly"],
            resource=row.get("resource"),
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        await db.delete_authorization_code(await self._get_conn(), authorization_code.code)

        access_token = secrets.token_hex(32)
        refresh_token = secrets.token_hex(32)
        expires_in = 3600

        await db.save_oauth_token(
            await self._get_conn(),
            access_token,
            "access",
            client.client_id,
            authorization_code.scopes,
            int(time.time()) + expires_in,
            resource=authorization_code.resource,
        )
        await db.save_oauth_token(
            await self._get_conn(),
            refresh_token,
            "refresh",
            client.client_id,
            authorization_code.scopes,
            resource=authorization_code.resource,
        )

        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=expires_in,
            refresh_token=refresh_token,
            scope=" ".join(authorization_code.scopes) if authorization_code.scopes else None,
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        row = await db.get_oauth_token(await self._get_conn(), refresh_token)
        if not row or row["token_type"] != "refresh":
            return None
        if row["client_id"] != client.client_id:
            return None
        return RefreshToken(
            token=row["token"],
            client_id=row["client_id"],
            scopes=row["scopes"],
            expires_at=row["expires_at"],
        )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        await db.delete_oauth_tokens_for_client(await self._get_conn(), client.client_id)

        access_token = secrets.token_hex(32)
        new_refresh_token = secrets.token_hex(32)
        expires_in = 3600
        use_scopes = scopes or refresh_token.scopes

        await db.save_oauth_token(
            await self._get_conn(),
            access_token,
            "access",
            client.client_id,
            use_scopes,
            int(time.time()) + expires_in,
        )
        await db.save_oauth_token(
            await self._get_conn(),
            new_refresh_token,
            "refresh",
            client.client_id,
            use_scopes,
        )

        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=expires_in,
            refresh_token=new_refresh_token,
            scope=" ".join(use_scopes) if use_scopes else None,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        row = await db.get_oauth_token(await self._get_conn(), token)
        if not row or row["token_type"] != "access":
            return None
        if row["expires_at"] and row["expires_at"] < time.time():
            return None
        return AccessToken(
            token=row["token"],
            client_id=row["client_id"],
            scopes=row["scopes"],
            expires_at=row["expires_at"],
            resource=row.get("resource"),
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        await db.delete_oauth_tokens_for_client(await self._get_conn(), token.client_id)
