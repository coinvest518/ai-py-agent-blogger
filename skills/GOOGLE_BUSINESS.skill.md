# GOOGLE_BUSINESS Skill

Google Business Profile posting is handled via `upload-post.com`
(platform slug `google_business`) — NOT Composio. The Composio
Google Business toolkit is limited; upload-post covers image+caption+CTA.

## Entry point

```python
from src.agent.agents import upload_post_agent
result = upload_post_agent.post_google_business(
    title="Headline (≤58 chars for GBP)",
    caption="Body text with one CTA link",
    image_url="https://public-url/image.jpg",
)
```

## Rules

- Counts as 1 of 10 uploads/month shared with Pinterest/X.
- Only fire for content tagged `promote_product=True` in the AI strategy.
- Image must be a public HTTPS URL (no `file://`, no expiring presigns under 24h).
- Caption ≤1500 chars; first 120 chars show in search — lead with hook.
- If `UPLOAD_POST_API_KEY` is unset → silent skip.
