# SOCIAL_READ (Composio toolkit slugs — READ path)

Used by `src/agent/agents/engagement_reader_agent.py`. All calls run through
`src/agent/tools/composio_tools._exec_read(slug, args)` which auto-resolves
the connected account via `user_id=COMPOSIO_ENTITY_ID`.

## Facebook
- `FACEBOOK_GET_PAGE_INSIGHTS` — `{page_id, metric, period}`; metrics: `page_impressions`, `page_reach`, `page_engaged_users`, `page_post_engagements`
- `FACEBOOK_GET_POSTS` — `{page_id, limit}` → recent posts with reactions/comments counts

## LinkedIn
- `LINKEDIN_GET_ANALYTICS_FOR_SHARE` — `{share_urn}` → impressions, clicks, engagement, unique-impressions
  - share_urn format: `urn:li:share:<id>`

## Instagram (Graph API, business acct only)
- `INSTAGRAM_GET_MEDIA_INSIGHTS` — `{media_id, metric}`; metrics: `reach,impressions,likes,comments,saved`
- `INSTAGRAM_GET_MEDIA_COMMENTS` — `{media_id}`

## Telegram
- Uses native Bot API `getUpdates` via `src/agent/telegram_agent.get_updates(limit=N)` — no Composio slug needed
- For group metrics the bot must be an admin

## Rate limits
- FB Page Insights: 200 calls/hour/page — cache 6h
- IG Graph: 200 calls/user/hour
- LinkedIn: ~500 calls/day/app
- `engagement_reader_agent` caches in `.engagement_cache.json` with 6h TTL (`CACHE_TTL_SECONDS`).

## Env
- `COMPOSIO_ENTITY_ID` — required
- `FACEBOOK_PAGE_ID`, `INSTAGRAM_USER_ID`, `LINKEDIN_AUTHOR_URN` — per-platform IDs
- `COMPOSIO_TOOLKIT_VERSION_FACEBOOK`/`_INSTAGRAM`/`_LINKEDIN` — pin versions when new READ slugs appear
