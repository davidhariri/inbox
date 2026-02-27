# Inbox — Spec

> A dead-simple, MCP-native todo manager. SQLite backend, deploy anywhere, interact through any MCP client.

## Overview

Inbox is an MCP server that manages todos. There is no web UI, no REST API, no CLI — the MCP protocol is the only interface. This means it works natively with Claude, ChatGPT, and any other MCP-compatible client.

Todos land in the Inbox by default and can be triaged into projects. Tags provide a second dimension of organization. That's it.

## License

[O'Saasy License](https://osaasy.dev) — MIT-like, but the right to run the software as a competing hosted service is reserved for the copyright holder. Self-hosting, modification, and all other uses are permitted.

## Stack

| Concern         | Choice              |
|-----------------|---------------------|
| Language        | Python 3.12+        |
| Dep management  | uv                  |
| Linting         | ruff                |
| Testing         | pytest              |
| Database        | SQLite (FTS5)       |
| MCP SDK         | `mcp` (official)    |
| Transport       | Streamable HTTP     |
| Auth            | OAuth 2.1           |
| Hosting         | Railway (1-click)   |

## Data Model

### Todos

| Column       | Type    | Notes                                                        |
|--------------|---------|--------------------------------------------------------------|
| `id`         | INTEGER | Primary key, autoincrement                                   |
| `name`       | TEXT    | Required. The todo itself.                                   |
| `link`       | TEXT    | Optional URL                                                 |
| `due_date`   | TEXT    | Optional, `YYYY-MM-DD` format. Date only, no timezone.       |
| `priority`   | TEXT    | Optional. One of: `high`, `medium`, `low`                    |
| `project_id` | INTEGER | FK to `projects.id`. `NULL` = Inbox.                         |
| `tags`       | TEXT    | JSON array of strings, e.g. `["urgent", "bug"]`. Default `[]`. Max 50 chars per tag. |
| `created_at` | TEXT    | ISO 8601 datetime, set on insert                             |
| `updated_at` | TEXT    | ISO 8601 datetime, updated on every write                    |
| `completed_at` | TEXT  | `NULL` = open. Set to datetime when completed.               |
| `deleted_at` | TEXT    | `NULL` = active. Soft delete timestamp.                      |

**Indexes:**
- FTS5 virtual table on `name` (and `tags` content for text search)
- Index on `project_id`
- Index on `due_date`
- Index on `completed_at` (for filtering open vs done)
- Index on `deleted_at` (for excluding soft-deleted)

### Projects

| Column       | Type    | Notes                                    |
|--------------|---------|------------------------------------------|
| `id`         | INTEGER | Primary key, autoincrement               |
| `name`       | TEXT    | Required. Unique.                        |
| `created_at` | TEXT    | ISO 8601 datetime                        |
| `updated_at` | TEXT    | ISO 8601 datetime                        |
| `deleted_at` | TEXT    | Soft delete timestamp.                   |

Flat — no nesting. Projects are an optional organizing bucket.

### Inbox

The Inbox is virtual, not a row in the projects table. A todo with `project_id = NULL` is in the Inbox. This means:
- No seed data required
- Inbox can't be renamed, deleted, or confused with user-created projects
- Querying the inbox = `WHERE project_id IS NULL AND deleted_at IS NULL`

## MCP Tools

All tools exclude soft-deleted records by default.

### Todos

#### `create_todo`
Create a new todo. Lands in Inbox unless `project_id` is provided.

| Param        | Type           | Required | Default |
|--------------|----------------|----------|---------|
| `name`       | `str`          | Yes      |         |
| `link`       | `str`          | No       | `None`  |
| `due_date`   | `str`          | No       | `None`  |
| `priority`   | `str`          | No       | `None`  |
| `project_id` | `int`          | No       | `None`  |
| `tags`       | `list[str]`    | No       | `[]`    |

Returns: the created todo.

#### `get_todo`
Fetch a single todo by ID.

| Param | Type  | Required |
|-------|-------|----------|
| `id`  | `int` | Yes      |

Returns: the todo, or error if not found / deleted.

#### `update_todo`
Update one or more fields on a todo. Only provided fields are changed.

| Param        | Type           | Required |
|--------------|----------------|----------|
| `id`         | `int`          | Yes      |
| `name`       | `str`          | No       |
| `link`       | `str`          | No       |
| `due_date`   | `str`          | No       |
| `priority`   | `str`          | No       |
| `project_id` | `int`          | No       |
| `tags`       | `list[str]`    | No       |

Returns: the updated todo.

#### `complete_todo`
Mark a todo as done. Sets `completed_at` to now.

| Param | Type  | Required |
|-------|-------|----------|
| `id`  | `int` | Yes      |

Returns: the updated todo.

#### `reopen_todo`
Reopen a completed todo. Clears `completed_at`.

| Param | Type  | Required |
|-------|-------|----------|
| `id`  | `int` | Yes      |

Returns: the updated todo.

#### `delete_todo`
Soft-delete a todo. Sets `deleted_at` to now.

| Param | Type  | Required |
|-------|-------|----------|
| `id`  | `int` | Yes      |

Returns: confirmation.

#### `search_todos`
Full-text search + filtering. All params optional — calling with no args returns all open Inbox todos.

| Param        | Type           | Required | Notes                                      |
|--------------|----------------|----------|--------------------------------------------|
| `query`      | `str`          | No       | FTS5 full-text search on name and tags      |
| `tags`       | `list[str]`    | No       | Filter: todo must have ALL of these tags    |
| `project_id` | `int`          | No       | Filter by project. Use `0` for Inbox only.  |
| `due_before` | `str`          | No       | Filter: due_date <= this date (YYYY-MM-DD)  |
| `priority`   | `str`          | No       | Filter by priority level                    |
| `status`     | `str`          | No       | `open` (default), `done`, or `all`          |

Returns: list of matching todos, ordered by due_date (nulls last), then created_at desc.

### Projects

#### `create_project`

| Param  | Type  | Required |
|--------|-------|----------|
| `name` | `str` | Yes      |

Returns: the created project.

#### `list_projects`
No params. Returns all active projects with todo counts (open / done).

#### `update_project`

| Param  | Type  | Required |
|--------|-------|----------|
| `id`   | `int` | Yes      |
| `name` | `str` | Yes      |

Returns: the updated project.

#### `delete_project`
Soft-deletes the project. Todos in the project are moved to the Inbox (`project_id` set to `NULL`).

| Param | Type  | Required |
|-------|-------|----------|
| `id`  | `int` | Yes      |

Returns: confirmation with count of todos moved to Inbox.

### Tags

#### `list_tags`
Returns all unique tags currently in use across active (non-deleted) todos, with counts.

No params. Returns: `[{"tag": "bug", "count": 3}, ...]`

## Auth & Transport

### Transport
Streamable HTTP using the MCP Python SDK's built-in Starlette server. Single endpoint at `/mcp`.

### OAuth 2.1 (Self-Contained)

Inbox is its own OAuth Authorization Server + Resource Server using the MCP SDK's combined AS+RS mode. No external auth provider needed.

**Flow:**
1. MCP client (Claude, ChatGPT) redirects user to Inbox's `/authorize` endpoint
2. Inbox serves a simple HTML login form (email + password)
3. User authenticates → Inbox issues an authorization code
4. Client exchanges the code for an access token at `/token`
5. Client uses the bearer token for all subsequent MCP requests

**Endpoints (auto-registered by SDK):**
- `/.well-known/oauth-authorization-server` — RFC 8414 metadata discovery
- `/authorize` — login form + authorization code grant
- `/token` — token exchange
- `/register` — dynamic client registration (required by MCP spec)
- `/revoke` — token revocation

**Custom routes:**
- `/setup` — first-time onboarding (protected by one-time code)
- `/login` — HTML email + password form (GET: render, POST: validate)

### First-Time Onboarding

There are no required environment variables. Inbox boots, detects it has no owner, and enters **setup mode**.

**What happens on first boot:**

1. Server starts and creates the database if it doesn't exist
2. Detects no owner account exists → enters setup mode
3. Generates a one-time setup code (8-character alphanumeric)
4. Logs clearly to stdout:
   ```
   ┌─────────────────────────────────────────────┐
   │  Inbox is ready for setup.                   │
   │                                              │
   │  Visit: http://localhost:8000/setup           │
   │  Setup code: A7kX9mQ2                        │
   │                                              │
   │  This code expires when setup is complete.    │
   └─────────────────────────────────────────────┘
   ```
5. MCP endpoint returns `503 Service Unavailable` with message: "Inbox is not set up yet. Visit {url}/setup to complete setup."
6. Only `/setup` and static assets are accessible

**The setup page (`/setup`):**

1. Enter the one-time setup code (prevents someone else from claiming a public deployment)
2. Create owner account: email + password
3. Configure sign-in policy:
   - **Only me** — no other emails can register (default)
   - **Specific emails** — comma-separated allowlist
   - **Open** — anyone can create an account
4. Submit → owner account created, setup code invalidated, server switches to normal mode
5. Redirects to a "You're all set" page with the Claude Desktop JSON config snippet

**After setup:**
- `/setup` returns 404 (no longer exists)
- MCP endpoint is live, OAuth flow works
- Owner can sign in and authorize MCP clients

### User Management

- Passwords hashed with bcrypt, stored in SQLite
- Sign-in policy is stored in the `settings` table and can be changed by the owner later (via a future MCP admin tool or by re-running setup)
- The owner is the first user and has no special privileges beyond being the one who ran setup — all authenticated users have equal access to all todos

### Secret Key

- `SECRET_KEY` env var is used for signing tokens if provided
- **Railway:** auto-generated via `${{secret(64, true)}}` in the deploy template — user never sees it
- **Self-hosted:** if not set, generated on first boot and stored in the `settings` table
- Either way, the user never has to think about it

**Storage:**
All auth data lives in SQLite alongside app data:
- `settings` table: key/value pairs (secret_key, allowed_emails, sign_in_policy, setup_complete)
- `users` table: id, email, password_hash, created_at
- `oauth_clients` table: client_id, client_secret, redirect_uris, etc.
- `oauth_tokens` table: access_token, refresh_token, user_id, client_id, expires_at, scopes
- `authorization_codes` table: code, user_id, client_id, redirect_uri, expires_at, code_challenge

**Environment variables (all optional):**
- `SECRET_KEY` — overrides the auto-generated token signing key
- `DATABASE_PATH` — path to SQLite file (default: `./inbox.db`, Railway: `/data/inbox.db`)
- `PORT` — server port (default: `8000`)

## Project Structure

```
inbox/
  __init__.py
  __main__.py         # Entry point: python -m inbox
  server.py           # MCP server setup, tool registration, custom routes
  db.py               # SQLite connection, migrations, queries
  tools/
    __init__.py
    todos.py           # Todo tool handlers
    projects.py        # Project tool handlers
    tags.py            # Tag tool handlers
  auth.py              # OAuthAuthorizationServerProvider implementation
  models.py            # Pydantic models for todos, projects, users
  templates/
    setup.html         # First-time onboarding page
    login.html         # Login form served at /authorize
    done.html          # "You're all set" page with config snippets
tests/
  conftest.py          # Fixtures: in-memory DB, MCP test client
  test_todos.py        # Todo CRUD + search integration tests
  test_projects.py     # Project CRUD integration tests
  test_tags.py         # Tag listing tests
  test_auth.py         # Auth flow tests
  test_setup.py        # Onboarding flow tests
pyproject.toml
Dockerfile
railway.toml
LICENSE
README.md
SPEC.md
```

## Testing Strategy

Integration tests that exercise the full stack: MCP tool call → handler → DB → response → assertion. Using an in-memory SQLite database for speed and isolation.

Each test:
1. Calls the MCP tool handler directly (or via test client)
2. Verifies the DB state changed correctly
3. Verifies the returned response matches expectations

Key test scenarios:
- CRUD for todos and projects
- Inbox behavior (create without project, delete project moves todos)
- FTS5 search accuracy and ranking
- Tag filtering (AND semantics)
- Soft delete (deleted records excluded from queries)
- Complete / reopen state transitions
- Validation (bad dates, invalid priority, tag length limits, missing required fields)
- Edge cases (empty search, no results, duplicate project names)
- Setup flow (setup mode blocks MCP, setup code validates, setup completes, /setup disappears)
- Sign-in policy enforcement (only-me, allowlist, open)

Framework: **pytest** with async support via `pytest-asyncio` (MCP SDK is async).

## Deployment

### Railway (1-click)

`railway.toml` config:
- Build: `uv sync` + Dockerfile
- Start: `python -m inbox`
- Volume mount for SQLite persistence at `/data/inbox.db`
- `SECRET_KEY` auto-generated by Railway template
- `DATABASE_PATH` set to `/data/inbox.db`

**User experience:**
1. Click "Deploy on Railway" in README
2. Railway builds and deploys (no env vars to fill in)
3. Check deploy logs → see the setup URL and one-time code
4. Visit the URL, enter the code, create your account
5. Copy the Claude Desktop config from the "You're all set" page
6. Done

### Self-hosted

```bash
uv sync
python -m inbox
```

That's it. No env vars required. Check the logs for the setup URL on first run.

## README Scope

The README is the documentation. It covers:
1. What Inbox is (one paragraph)
2. Deploy on Railway button
3. Self-hosted setup instructions
4. Claude Desktop configuration (JSON snippet)
5. ChatGPT configuration instructions
6. Tool reference (auto-generated or manually maintained)
7. License
