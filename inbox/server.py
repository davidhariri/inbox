import os
import secrets
import sqlite3
from pathlib import Path

import bcrypt
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from inbox import db
from inbox.auth import InboxAuthProvider
from inbox.tools import projects as project_tools
from inbox.tools import tags as tag_tools
from inbox.tools import todos as todo_tools

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Module-level DB connection, initialized lazily on first async access
_conn = None


def _get_server_url() -> str:
    port = os.environ.get("PORT", "8000")
    host = os.environ.get("HOST", "localhost")
    scheme = "https" if os.environ.get("RAILWAY_ENVIRONMENT") else "http"
    if os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
        return f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}"
    return f"{scheme}://{host}:{port}"


def _print_setup_banner():
    """Check setup state synchronously and print banner if needed."""
    db_path = db.DATABASE_PATH
    sync_conn = sqlite3.connect(db_path)
    try:
        sync_conn.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        row = sync_conn.execute(
            "SELECT value FROM settings WHERE key = 'setup_complete'"
        ).fetchone()
        if row and row[0] == "true":
            return

        setup_code = secrets.token_hex(4).upper()
        sync_conn.execute(
            "INSERT INTO settings (key, value) VALUES ('setup_code', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = ?",
            (setup_code, setup_code),
        )
        sync_conn.commit()

        url = _get_server_url()
        import sys

        print("\n┌─────────────────────────────────────────────┐")
        print("│  Inbox is ready for setup.                  │")
        print("│                                             │")
        print(f"│  Visit: {url}/setup")
        print(f"│  Setup code: {setup_code}")
        print("│                                             │")
        print("│  This code expires when setup is complete.  │")
        print("└─────────────────────────────────────────────┘\n")
        sys.stdout.flush()
    finally:
        sync_conn.close()


async def _get_conn():
    global _conn
    if _conn is None:
        _conn = await db.get_db()
    return _conn


