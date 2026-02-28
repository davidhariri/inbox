from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer()


async def require_oauth_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
):
    token = await request.app.state.auth_provider.load_access_token(credentials.credentials)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return token
