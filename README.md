# Inbox

A dead-simple, MCP-native todo manager. SQLite backend, deploy anywhere, interact through any MCP client.

There's no web UI, no REST API, no CLI. The MCP protocol is the only interface — connect Claude, ChatGPT, or any MCP-compatible client and start managing todos.

## Deploy on Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/inbox?referralCode=2bD5N8&utm_medium=integration&utm_source=template&utm_campaign=generic)

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

## Environment variables

All optional:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Auto-generated | Token signing key |
| `DATABASE_PATH` | `./inbox.db` | Path to SQLite file |
| `PORT` | `8000` | Server port |

## License

[O'Saasy License](https://osaasy.dev) — MIT-like, but the right to run the software as a competing hosted service is reserved for the copyright holder. Self-hosting, modification, and all other uses are permitted.
