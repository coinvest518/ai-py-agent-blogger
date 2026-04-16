# UPLOAD_PHOTOS Skill

Overview

This document describes the `POST /api/upload_photos` endpoint used by Upload-Post.com to upload images (and mixed-image/video carousels for supported platforms) to multiple social networks in a single request.

Endpoint

POST /api/upload_photos

Headers

- `Authorization`: `Apikey <your-api-key-here>` (required)
- `Idempotency-Key`: `unique-string` (optional) — prevents duplicate jobs on retries. Can also be sent as `X-Idempotency-Key` or `X-Request-Id`.

Common Parameters

- `user` (string, required): User identifier (username/account alias).
- `platform[]` (array, required): Target platforms. Supported values include `tiktok`, `instagram`, `linkedin`, `facebook`, `x`, `threads`, `pinterest`, `bluesky`, `reddit`, `google_business`.
- `photos[]` (array, required): Files or URLs for images (jpg, png, etc.). When sent as multipart/form-data, use `photos[]=@/path/to/file.jpg`. When sending URLs, include as `photos[]=https://...`.
- `title` (string, conditional): Default title/caption. Required for Reddit; optional elsewhere.
- `description` (string, optional): Extended text used on TikTok photo descriptions, LinkedIn commentary, Facebook descriptions, Pinterest notes, and Reddit bodies.
- `request_id` (string, optional): Client-supplied request id — returned and used to track upload status.
- `scheduled_date` (ISO-8601 string, optional): Schedule publish time (must be future, ≤ 365 days).
- `timezone` (IANA string, optional): Interprets `scheduled_date` in this timezone; defaults to UTC.
- `async_upload` (boolean, optional): If true, returns immediately with `request_id` and processes in background.
- `add_to_queue` (boolean, optional): If true, schedules to the next available queue slot (cannot be used with `scheduled_date`).
- `max_posts_per_slot` (integer, optional): Override profile's max posts per slot.
- `first_comment` (string, optional): Automatically post a first comment after publishing (supported on Instagram, Facebook, Threads, Bluesky, Reddit, X, YouTube, LinkedIn). Use platform-specific overrides to customize per-platform.
- `first_comment_media[]` (files, optional): Files to attach to the first comment (supported on Reddit).

Platform-Specific Notes

- Instagram
  - `instagram_title` optional, `instagram_first_comment` override available.
  - Supports mixed carousels (photos + videos) when videos are included in `photos[]` for Instagram only.
  - Global `description` is ignored — `title` is used as caption.
  - Meta often rejects repeated third-party CDN URLs; re-hosting to a fresh CDN is recommended.

- LinkedIn
  - `linkedin_title` and `linkedin_description` may be provided; `description` falls back to `title`.
  - Supports `photos[]` uploads. When posting to an organization page, supply `target_linkedin_page_id`.
  - `visibility` can be set (e.g., `PUBLIC`).

- Facebook
  - `facebook_page_id` required when posting to a Page. If omitted and the user has exactly one connected Page, the API will auto-select it.
  - Caption applied only to the first photo.

- X (Twitter)
  - Supports up to 4 images per tweet; more images will create a thread and distribute images across tweets.
  - Use `x_thread_image_layout` to control exact image distribution.

- Pinterest
  - `pinterest_board_id` required.
  - Optional `pinterest_alt_text` and `pinterest_title` available.

- Threads, Bluesky, Reddit, Google Business
  - Threads: supports up to 10 media items in a single post (auto-chunking available).
  - Reddit photo posts support a single image (use `subreddit` parameter).
  - Google Business Profile: supports images and several post types (STANDARD, EVENT, OFFER).

Video Support (Mixed Carousels)

- Only Instagram and Threads allow videos in `photos[]` to create mixed carousels. Do NOT upload videos to this endpoint for other platforms; use the Upload Video endpoint instead.

Idempotency, Timeouts and Scheduling

- Requests may switch to asynchronous processing if they exceed ~59 seconds. When this happens the response will contain `request_id` and processing continues in background.
- Use `request_id` and the Upload Status endpoint to poll for progress when `async_upload` is true or when a sync→background fallback occurs.
- When `scheduled_date` is provided and accepted, the API returns `202 Accepted` and a `job_id` which can be used to correlate later status updates.

Responses

- 200 OK: synchronous completion with `results` mapping per-platform.
- 200 OK (async): returns `success: true` and `request_id` when background processing started.
- 202 Accepted: scheduled job created (includes `job_id`).
- 400/401/403/404/429/500: standard API error responses with details in the JSON body.

Examples

Upload Photo to LinkedIn

```bash
curl -H 'Authorization: Apikey your-api-key-here' \
  -F 'photos[]=@/path/to/image.jpg' \
  -F 'user="test"' \
  -F 'platform[]=linkedin' \
  -F 'title="Product update"' \
  -X POST https://api.upload-post.com/api/upload_photos
```

Upload Mixed Carousel to Instagram (photo + video)

```bash
curl -H 'Authorization: Apikey your-api-key-here' \
  -F 'photos[]=@/path/to/image1.jpg' \
  -F 'photos[]=@/path/to/video1.mp4' \
  -F 'user="test"' \
  -F 'platform[]=instagram' \
  -F 'title="My Mixed Carousel"' \
  -X POST https://api.upload-post.com/api/upload_photos
```

Repository Usage

- In this repo, use `src/agent/agents/upload_post_agent.upload(...)` to call this endpoint. See the convenience wrappers in `src/agent/agents/upload_post_agent.py`.
