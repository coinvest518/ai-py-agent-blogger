**LinkedIn Integration Skill**

Purpose: Provide explicit, machine-friendly guidance about LinkedIn's API, required identifiers, rate limits, and recommended fallback and backoff behaviour so AI agents can make safe, compliant decisions when posting to LinkedIn.

Summary:
- Preferred path: use `Composio` toolkit integrations when available and accepted (handles account wiring and toolkit versions).
- Fallback path: when Composio is unavailable, returns toolkit/version errors, or is rate-limited, agents MAY use the direct LinkedIn REST API if valid application credentials and a valid member access token are configured.
- Author identity: Always use a Person URN for the author (format `urn:li:person:<id>`). Activity URNs (`urn:li:activity:...`) are NOT valid as an author and must NOT be used.

Key facts (quick):
- Primary endpoints:
  - Create UGC post: `POST https://api.linkedin.com/v2/ugcPosts` (header `X-Restli-Protocol-Version: 2.0.0`).
  - Register media upload: `POST https://api.linkedin.com/v2/assets?action=registerUpload`.
  - Upload image bytes: use the returned `uploadUrl` (HTTP PUT).
- Required OAuth scope for posting on behalf of a member: `w_member_social` (must be granted by the user via OAuth flow).
- Rate limits (LinkedIn): Member-level ~150 requests/day; Application-level up to 100,000/day (subject to change). Respect these limits with caching and spacing.

Posting workflow (direct LinkedIn API):
1. Ensure you have a valid member access token with `w_member_social` scope (env: `LINKEDIN_ACCESS_TOKEN` or a secure vault). Refresh/rotate tokens as needed.
2. Ensure `LINKEDIN_AUTHOR_URN` is a person URN (`urn:li:person:<id>`). If missing, discover via the OAuth identity assertion (OpenID Connect) or via Composio connected accounts and cache it.
3. For text-only post: `POST /v2/ugcPosts` with JSON body containing `author`, `lifecycleState: "PUBLISHED"`, `specificContent`→`com.linkedin.ugc.ShareContent`→`shareCommentary.text`, and `visibility` set to `PUBLIC`.
   - Example snippet (text-only):

```json
{
  "author": "urn:li:person:8675309",
  "lifecycleState": "PUBLISHED",
  "specificContent": {
    "com.linkedin.ugc.ShareContent": {
      "shareCommentary": { "text": "Hello from FDWA agent" },
      "shareMediaCategory": "NONE"
    }
  },
  "visibility": { "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC" }
}
```

4. For images/videos: call `assets?action=registerUpload` with `owner` set to the person URN and the appropriate `recipes` (e.g. `urn:li:digitalmediaRecipe:feedshare-image`). Save `uploadUrl` and `asset`; PUT bytes to `uploadUrl`; then use the `asset` in `ugcPosts` media block (status `READY`).

Fallback & decision rules for agents:
- If `Composio` posting returns toolkit-version errors (NONEXISTENT_VERSION) or rejects media URLs consistently, the agent should attempt the direct LinkedIn API ONLY if:
  - `LINKEDIN_ACCESS_TOKEN` (or equivalent direct credentials) is present and valid, AND
  - `LINKEDIN_AUTHOR_URN` is a valid person URN (not an activity URN), OR the agent can discover the person URN without excessive Composio calls.
- If Composio returns 429, apply exponential backoff with jitter and consider using the direct API only if application/member rate limits remain available.
- Use `LINKEDIN_DAILY_LIMIT` and `UPLOAD_POST_WEEKLY_CAP` to avoid exceeding account-level caps; prefer upload-post service as a second-line fallback when Composio fails and direct API is not configured.

Caching & observability:
- Cache discovered `urn:li:person:...` values in `agent_status.json` (or vault) with TTL (env: `COMPOSIO_URN_CACHE_TTL_DAYS`) to avoid repeated identity lookups and rate-limited calls.
- Record each LinkedIn POST attempt with timestamp, tool used (`composio` vs `direct` vs `upload-post`), and outcome in `social_media_history.json`.

Rate-limiting & retries:
- Implement exponential backoff with jitter on 429 responses. Configurable env vars: `COMPOSIO_MAX_RETRIES`, `COMPOSIO_RETRY_BACKOFF_BASE` (applies to Composio wrapper) and for direct LinkedIn calls use similar retry policy but respect LinkedIn `Retry-After` headers when provided.
- Throttle member-level posting to `LINKEDIN_DAILY_LIMIT` (default small number) to avoid member rate-limit exhaustion.

Environment variables (recommended):
- `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` — OAuth app
- `LINKEDIN_ACCESS_TOKEN` — member access token (short-lived; prefer refresh flow)
- `LINKEDIN_REFRESH_TOKEN` — (optional)
- `LINKEDIN_AUTHOR_URN` — preferred person URN (if available); MUST be `urn:li:person:...` for posting
- `LINKEDIN_DAILY_LIMIT` — limit posts per member per day
- `COMPOSIO_TOOLKIT_VERSION_LINKEDIN` — when using Composio
- `COMPOSIO_URN_CACHE_TTL_DAYS` — TTL for cached URNs

Security & best practices
- Never commit tokens or secrets to source control. Use environment secrets or a secrets manager.
- Prefer Composio for account wiring; fallback to direct API only when needed and credentials are available.

Suggested agent instructions (to include in agents' decision logic):
- "Before posting to LinkedIn, check `LINKEDIN_AUTHOR_URN` and cached URN. If a valid person URN exists, prefer Composio; if Composio fails with rate-limit or toolkit errors and `LINKEDIN_ACCESS_TOKEN` is present, perform direct API posting using the member token. Cache the person URN after successful direct API call. Respect `LINKEDIN_DAILY_LIMIT` and exponential backoff on rate-limit responses." 

References:
- LinkedIn UGC API docs: https://docs.linkedin.com/
- LinkedIn register upload assets: https://docs.linkedin.com/docs/assets
- Share on LinkedIn / w_member_social scope: See LinkedIn developer portal.

Notes for maintainers:
- This is a behavioural/knowledge skill for agents — it does not implement direct API code. If you want direct-API helpers, add `src/agent/tools/linkedin_direct.py` implementing `post_ugc()` and `upload_asset()` following the workflow above and use tokens from env/secrets.
