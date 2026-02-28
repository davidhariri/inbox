from fastapi import APIRouter, Depends, HTTPException, Request

from inbox.models import CreateProjectRequest, UpdateProjectRequest
from inbox.oauth_dep import require_oauth_token
from inbox.tools import projects as project_tools

router = APIRouter(prefix="/api/projects", dependencies=[Depends(require_oauth_token)])


def _get_conn(request: Request):
    return request.app.state.conn


@router.post("")
async def create_project(request: Request, body: CreateProjectRequest):
    conn = _get_conn(request)
    try:
        return await project_tools.create_project(conn, body.name, body.description)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("")
async def list_projects(request: Request):
    conn = _get_conn(request)
    return await project_tools.list_projects(conn)


@router.patch("/{project_id}")
async def update_project(request: Request, project_id: int, body: UpdateProjectRequest):
    conn = _get_conn(request)
    fields = body.model_dump(exclude_none=True)
    try:
        return await project_tools.update_project(conn, project_id, **fields)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=422, detail=msg)


@router.delete("/{project_id}")
async def delete_project(request: Request, project_id: int):
    conn = _get_conn(request)
    try:
        return await project_tools.delete_project(conn, project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
