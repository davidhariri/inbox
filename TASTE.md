# Inbox — Taste

This document describes how Inbox should *feel*. Not what it does (that's the spec), but the quality bar and sensibility behind every decision. Use this as a gut-check when building.

## The AI is the user

There is no UI. The AI model — Claude, ChatGPT, whatever comes next — is the primary user of this software. Every design decision flows from that.

This means:

- **Tool names are the interface.** A model should be able to guess what `create_todo` does and what params it takes without reading a single line of documentation. If a tool name needs explanation, rename it.
- **Responses carry context, not just data.** When a todo is created, the response should read like a confirmation a human would appreciate: the todo name, which project it landed in, the due date, how many open items are in that project now. Give the model enough to say something useful back to the person.
- **Errors are instructions.** Don't return "invalid input." Return "priority must be one of: high, medium, low — got 'urgent'." The model shouldn't have to guess what went wrong or retry blindly.
- **Be proactive.** If someone creates a todo and they have 6 overdue items, mention it. If they complete the last todo in a project, say so. The server has context the model doesn't — share it. This is what makes the experience feel alive rather than like talking to a database.

## Small, finished, polished

Inbox does very little. That's the point.

- No feature is half-done. Everything that ships works completely, handles edge cases, and fails gracefully.
- No "coming soon." If it's not ready, it doesn't exist in the tool list.
- No feature flags, no plugin architecture, no extension points. The app makes decisions so you don't have to. There is one way to do things and it's the right way.
- If you can delete something and nothing breaks, delete it.

## Speed to value

Someone should go from "I've never heard of this" to "I just created my first todo from Claude" in under 2 minutes. That means:

- The Railway deploy button works on the first click.
- The README shows the Claude Desktop JSON config snippet — copy, paste, done.
- First run creates the database, runs migrations, and is ready to serve. No setup commands, no init step.
- The OAuth flow should be fast and unsurprising. Sign up, authorize, you're in.

## Docs are clear, not clever

The reader is smart but busy. They might be a developer, or they might be someone who just wants a todo list that works with their AI assistant.

- Explain what things are and how to use them. Don't explain what they could be.
- Show, don't tell. A JSON snippet is worth more than a paragraph.
- Say why when the reason isn't obvious. "Todos default to the Inbox because most things don't need a project yet" is more useful than just "Todos default to the Inbox."
- No jargon without context. If you say "Streamable HTTP," link to what that means or say it in plain language first.

## Inspiration: Things by Cultured Code

Things is the spiritual reference for this project. Not because we're building a GUI, but because of what it gets right:

- **Obvious structure.** Inbox, Today, projects, tags — you never wonder where something goes. Our data model should feel the same way through MCP tools. When a model asks "where should I put this?", the answer should be self-evident from the tool params.
- **Nothing is in your way.** Things doesn't ask you to configure views, set up workflows, or decide on a methodology. You open it and start typing. Inbox should feel the same: connect to the MCP server and start creating todos. No onboarding, no decisions to make first.
- **Calm clarity.** Things never feels rushed or cluttered. Every interaction is considered. For us, that means tool responses are clean and well-structured, errors are helpful not noisy, and the server never returns more than you need.
- **Deceptive depth.** Things looks simple but supports real workflows — repeating tasks, areas, deadlines vs. scheduling. We're not copying those features, but we should share the principle: the simple surface (13 tools, 3 tables) should handle real-world usage without feeling like a toy.

## What Inbox is NOT

- **Not enterprise software.** No roles, no permissions beyond "can this email sign in," no audit trails, no compliance features. If you need that, you need a different tool.
- **Not configurable.** There's no settings page, no YAML files, no 15-flag CLI. Env vars for the things that must vary per deployment (database path, allowed emails, secret key). Everything else is a decision the app already made.
- **Not a platform.** No webhooks, no integrations, no API beyond MCP. Inbox doesn't try to be the center of your workflow. It's a tool that does one thing.

## The quality bar

Before shipping anything, ask:

1. Would an AI use this tool correctly on the first try, with no examples?
2. If someone read only the README, could they be running in 2 minutes?
3. Is there anything here that could be removed without making the experience worse?

If the answer to 3 is yes, remove it.
