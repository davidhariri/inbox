from fastapi import APIRouter, Depends, HTTPException, Request

from inbox.models import CreateTodoInput, IdsRequest, UpdateTodoRequest
from inbox.oauth_dep import require_oauth_token
from inbox.tools import todos as todo_tools

router = APIRouter(prefix="/api/todos", dependencies=[Depends(require_oauth_token)])


def _get_conn(request: Request):
    return request.app.state.conn


@router.post("")
async def create_todos(request: Request, body: list[CreateTodoInput]):
    conn = _get_conn(request)
    todos = [item.model_dump() for item in body]
    try:
        result = await todo_tools.bulk_create_todos(conn, todos=todos)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("")
async def search_todos(
    request: Request,
    query: str | None = None,
    tags: str | None = None,
    project_id: int | None = None,
    due_before: str | None = None,
    priority: str | None = None,
    status: str = "open",
):
    conn = _get_conn(request)
    tag_list = tags.split(",") if tags else None
    try:
        return await todo_tools.search_todos(
            conn,
            query=query,
            tags=tag_list,
            project_id=project_id,
            due_before=due_before,
            priority=priority,
            status=status,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{todo_id}")
async def get_todo(request: Request, todo_id: int):
    conn = _get_conn(request)
    try:
        return await todo_tools.get_todo(conn, todo_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"todo {todo_id} not found")


@router.patch("/{todo_id}")
async def update_todo(request: Request, todo_id: int, body: UpdateTodoRequest):
    conn = _get_conn(request)
    fields = body.model_dump(exclude_none=True)
    try:
        return await todo_tools.update_todo(conn, todo_id, **fields)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=422, detail=msg)


@router.delete("/{todo_id}")
async def delete_todo(request: Request, todo_id: int):
    conn = _get_conn(request)
    try:
        return await todo_tools.delete_todo(conn, todo_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"todo {todo_id} not found")


@router.post("/complete")
async def complete_todos(request: Request, body: IdsRequest):
    conn = _get_conn(request)
    try:
        return await todo_tools.bulk_complete_todos(conn, ids=body.ids)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=422, detail=msg)


@router.post("/reopen")
async def reopen_todos(request: Request, body: IdsRequest):
    conn = _get_conn(request)
    results = []
    try:
        for id in body.ids:
            result = await todo_tools.reopen_todo(conn, id)
            results.append(result)
        return {"reopened": results, "count": len(results)}
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=422, detail=msg)


@router.post("/delete")
async def delete_todos(request: Request, body: IdsRequest):
    conn = _get_conn(request)
    try:
        return await todo_tools.bulk_delete_todos(conn, ids=body.ids)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=422, detail=msg)
