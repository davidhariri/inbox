# Inbox — Agent Instructions

## What is this project?

Inbox is an MCP-native todo manager. No UI, no REST API — just an MCP server backed by SQLite. Read `SPEC.md` for the full specification and `TASTE.md` for the quality bar.

## Stack

- **Python 3.12+** — use modern syntax (type unions with `|`, match statements, etc.)
- **uv** — dependency management. Use `uv add` to add deps, `uv sync` to install, `uv run` to execute.
- **ruff** — linting and formatting. Run `ruff check` and `ruff format` before committing.
- **pytest + pytest-asyncio** — testing. The MCP SDK is async, so all tests are async.
- **MCP Python SDK (`mcp`)** — official SDK. Uses Starlette + uvicorn under the hood. No FastAPI.
- **SQLite with FTS5** — single-file database. `aiosqlite` for async access.
- **HTMX** — declarative form interactions. CDN, no build step. Docs: https://htmx.org/docs/

## Project layout

```
inbox/
  __init__.py
  __main__.py         # Entry point: python -m inbox
  server.py           # MCP server, tool registration, custom routes
  db.py               # SQLite connection, migrations, queries
  auth.py             # OAuthAuthorizationServerProvider (combined AS+RS)
  models.py           # Pydantic models
  tools/
    todos.py
    projects.py
    tags.py
  templates/
    setup.html         # First-time onboarding
    login.html         # OAuth login form
    done.html          # Post-setup config page
tests/
  conftest.py          # Fixtures: in-memory DB, MCP test client
  test_todos.py
  test_projects.py
  test_tags.py
  test_auth.py
  test_setup.py
```

## Commands

```bash
uv sync                   # Install deps
uv run python -m inbox    # Run the server
uv run ruff check .       # Lint
uv run ruff format .      # Format
uv run pytest             # Run tests
uv run pytest -x          # Stop on first failure
```

## Architecture decisions

- **Inbox is virtual.** `project_id = NULL` means a todo is in the Inbox. There is no Inbox row in the projects table.
- **Soft deletes everywhere.** Todos and projects use `deleted_at`. All queries must filter `WHERE deleted_at IS NULL` by default.
- **Timestamps are ISO 8601 strings.** SQLite stores them as TEXT. Due dates are `YYYY-MM-DD` only (no time, no timezone).
- **Tags are a JSON array on the todo row.** Not a junction table. Use `json_each()` for tag filtering. Max 50 chars per tag.
- **FTS5 for search.** Virtual table indexes `name` and `tags`. Keep it in sync with triggers on insert/update/delete.
- **OAuth is self-contained.** Inbox implements the full OAuth AS+RS using the MCP SDK's combined mode (`OAuthAuthorizationServerProvider`). No external auth provider.
- **First-time onboarding.** Server boots in setup mode when no owner exists. Prints a one-time code to stdout, serves `/setup`, blocks MCP with 503. After setup, `/setup` disappears.
- **SECRET_KEY auto-generates.** Check env var first, then DB `settings` table, then generate and persist. User never has to set this.

## Code principles

- **KISS.** Simplest solution that works. If there's a choice between clever and obvious, pick obvious.
- **DRY.** Extract when you see actual duplication (3+ occurrences), not potential duplication. Three similar lines are better than a premature abstraction.
- **Single responsibility.** Each module, function, and tool handler does one thing. If a function needs an "and" in its description, split it.
- **Fail fast.** Validate inputs at the boundary and reject early with clear errors. Don't let bad data propagate.

## Code style

- Keep it simple. Don't add abstractions for one-time operations.
- No feature flags, no plugin system, no extension points.
- Validate at boundaries (tool inputs), trust internal code.
- Error messages should be actionable: tell the caller what went wrong and what the valid options are.
- Tool responses should carry context (see TASTE.md "The AI is the user"). Return the created/updated object plus relevant context like open todo count or overdue items.

## Templates

- **HTMX for forms.** All form submissions use HTMX — no raw form POSTs, no custom JS. Docs: https://htmx.org/docs/
- **Shared CSS.** Define base styles once. Use CSS custom properties for colors, spacing, and typography. No duplicated style blocks across templates.
- **Dark mode.** All pages support `prefers-color-scheme: dark` via CSS media query. No toggle, no JS — respect the OS setting.
- **Minimal markup.** Semantic HTML, no CSS frameworks, no bundler. HTMX via CDN `<script>` tag.

## Testing

Tests are integration tests that go through the full stack: MCP tool call → handler → DB → response. Use an in-memory SQLite database (`:memory:`) for speed and isolation.

- Every test gets a fresh database via fixture
- Test both happy paths and validation errors
- Test soft delete filtering (deleted records must not appear)
- Test the setup/onboarding flow separately

## Git

- Never rebase. Always merge.
- `git pull` (not `git pull --rebase`)
- Commit messages: short, imperative, focused on "why"

## Don't

- Don't add docstrings or type annotations to code you didn't change
- Don't add comments unless the logic is non-obvious
- Don't create abstractions for hypothetical future use
- Don't add features beyond what SPEC.md defines
- Don't create documentation files unless explicitly asked
- Don't add enterprise features (roles, permissions, audit logs, webhooks)
