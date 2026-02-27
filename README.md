# Inbox

A dead-simple, MCP-native todo manager. SQLite backend, deploy anywhere, interact through any MCP client.

There's no web UI, no REST API, no CLI. The MCP protocol is the only interface — connect Claude, ChatGPT, or any MCP-compatible client and start managing todos.

## Deploy on Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/template/inbox)

Check the deploy logs for your setup URL and one-time code, then visit it to create your account.

## Self-hosted

```bash
uv sync
python -m inbox
```

Check the logs for the setup URL on first run.

## Connect your client

### Claude Desktop

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "inbox": {
      "type": "streamable-http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Claude Code

```bash
claude mcp add inbox --transport http http://localhost:8000/mcp
```

### ChatGPT

In ChatGPT settings, add an MCP server with URL: `http://localhost:8000/mcp`

## Tools

### Todos

| Tool | Description |
|------|-------------|
| `create_todo` | Create a todo. Lands in Inbox unless `project_id` is given. |
| `get_todo` | Fetch a single todo by ID. |
| `update_todo` | Update one or more fields. Only provided fields change. |
| `complete_todo` | Mark a todo as done. |
| `reopen_todo` | Reopen a completed todo. |
| `delete_todo` | Soft-delete a todo. |
| `search_todos` | Full-text search + filtering. No args = all open Inbox todos. |

### Projects

| Tool | Description |
|------|-------------|
| `create_project` | Create a new project. |
| `list_projects` | List all projects with open/done counts. |
| `update_project` | Rename a project. |
| `delete_project` | Delete a project. Todos move to Inbox. |

### Tags

| Tool | Description |
|------|-------------|
| `list_tags` | All unique tags in use, with counts. |

## Environment variables

All optional:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Auto-generated | Token signing key |
| `DATABASE_PATH` | `./inbox.db` | Path to SQLite file |
| `PORT` | `8000` | Server port |

## License

[O'Saasy License](https://osaasy.dev) — MIT-like, but the right to run the software as a competing hosted service is reserved for the copyright holder. Self-hosting, modification, and all other uses are permitted.
