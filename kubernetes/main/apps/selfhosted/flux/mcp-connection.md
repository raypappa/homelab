# How to connect an AI agent to the Flux MCP server

This PR deploys Flux (the kanban board) with an **embedded MCP server** so an
AI agent can read and write the board as a first-class actor. The MCP server
shares the same `flux-data` volume (and hence the same `flux.sqlite`) as the
Flux board, so a task an agent creates is immediately visible in the web UI.

## Where it lives

- Board web UI: `https://flux.fieldsofbears.com`
- MCP HTTP endpoint: `https://mcp.fieldsofbears.com`
  - Tunneled through Cloudflare, on port 3001, behind `FLUX_MCP_PASSWORD`.

## Connecting an agent

### Option A — stdio (agent runs on the same machine as the board)

Use Flux's MCP stdio transport. From this repository, the quickstart already
documents this:

```bash
# Flux board server (runs in Kubernetes, port 80)
docker run -d -p 127.0.0.1:80:80 -v flux-data:/app/packages/data \
  -e FLUX_DATA=/app/packages/data/flux.sqlite -e FLUX_ALLOW_ANONYMOUS=1 \
  sirsjg/flux-mcp:sha-4d77f4f bun packages/server/dist/index.js

# Flux MCP server (stdio)
docker run -i --rm -v flux-data:/app/packages/data \
  sirsjg/flux-mcp:sha-4d77f4f bun packages/mcp/dist/index.js
```

Then point your MCP client at the local stdio server.

### Option B — HTTP (agent runs elsewhere, e.g. this platform)

The MCP server above binds HTTP (port 3001) and authenticates over OAuth via
`FLUX_MCP_PASSWORD`. Point your MCP client at:

```
https://mcp.fieldsofbears.com
```

Provide the OAuth client Credentials flow with the `FLUX_MCP_PASSWORD` value,
or a long-lived `FLUX_MCP_TOKEN` for scripts.

### Agent workflow

Use Flux the way a human would:

1. On startup, list projects, then select or create one and confirm its
   `project_id` before doing anything.
2. Pick the next task with `list_ready_tasks` (excludes blocked, sorted by
   priority), set `in_progress` when you start and `done` when you finish.
3. Pass your `agent_name` on status changes so the board shows who is busy.
4. When you discover new work, create a task with acceptance criteria rather
   than expanding the current task.
5. Record decisions, findings and blockers as task comments — they are your
   memory across sessions.

If you are unsure of a project_id or lose context, stop and re-list, then ask
the user rather than guessing.
