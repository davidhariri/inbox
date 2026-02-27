# Inbox

A dead-simple, MCP-native todo manager. SQLite backend, deploy anywhere, interact through any MCP client.

There's no web UI, no REST API, no CLI. The MCP protocol is the only interface — connect Claude, ChatGPT, or any MCP-compatible client and start managing todos.

## Deployment

Deploy Inbox, then visit the setup URL printed in the logs to create your owner account. You'll enter a one-time code (also in the logs), set your email and password, and choose a sign-in policy.

### Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/inbox?referralCode=2bD5N8&utm_medium=integration&utm_source=template&utm_campaign=generic)

Check the deploy logs for your setup URL and one-time code.

### Self-hosted

```bash
docker build -t inbox .
docker run -p 8000:8000 -v inbox-data:/data inbox
```

## Connecting your client

After completing setup, the confirmation page at `/done` shows connection instructions with your server URL pre-filled for Claude Desktop, Claude Code, and ChatGPT.

## License

[O'Saasy License](https://osaasy.dev) — MIT-like, but the right to run the software as a competing hosted service is reserved for the copyright holder. Self-hosting, modification, and all other uses are permitted.
