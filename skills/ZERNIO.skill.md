# Zernio (MCP) Skill

Purpose: primary transport for Twitter/X (our direct + Composio X paths were removed) and an optional one-token aggregator for 14 platforms (LinkedIn, Instagram, TikTok, Bluesky, Facebook, YouTube, Pinterest, Threads, Telegram, WhatsApp, Google Business, Snapchat).

## Transport

- Endpoint: `https://mcp.zernio.com/mcp`
- Auth: `Authorization: Bearer $ZERNIO_API_KEY`
- Transport: streamable HTTP (`langchain-mcp-adapters`, same pattern as Buffer + Pipedream)
- API base (reference only): `https://zernio.com/api/v1`
- Dashboard / key mgmt: `https://zernio.com/dashboard/api-keys`

## Why Zernio for Twitter

Memory `twitter_via_upload_post.md` notes our X posting is image-only via upload-post aggregator (10/mo cap). Zernio removes both limits: unlimited text tweets AND images through one bearer, no per-platform OAuth. Keep upload-post as a fallback but prefer Zernio.

## Core tools used

- `accounts_list` — sanity check which social accounts the Zernio workspace has connected
- `posts_publish_now(content, platform, media_urls="", title="")` — immediate publish
- `posts_create(content, platform, is_draft|publish_now|schedule_minutes, ...)` — full create with scheduling
- `posts_cross_post(content, platforms, publish_now=true, media_urls="")` — one call, multi-platform
- `posts_list(status, limit)` — verify / recover failed posts
- `posts_retry` / `posts_list_failed` — for error recovery

Tool count: 280+ auto-generated from Zernio's OpenAPI spec (ads, WhatsApp, inbox, sequences, comment automations, analytics). Call `list_tools()` once to inspect.

## Modes (critical)

`posts_create` has THREE mutually-exclusive modes — pick the right one:
- `is_draft=true` → saved only, not published (NOT what we want for agent runs)
- `publish_now=true` → live immediately (our default for agent runs)
- neither set → scheduled, defaults `schedule_minutes=60`

Our `zernio_mcp.publish_now()` wrapper always uses `posts_publish_now` (which is itself a convenience wrapper around `posts_create(publish_now=true)`).

## Platform strings

Exactly one of: `twitter, instagram, linkedin, tiktok, bluesky, facebook, youtube, pinterest, threads, googlebusiness, telegram, snapchat`.

For cross-post pass a CSV string, e.g. `"twitter,linkedin,bluesky"`.

## Media

Zernio expects `media_urls` as a **comma-separated string of public HTTPS URLs**, NOT a list. Our wrapper joins lists with `,` before sending. Browser-upload flow (`media_generate_upload_link`) is NOT used from the agent — we always pass ImgBB/Pollinations URLs.

Supported: JPG/PNG/WebP/GIF images, MP4/MOV/WebM video, PDF. Max 5GB.

YouTube requires `title`; Pinterest recommends it.

## Env vars

- `ZERNIO_API_KEY` (required, `sync: false`)
- `ZERNIO_MCP_URL` default `https://mcp.zernio.com/mcp`

## Gotchas

- Accounts must be connected inside zernio.com first — the MCP key does not itself authorize X/LinkedIn/etc. If `accounts_list` is empty, posting will fail.
- API key is workspace-scoped: rotating or revoking kills all agent posting. Store in Render env group `fdwa-shared-env` with `sync: false`.
- `posts_publish_now` returns JSON `{post_id, platform, status}` on success; our `_parse()` inspects `error` key to flag failures. A plain text response containing "published" or "scheduled" is also treated as success.
- Twitter character limit still enforced by X (280). We hard-truncate in `post_twitter()`; feeding >280 chars will fail at publish-time even if Zernio accepts the request.

## Code

Implementation: `src/agent/tools/zernio_mcp.py`. Public surface: `is_configured()`, `publish_now()`, `cross_post()`, `post_twitter()`, `list_accounts()`, `call_tool()`, `list_tools()`.
