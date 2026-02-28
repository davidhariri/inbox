from fastmcp import FastMCP

from inbox import db
from inbox.tools import projects as project_tools
from inbox.tools import tags as tag_tools
from inbox.tools import todos as todo_tools

# Module-level DB connection, initialized lazily on first async access
_conn = None


async def _get_conn():
    global _conn
    if _conn is None:
        _conn = await db.get_db()
    return _conn


def create_mcp(auth=None) -> FastMCP:
    mcp = FastMCP(
        name="Inbox",
        instructions=(
            "A simple todo manager. Create, search, and organize todos with projects and tags."
        ),
        auth=auth,
    )

    # --- Todo tools ---

    @mcp.tool
    async def create_todo(
        name: str,
        link: str | None = None,
        due_date: str | None = None,
        priority: str | None = None,
        project_id: int | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Create a new todo. Lands in Inbox unless project_id is provided."""
        conn = await _get_conn()
        return await todo_tools.create_todo(
            conn,
            name=name,
            link=link,
            due_date=due_date,
            priority=priority,
            project_id=project_id,
            tags=tags,
        )

    @mcp.tool
    async def bulk_create_todos(
        todos: list[dict],
    ) -> dict:
        """Create multiple todos at once.

        Each item needs a name; link, due_date, priority, project_id, and tags are optional.
        """
        return await todo_tools.bulk_create_todos(await _get_conn(), todos=todos)

    @mcp.tool
    async def get_todo(id: int) -> dict:
        """Fetch a single todo by ID."""
        return await todo_tools.get_todo(await _get_conn(), id)

    @mcp.tool
    async def update_todo(
        id: int,
        name: str | None = None,
        link: str | None = None,
        due_date: str | None = None,
        priority: str | None = None,
        project_id: int | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Update one or more fields on a todo. Only provided fields are changed."""
        conn = await _get_conn()
        return await todo_tools.update_todo(
            conn,
            id,
            name=name,
            link=link,
            due_date=due_date,
            priority=priority,
            project_id=project_id,
            tags=tags,
        )

    @mcp.tool
    async def complete_todo(id: int) -> dict:
        """Mark a todo as done."""
        return await todo_tools.complete_todo(await _get_conn(), id)

    @mcp.tool
    async def reopen_todo(id: int) -> dict:
        """Reopen a completed todo."""
        return await todo_tools.reopen_todo(await _get_conn(), id)

    @mcp.tool
    async def delete_todo(id: int) -> dict:
        """Soft-delete a todo."""
        return await todo_tools.delete_todo(await _get_conn(), id)

    @mcp.tool
    async def bulk_complete_todos(ids: list[int]) -> dict:
        """Mark multiple todos as done at once."""
        return await todo_tools.bulk_complete_todos(await _get_conn(), ids=ids)

    @mcp.tool
    async def bulk_delete_todos(ids: list[int]) -> dict:
        """Soft-delete multiple todos at once."""
        return await todo_tools.bulk_delete_todos(await _get_conn(), ids=ids)

    @mcp.tool
    async def search_todos(
        query: str | None = None,
        tags: list[str] | None = None,
        project_id: int | None = None,
        due_before: str | None = None,
        priority: str | None = None,
        status: str = "open",
    ) -> dict:
        """Search and filter todos. Use filters to avoid fetching everything.

        Tips: use due_before=YYYY-MM-DD for todos due by a date (or today's date for overdue).
        Use project_id=0 for Inbox only, or a specific project ID. Combine filters.
        Calling with no args returns ALL open todos — prefer filtering first.
        """
        conn = await _get_conn()
        return await todo_tools.search_todos(
            conn,
            query=query,
            tags=tags,
            project_id=project_id,
            due_before=due_before,
            priority=priority,
            status=status,
        )

    # --- Project tools ---

    @mcp.tool
    async def create_project(name: str, description: str | None = None) -> dict:
        """Create a new project."""
        return await project_tools.create_project(await _get_conn(), name, description)

    @mcp.tool
    async def list_projects() -> dict:
        """List all active projects with todo counts."""
        return await project_tools.list_projects(await _get_conn())

    @mcp.tool
    async def update_project(
        id: int, name: str | None = None, description: str | None = None
    ) -> dict:
        """Update a project. Only provided fields are changed."""
        return await project_tools.update_project(
            await _get_conn(), id, name=name, description=description
        )

    @mcp.tool
    async def delete_project(id: int) -> dict:
        """Soft-delete a project. Todos in the project are moved to the Inbox."""
        return await project_tools.delete_project(await _get_conn(), id)

    # --- Tag tools ---

    @mcp.tool
    async def list_tags() -> dict:
        """List all unique tags in use across active todos, with counts."""
        return await tag_tools.list_tags(await _get_conn())

    return mcp
