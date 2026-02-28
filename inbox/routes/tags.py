from fastapi import APIRouter, Depends, Request

from inbox.oauth_dep import require_oauth_token
from inbox.tools import tags as tag_tools

router = APIRouter(prefix="/api/tags", dependencies=[Depends(require_oauth_token)])


@router.get("")
async def list_tags(request: Request):
    conn = request.app.state.conn
    return await tag_tools.list_tags(conn)
