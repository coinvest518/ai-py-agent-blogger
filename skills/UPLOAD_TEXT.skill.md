# UPLOAD_TEXT Skill

Overview

This document documents the `POST /api/upload_text` endpoint used to publish text-only posts across multiple platforms in a single API call.

Endpoint

POST /api/upload_text

Headers

- `Authorization`: `Apikey <your-api-key-here>` (required)
- `Idempotency-Key`: `unique-string` (optional)

Common Parameters

- `user` (string, required): User identifier.
- `platform[]` (array, required): Supported values: `linkedin`, `x`, `facebook`, `threads`, `reddit`, `bluesky`, `google_business`.
- `title` (string, required): Main text content for the post (used as 'title' param by service).
- `description` (string, optional): Longer body text — used on Reddit as the post body; ignored on many platforms.
- `request_id` (string, optional): Client request id for tracking asynchronous uploads.
- `scheduled_date` (ISO-8601 string, optional): Schedule publish time.
- `timezone` (IANA string, optional): Interprets `scheduled_date` in this timezone; defaults to UTC.
- `async_upload` (boolean, optional): If true, returns `request_id` and processes in background.
- `add_to_queue` (boolean, optional): Schedule to next available queue slot; cannot be combined with `scheduled_date`.
- `first_comment` (string, optional): Post a first comment automatically after publish. Supported on several platforms.

Platform-Specific Notes

- LinkedIn
  - Supports `linkedin_title` and `linkedin_link_url` for link previews. `linkedin_description` may be used as extended commentary in some toolkits.
  - `target_linkedin_page_id` may publish to an organization page instead of the user's personal profile.

- X (Twitter)
  - Long text is split into a thread automatically unless `x_long_text_as_post` is `true` (for eligible accounts).

- Reddit
  - Provide `subreddit` (required) and optionally `flair_id`.
  - Use `description` as post body when provided; otherwise the `title` is used.

- Threads/Bluesky
  - Long text behavior: auto-threading if over platform character limits.

Scheduling / Async Behavior

- Requests that exceed ~59 seconds may be converted to background jobs; use `request_id` with the Upload Status endpoint.
- Scheduled posts respond with `202 Accepted` and a `job_id`.

Examples

Upload Text to LinkedIn

```bash
curl -H 'Authorization: Apikey your-api-key-here' \
  -F 'user="test"' \
  -F 'platform[]=linkedin' \
  -F 'title="Exciting news to share on LinkedIn!"' \
  -X POST https://api.upload-post.com/api/upload_text
```

Create a Twitter Thread (auto-split)

```bash
curl -H 'Authorization: Apikey your-api-key-here' \
  -F 'user="test"' \
  -F 'platform[]=x' \
  -F 'title="Long content... (many paragraphs)"' \
  -X POST https://api.upload-post.com/api/upload_text
```

Repository Usage

- Use `src/agent/agents/upload_post_agent.upload(...)` to publish text-only posts to multiple platforms.
