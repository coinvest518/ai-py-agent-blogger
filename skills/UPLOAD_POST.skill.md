# UPLOAD_POST Skill

`upload-post.com` aggregates OAuth for platforms we don't reach directly:
Pinterest, X (video + image), Google Business Profile, TikTok, YouTube.

Free tier = **10 uploads/month**, tracked in `.upload_post_usage.json` by
`src/agent/agents/upload_post_agent.py`.

## Entry points

```python
from src.agent.agents import upload_post_agent

# Multi-platform in one call (counts as 1 upload regardless of platforms)
upload_post_agent.upload(
    platforms=["pinterest", "x", "google_business"],
    title="Headline",
    caption="Body",
    image_url="https://...",   # preferred over video_url for 10/mo savings
)

# Single-platform wrappers
upload_post_agent.pin_to_pinterest(title, caption, image_url)
upload_post_agent.tweet_video(caption, video_url)
upload_post_agent.post_google_business(title, caption, image_url)

# Quota check
remaining = upload_post_agent.remaining_quota()
```

## Quota rules

- `upload()` hard-stops when remaining ≤ 0 and returns `{"success": False, "error": "Monthly cap..."}`.
- **Strategy gate:** only post when the content strategy tags
  `promote_product=True` — burning uploads on low-value content wastes the month.
- Counter rolls on calendar month (`YYYY-MM` key).

## Media requirements

| Platform | Image | Video |
|---|---|---|
| `pinterest` | required (HTTPS URL) | supported |
| `x` | required (HTTPS URL) or video_url | preferred for engagement |
| `google_business` | required | not supported |

All media must be a publicly-fetchable HTTPS URL. Local files can be passed
via `image_path`/`video_path` but upload-post will fail if the file isn't
reachable — prefer uploading to ImgBB first, then pass the returned URL.

## Auth

`UPLOAD_POST_API_KEY` in `.env` → `Authorization: Apikey <key>` header.