def create_server() -> FastMCP:
    server_url = _get_server_url()
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")

    _print_setup_banner()

    class LazyAuthProvider(InboxAuthProvider):
        def __init__(self, server_url):
            self.server_url = server_url

        async def _get_conn(self):
            return await _get_conn()

    auth_provider = LazyAuthProvider(server_url)

    mcp = FastMCP(
        name="Inbox",
        instructions=(
            "A simple todo manager. Create, search, and organize todos with projects and tags."
        ),
        host=host,
        port=port,
        auth_server_provider=auth_provider,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(server_url),
            resource_server_url=AnyHttpUrl(f"{server_url}/mcp"),
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=["inbox"],
                default_scopes=["inbox"],
            ),
            revocation_options=RevocationOptions(enabled=True),
            required_scopes=[],
        ),
    )

    # --- Todo tools ---

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False))
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

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False))
    async def bulk_create_todos(
        todos: list[dict],
    ) -> dict:
        """Create multiple todos at once. Each item needs a name; link, due_date, priority, project_id, and tags are optional."""
        return await todo_tools.bulk_create_todos(await _get_conn(), todos=todos)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_todo(id: int) -> dict:
        """Fetch a single todo by ID."""
        return await todo_tools.get_todo(await _get_conn(), id)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False, idempotentHint=True))
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

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False, idempotentHint=True))
    async def complete_todo(id: int) -> dict:
        """Mark a todo as done."""
        return await todo_tools.complete_todo(await _get_conn(), id)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False, idempotentHint=True))
    async def reopen_todo(id: int) -> dict:
        """Reopen a completed todo."""
        return await todo_tools.reopen_todo(await _get_conn(), id)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    async def delete_todo(id: int) -> dict:
        """Soft-delete a todo."""
        return await todo_tools.delete_todo(await _get_conn(), id)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False, idempotentHint=True))
    async def bulk_complete_todos(ids: list[int]) -> dict:
        """Mark multiple todos as done at once."""
        return await todo_tools.bulk_complete_todos(await _get_conn(), ids=ids)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    async def bulk_delete_todos(ids: list[int]) -> dict:
        """Soft-delete multiple todos at once."""
        return await todo_tools.bulk_delete_todos(await _get_conn(), ids=ids)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
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
        Use project_id=0 for Inbox only, or a specific project ID. Combine filters to narrow results.
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

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False))
    async def create_project(name: str, description: str | None = None) -> dict:
        """Create a new project."""
        return await project_tools.create_project(await _get_conn(), name, description)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def list_projects() -> dict:
        """List all active projects with todo counts."""
        return await project_tools.list_projects(await _get_conn())

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False, idempotentHint=True))
    async def update_project(
        id: int, name: str | None = None, description: str | None = None
    ) -> dict:
        """Update a project. Only provided fields are changed."""
        return await project_tools.update_project(
            await _get_conn(), id, name=name, description=description
        )

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    async def delete_project(id: int) -> dict:
        """Soft-delete a project. Todos in the project are moved to the Inbox."""
        return await project_tools.delete_project(await _get_conn(), id)

    # --- Tag tools ---

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def list_tags() -> dict:
        """List all unique tags in use across active todos, with counts."""
        return await tag_tools.list_tags(await _get_conn())

    # --- Custom routes ---

    def _render_template(name: str, **kwargs) -> str:
        template_path = TEMPLATES_DIR / name
        html = template_path.read_text()
        for key, value in kwargs.items():
            html = html.replace(f"{{{{{key}}}}}", str(value))
        return html

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    @mcp.custom_route("/setup", methods=["GET"])
    async def setup_page(request: Request) -> Response:
        if await db.is_setup_complete(await _get_conn()):
            return Response(status_code=404)
        html = _render_template("setup.html", server_url=_get_server_url())
        return HTMLResponse(html)

    @mcp.custom_route("/setup", methods=["POST"])
    async def setup_submit(request: Request) -> Response:
        if await db.is_setup_complete(await _get_conn()):
            return Response(status_code=404)

        form = await request.form()
        setup_code = str(form.get("setup_code", "")).strip()
        email = str(form.get("email", "")).strip()
        password = str(form.get("password", ""))

        stored_code = await db.get_setting(await _get_conn(), "setup_code")
        if setup_code != stored_code:
            return HTMLResponse(
                '<p class="error">Invalid setup code. Check your deploy logs.</p>',
            )

        if not email:
            return HTMLResponse('<p class="error">Email is required.</p>')
        if not password or len(password) < 8:
            return HTMLResponse(
                '<p class="error">Password must be at least 8 characters.</p>',
            )

        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        await db.create_user(await _get_conn(), email, hashed)
        await db.set_setting(await _get_conn(), "owner_email", email)
        await db.set_setting(await _get_conn(), "setup_complete", "true")

        # Return redirect via HTMX
        return HTMLResponse(
            headers={"HX-Redirect": "/done"},
            content="",
        )

    @mcp.custom_route("/done", methods=["GET"])
    async def done_page(request: Request) -> Response:
        if not await db.is_setup_complete(await _get_conn()):
            return RedirectResponse("/setup")
        server_url = _get_server_url()
        html = _render_template("done.html", server_url=server_url)
        return HTMLResponse(html)

    @mcp.custom_route("/login", methods=["GET"])
    async def login_page(request: Request) -> Response:
        if not await db.is_setup_complete(await _get_conn()):
            return Response(
                content="Inbox is not set up yet. Visit /setup to complete setup.",
                status_code=503,
            )
        session = request.query_params.get("session", "")
        html = _render_template("login.html", session=session, server_url=_get_server_url())
        return HTMLResponse(html)

    @mcp.custom_route("/login", methods=["POST"])
    async def login_submit(request: Request) -> Response:
        form = await request.form()
        session_id = str(form.get("session", "")).strip()
        email = str(form.get("email", "")).strip()
        password = str(form.get("password", ""))

        if not email or not password:
            return HTMLResponse(
                '<p class="error">Email and password are required.</p>',
            )

        try:
            redirect_url = await auth_provider.complete_authorization(session_id, email, password)
            return HTMLResponse(
                headers={"HX-Redirect": redirect_url},
                content="",
            )
        except Exception as e:
            msg = str(e.error_description) if hasattr(e, "error_description") else str(e)
            return HTMLResponse(f'<p class="error">{msg}</p>')

    return mcp
