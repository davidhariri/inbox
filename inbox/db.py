import json
import os
import secrets
from datetime import UTC, datetime

import aiosqlite

DATABASE_PATH = os.environ.get("DATABASE_PATH", "./inbox.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    link TEXT,
    due_date TEXT,
    priority TEXT CHECK(priority IN ('high', 'medium', 'low')),
    project_id INTEGER REFERENCES projects(id),
    tags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    completed_at TEXT,
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_todos_project_id ON todos(project_id);
CREATE INDEX IF NOT EXISTS idx_todos_due_date ON todos(due_date);
CREATE INDEX IF NOT EXISTS idx_todos_completed_at ON todos(completed_at);
CREATE INDEX IF NOT EXISTS idx_todos_deleted_at ON todos(deleted_at);

CREATE VIRTUAL TABLE IF NOT EXISTS todos_fts USING fts5(
    name,
    tags,
    content='todos',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS todos_ai AFTER INSERT ON todos BEGIN
    INSERT INTO todos_fts(rowid, name, tags) VALUES (new.id, new.name, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS todos_ad AFTER DELETE ON todos BEGIN
    INSERT INTO todos_fts(todos_fts, rowid, name, tags)
    VALUES ('delete', old.id, old.name, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS todos_au AFTER UPDATE ON todos BEGIN
    INSERT INTO todos_fts(todos_fts, rowid, name, tags)
    VALUES ('delete', old.id, old.name, old.tags);
    INSERT INTO todos_fts(rowid, name, tags)
    VALUES (new.id, new.name, new.tags);
END;

CREATE TABLE IF NOT EXISTS oauth_clients (
    client_id TEXT PRIMARY KEY,
    client_secret TEXT,
    client_info TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS authorization_codes (
    code TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    code_challenge TEXT NOT NULL,
    scopes TEXT NOT NULL DEFAULT '[]',
    expires_at REAL NOT NULL,
    redirect_uri_provided_explicitly INTEGER NOT NULL DEFAULT 1,
    resource TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    token TEXT PRIMARY KEY,
    token_type TEXT NOT NULL CHECK(token_type IN ('access', 'refresh')),
    client_id TEXT NOT NULL,
    user_id INTEGER,
    scopes TEXT NOT NULL DEFAULT '[]',
    expires_at INTEGER,
    resource TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
"""


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def get_db(path: str | None = None) -> aiosqlite.Connection:
    db = await aiosqlite.connect(path or DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.executescript(SCHEMA)
    return db


async def get_setting(db: aiosqlite.Connection, key: str) -> str | None:
    row = await db.execute_fetchall("SELECT value FROM settings WHERE key = ?", (key,))
    return row[0]["value"] if row else None


async def set_setting(db: aiosqlite.Connection, key: str, value: str) -> None:
    await db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
        (key, value, value),
    )
    await db.commit()


async def get_secret_key(db: aiosqlite.Connection) -> str:
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    stored = await get_setting(db, "secret_key")
    if stored:
        return stored
    generated = secrets.token_hex(32)
    await set_setting(db, "secret_key", generated)
    return generated


async def is_setup_complete(db: aiosqlite.Connection) -> bool:
    val = await get_setting(db, "setup_complete")
    return val == "true"


# --- Users ---


async def create_user(db: aiosqlite.Connection, email: str, password_hash: str) -> dict:
    now = _now()
    cursor = await db.execute(
        "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
        (email, password_hash, now),
    )
    await db.commit()
    return {"id": cursor.lastrowid, "email": email, "created_at": now}


async def get_user_by_email(db: aiosqlite.Connection, email: str) -> dict | None:
    rows = await db.execute_fetchall(
        "SELECT id, email, password_hash, created_at FROM users WHERE email = ?", (email,)
    )
    return dict(rows[0]) if rows else None


# --- Todos ---


async def create_todo(
    db: aiosqlite.Connection,
    name: str,
    link: str | None = None,
    due_date: str | None = None,
    priority: str | None = None,
    project_id: int | None = None,
    tags: list[str] | None = None,
) -> dict:
    now = _now()
    tags_json = json.dumps(tags or [])
    cursor = await db.execute(
        """INSERT INTO todos
           (name, link, due_date, priority, project_id, tags, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, link, due_date, priority, project_id, tags_json, now, now),
    )
    await db.commit()
    return await get_todo(db, cursor.lastrowid)


async def get_todo(db: aiosqlite.Connection, todo_id: int) -> dict | None:
    rows = await db.execute_fetchall(
        "SELECT * FROM todos WHERE id = ? AND deleted_at IS NULL", (todo_id,)
    )
    if not rows:
        return None
    row = dict(rows[0])
    row["tags"] = json.loads(row["tags"])
    return row


async def update_todo(db: aiosqlite.Connection, todo_id: int, **fields) -> dict | None:
    todo = await get_todo(db, todo_id)
    if not todo:
        return None

    updates = []
    values = []
    for key, val in fields.items():
        if key == "tags":
            updates.append("tags = ?")
            values.append(json.dumps(val))
        else:
            updates.append(f"{key} = ?")
            values.append(val)

    updates.append("updated_at = ?")
    values.append(_now())
    values.append(todo_id)

    await db.execute(
        f"UPDATE todos SET {', '.join(updates)} WHERE id = ? AND deleted_at IS NULL",
        values,
    )
    await db.commit()
    return await get_todo(db, todo_id)


async def complete_todo(db: aiosqlite.Connection, todo_id: int) -> dict | None:
    now = _now()
    await db.execute(
        "UPDATE todos SET completed_at = ?, updated_at = ? WHERE id = ? AND deleted_at IS NULL",
        (now, now, todo_id),
    )
    await db.commit()
    return await get_todo(db, todo_id)


async def reopen_todo(db: aiosqlite.Connection, todo_id: int) -> dict | None:
    now = _now()
    await db.execute(
        "UPDATE todos SET completed_at = NULL, updated_at = ? WHERE id = ? AND deleted_at IS NULL",
        (now, todo_id),
    )
    await db.commit()
    return await get_todo(db, todo_id)


async def delete_todo(db: aiosqlite.Connection, todo_id: int) -> bool:
    now = _now()
    cursor = await db.execute(
        "UPDATE todos SET deleted_at = ?, updated_at = ? WHERE id = ? AND deleted_at IS NULL",
        (now, now, todo_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def search_todos(
    db: aiosqlite.Connection,
    query: str | None = None,
    tags: list[str] | None = None,
    project_id: int | None = None,
    due_before: str | None = None,
    priority: str | None = None,
    status: str = "open",
) -> list[dict]:
    conditions = ["t.deleted_at IS NULL"]
    params: list = []

    if status == "open":
        conditions.append("t.completed_at IS NULL")
    elif status == "done":
        conditions.append("t.completed_at IS NOT NULL")

    if project_id is not None:
        if project_id == 0:
            conditions.append("t.project_id IS NULL")
        else:
            conditions.append("t.project_id = ?")
            params.append(project_id)

    if due_before:
        conditions.append("t.due_date IS NOT NULL AND t.due_date <= ?")
        params.append(due_before)

    if priority:
        conditions.append("t.priority = ?")
        params.append(priority)

    if tags:
        for tag in tags:
            conditions.append("EXISTS (SELECT 1 FROM json_each(t.tags) WHERE json_each.value = ?)")
            params.append(tag)

    if query:
        conditions.append("t.id IN (SELECT rowid FROM todos_fts WHERE todos_fts MATCH ?)")
        params.append(query)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT t.* FROM todos t
        WHERE {where}
        ORDER BY
            CASE WHEN t.due_date IS NULL THEN 1 ELSE 0 END,
            t.due_date ASC,
            t.created_at DESC
    """
    rows = await db.execute_fetchall(sql, params)
    results = []
    for row in rows:
        d = dict(row)
        d["tags"] = json.loads(d["tags"])
        results.append(d)
    return results


async def count_open_todos(db: aiosqlite.Connection, project_id: int | None = None) -> int:
    base = "SELECT COUNT(*) as cnt FROM todos WHERE deleted_at IS NULL AND completed_at IS NULL"
    if project_id is None:
        rows = await db.execute_fetchall(base)
    elif project_id == 0:
        rows = await db.execute_fetchall(f"{base} AND project_id IS NULL")
    else:
        rows = await db.execute_fetchall(f"{base} AND project_id = ?", (project_id,))
    return rows[0]["cnt"]


async def count_overdue_todos(db: aiosqlite.Connection) -> int:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    rows = await db.execute_fetchall(
        """SELECT COUNT(*) as cnt FROM todos
           WHERE deleted_at IS NULL AND completed_at IS NULL AND due_date < ?""",
        (today,),
    )
    return rows[0]["cnt"]


# --- Projects ---


async def create_project(db: aiosqlite.Connection, name: str) -> dict:
    now = _now()
    cursor = await db.execute(
        "INSERT INTO projects (name, created_at, updated_at) VALUES (?, ?, ?)",
        (name, now, now),
    )
    await db.commit()
    return await get_project(db, cursor.lastrowid)


async def get_project(db: aiosqlite.Connection, project_id: int) -> dict | None:
    rows = await db.execute_fetchall(
        "SELECT * FROM projects WHERE id = ? AND deleted_at IS NULL", (project_id,)
    )
    return dict(rows[0]) if rows else None


async def list_projects(db: aiosqlite.Connection) -> list[dict]:
    rows = await db.execute_fetchall("""
        SELECT p.*,
            (SELECT COUNT(*) FROM todos t
             WHERE t.project_id = p.id AND t.deleted_at IS NULL
             AND t.completed_at IS NULL) as open_count,
            (SELECT COUNT(*) FROM todos t
             WHERE t.project_id = p.id AND t.deleted_at IS NULL
             AND t.completed_at IS NOT NULL) as done_count
        FROM projects p
        WHERE p.deleted_at IS NULL
        ORDER BY p.name
    """)
    return [dict(r) for r in rows]


async def update_project(db: aiosqlite.Connection, project_id: int, name: str) -> dict | None:
    project = await get_project(db, project_id)
    if not project:
        return None
    now = _now()
    await db.execute(
        "UPDATE projects SET name = ?, updated_at = ? WHERE id = ? AND deleted_at IS NULL",
        (name, now, project_id),
    )
    await db.commit()
    return await get_project(db, project_id)


async def delete_project(db: aiosqlite.Connection, project_id: int) -> dict | None:
    project = await get_project(db, project_id)
    if not project:
        return None
    now = _now()
    # Move todos to inbox
    cursor = await db.execute(
        """UPDATE todos SET project_id = NULL, updated_at = ?
           WHERE project_id = ? AND deleted_at IS NULL""",
        (now, project_id),
    )
    moved_count = cursor.rowcount
    # Soft-delete the project
    await db.execute(
        "UPDATE projects SET deleted_at = ?, updated_at = ? WHERE id = ?",
        (now, now, project_id),
    )
    await db.commit()
    return {"project": project["name"], "todos_moved_to_inbox": moved_count}


# --- Tags ---


async def list_tags(db: aiosqlite.Connection) -> list[dict]:
    rows = await db.execute_fetchall("""
        SELECT j.value as tag, COUNT(*) as count
        FROM todos t, json_each(t.tags) j
        WHERE t.deleted_at IS NULL
        GROUP BY j.value
        ORDER BY count DESC, j.value ASC
    """)
    return [dict(r) for r in rows]


# --- OAuth Clients ---


async def save_oauth_client(
    db: aiosqlite.Connection, client_id: str, client_secret: str | None, client_info_json: str
) -> None:
    await db.execute(
        "INSERT INTO oauth_clients (client_id, client_secret, client_info) VALUES (?, ?, ?)",
        (client_id, client_secret, client_info_json),
    )
    await db.commit()


async def get_oauth_client(db: aiosqlite.Connection, client_id: str) -> dict | None:
    rows = await db.execute_fetchall(
        "SELECT * FROM oauth_clients WHERE client_id = ?", (client_id,)
    )
    return dict(rows[0]) if rows else None


# --- Authorization Codes ---


async def save_authorization_code(
    db: aiosqlite.Connection,
    code: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    scopes: list[str],
    expires_at: float,
    redirect_uri_provided_explicitly: bool,
    resource: str | None = None,
) -> None:
    await db.execute(
        """INSERT INTO authorization_codes
           (code, client_id, redirect_uri, code_challenge,
            scopes, expires_at, redirect_uri_provided_explicitly, resource)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            code,
            client_id,
            redirect_uri,
            code_challenge,
            json.dumps(scopes),
            expires_at,
            int(redirect_uri_provided_explicitly),
            resource,
        ),
    )
    await db.commit()


async def get_authorization_code(db: aiosqlite.Connection, code: str) -> dict | None:
    rows = await db.execute_fetchall("SELECT * FROM authorization_codes WHERE code = ?", (code,))
    if not rows:
        return None
    row = dict(rows[0])
    row["scopes"] = json.loads(row["scopes"])
    row["redirect_uri_provided_explicitly"] = bool(row["redirect_uri_provided_explicitly"])
    return row


async def delete_authorization_code(db: aiosqlite.Connection, code: str) -> None:
    await db.execute("DELETE FROM authorization_codes WHERE code = ?", (code,))
    await db.commit()


# --- OAuth Tokens ---


async def save_oauth_token(
    db: aiosqlite.Connection,
    token: str,
    token_type: str,
    client_id: str,
    scopes: list[str],
    expires_at: int | None = None,
    resource: str | None = None,
) -> None:
    await db.execute(
        """INSERT INTO oauth_tokens (token, token_type, client_id, scopes, expires_at, resource)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (token, token_type, client_id, json.dumps(scopes), expires_at, resource),
    )
    await db.commit()


async def get_oauth_token(db: aiosqlite.Connection, token: str) -> dict | None:
    rows = await db.execute_fetchall("SELECT * FROM oauth_tokens WHERE token = ?", (token,))
    if not rows:
        return None
    row = dict(rows[0])
    row["scopes"] = json.loads(row["scopes"])
    return row


async def delete_oauth_tokens_for_client(db: aiosqlite.Connection, client_id: str) -> None:
    await db.execute("DELETE FROM oauth_tokens WHERE client_id = ?", (client_id,))
    await db.commit()
