# Inbox

A dead-simple, MCP-native todo manager. SQLite backend, deploy anywhere, interact through any MCP client or the REST API.

## Deployment

Deploy Inbox, then check the logs for the setup URL and one-time code:

```
┌─────────────────────────────────────────────┐
│  Inbox is ready for setup.                  │
│                                             │
│  Visit: https://your-server.example/setup   │
│  Setup code: A7B3F1E9                       │
│                                             │
│  This code expires when setup is complete.  │
└─────────────────────────────────────────────┘
```

Visit the URL, enter the code, and create your account.

### Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/inbox?referralCode=2bD5N8&utm_medium=integration&utm_source=template&utm_campaign=generic)

One-click deploy — check the logs for your setup URL.

### Self-hosted

```bash
docker build -t inbox .
docker run -p 8000:8000 -v inbox-data:/data inbox
```

## Connecting your client

After completing setup, the confirmation page at `/done` shows connection instructions with your server URL pre-filled for Claude Desktop, Claude Code, and ChatGPT.

## OAuth for API clients

Inbox uses OAuth 2.1 for all authentication — both MCP and REST API. Any client (web app, CLI tool, mobile app) can obtain tokens through the same flow.

### Flow

1. **Register a client** — `POST /mcp/register` with your `redirect_uris` and metadata. You'll get back a `client_id` and `client_secret`.

2. **Authorize** — Redirect the user to `/mcp/authorize` with standard OAuth params (`client_id`, `redirect_uri`, `code_challenge`, `state`, `response_type=code`). Inbox shows its login page. On success, the user is redirected back with an authorization `code`.

3. **Exchange for tokens** — `POST /mcp/token` with the `code`, `code_verifier`, `client_id`, and `client_secret`. You'll receive an `access_token` and `refresh_token`.

4. **Call the API** — Pass the access token as `Authorization: Bearer <token>` on any `/api/*` endpoint or MCP request to `/mcp/`.

5. **Refresh** — When the access token expires (1 hour), `POST /mcp/token` with `grant_type=refresh_token`.

### Discovery

`GET /mcp/.well-known/oauth-authorization-server` returns the full OAuth metadata (endpoints, supported grants, PKCE methods).

### Example: curl with a token

```bash
# List todos
curl -H "Authorization: Bearer <access_token>" https://your-server.example/api/todos

# Create a todo
curl -X POST -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '[{"name": "Buy milk"}]' \
  https://your-server.example/api/todos
```

## License

[O'Saasy License](https://osaasy.dev) — MIT-like, but the right to run the software as a competing hosted service is reserved for the copyright holder. Self-hosting, modification, and all other uses are permitted.
