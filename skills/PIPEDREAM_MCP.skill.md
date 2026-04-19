# Pipedream MCP — Composio fallback transport

Pipedream Connect exposes 3,000+ apps via one MCP endpoint. Use it as a
fallback when Composio returns 403 / 426 / 5xx / scope errors, or for apps
Composio doesn't support.

## Endpoint
- URL: `https://remote.mcp.pipedream.net/v3`
- Transport: streamable HTTP (langchain-mcp-adapters)
- Auth: `Authorization: Bearer <access_token>` from
  `POST https://api.pipedream.com/v1/oauth/token`
  (grant_type=client_credentials, client_id, client_secret).

## Required headers per request
- `x-pd-project-id` — `proj_xxxx`
- `x-pd-environment` — `development` | `production`
- `x-pd-external-user-id` — your user's id (FDWA uses `fdwa-owner`)
- `x-pd-app-slug` — which app to expose (`linkedin`, `notion`, `gmail`, ...)

Tools loaded are scoped to that one app_slug; swap the header to switch apps.

## Account connection model
No frontend. First tool call for an unlinked app returns a Connect Link URL:

```
https://pipedream.com/_static/connect.html?token=ctok_xxx&connectLink=true&app=<slug>
```

Open in browser → authorize → retry the tool call. Our wrapper detects this
pattern and surfaces the URL via `{"connect_url": "..."}` in the response so
the agent can post it to Notion/Telegram for you.

## Python wrapper

`src/agent/tools/pipedream_mcp.py` exposes:
- `is_configured() -> bool` — true when all env vars are set
- `list_tools(app_slug)` — tool names for an app
- `call_tool(app_slug, tool_name, args)` → `{success, data|error, connect_url?}`
- `post_linkedin_text(text, visibility="PUBLIC", article_url=None)` — convenience

Tools are cached per app_slug. Access token is cached ~55 min.

## Known LinkedIn tool names (post-related)
- `linkedin-create-text-post-user` — args: `visibility` (PUBLIC|CONNECTIONS|LOGGED_IN), `text`, optional `article`
- `linkedin-create-image-post-user` — image posts
- `linkedin-create-text-post-organization` / `linkedin-create-image-post-organization`
- `linkedin-delete-post`, `linkedin-create-comment`, `linkedin-create-like-on-share`

Run `pipedream_mcp.list_tools("linkedin")` to discover all 20 LinkedIn tools
under the current account; use `retrieve_options` for enum/property values.

## Fallback chain (LinkedIn example in agent)
1. Composio `post_linkedin` / `post_linkedin_with_image`
2. On fail → `pipedream_mcp.post_linkedin_text(...)`
3. On Connect Link → log URL in `linkedin_status`, skip for this run
4. On fail → `upload_post_agent.upload(platforms=["linkedin"], ...)` (image only)

## Gotchas
- `visibility` is REQUIRED on linkedin-create-text-post-user (not default PUBLIC).
- External user id MUST be stable across runs or each run looks like a new user
  and forces re-auth. FDWA pins it to `fdwa-owner`.
- `development` environment has separate connected accounts from `production` —
  you authorize once per environment.
- `appDiscovery=true` header lets one MCP session see all apps, but explicit
  `x-pd-app-slug` is faster and keeps tool count low.
