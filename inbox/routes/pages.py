import os
from pathlib import Path

import bcrypt
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from inbox import db

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

router = APIRouter()


def _get_server_url() -> str:
    port = os.environ.get("PORT", "8000")
    host = os.environ.get("HOST", "localhost")
    scheme = "https" if os.environ.get("RAILWAY_ENVIRONMENT") else "http"
    if os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
        return f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}"
    return f"{scheme}://{host}:{port}"


def _render_template(name: str, **kwargs) -> str:
    template_path = TEMPLATES_DIR / name
    html = template_path.read_text()
    for key, value in kwargs.items():
        html = html.replace(f"{{{{{key}}}}}", str(value))
    return html


@router.get("/setup")
async def setup_page(request: Request):
    conn = request.app.state.conn
    if await db.is_setup_complete(conn):
        return Response(status_code=404)
    html = _render_template("setup.html", server_url=_get_server_url())
    return HTMLResponse(html)


@router.post("/setup")
async def setup_submit(request: Request):
    conn = request.app.state.conn
    if await db.is_setup_complete(conn):
        return Response(status_code=404)

    form = await request.form()
    setup_code = str(form.get("setup_code", "")).strip()
    email = str(form.get("email", "")).strip()
    password = str(form.get("password", ""))

    stored_code = await db.get_setting(conn, "setup_code")
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
    await db.create_user(conn, email, hashed)
    await db.set_setting(conn, "owner_email", email)
    await db.set_setting(conn, "setup_complete", "true")

    return HTMLResponse(
        headers={"HX-Redirect": "/done"},
        content="",
    )


@router.get("/done")
async def done_page(request: Request):
    conn = request.app.state.conn
    if not await db.is_setup_complete(conn):
        return RedirectResponse("/setup")
    server_url = _get_server_url()
    html = _render_template("done.html", server_url=server_url)
    return HTMLResponse(html)


@router.get("/login")
async def login_page(request: Request):
    conn = request.app.state.conn
    if not await db.is_setup_complete(conn):
        return Response(
            content="Inbox is not set up yet. Visit /setup to complete setup.",
            status_code=503,
        )
    session = request.query_params.get("session", "")
    html = _render_template("login.html", session=session, server_url=_get_server_url())
    return HTMLResponse(html)


@router.post("/login")
async def login_submit(request: Request):
    auth_provider = request.app.state.auth_provider

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
