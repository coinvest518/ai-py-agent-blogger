"""Facebook Agent — generate and post Facebook content with optional image."""

import logging
import os
import time

from src.agent.agents.content_agent import generate_facebook
from src.agent.tools.composio_tools import post_facebook, comment_facebook
from src.agent.tools.image_tools import download_image
from src.agent.duplicate_detector import record_post

logger = logging.getLogger(__name__)


def run(state: dict) -> dict:
    """Generate Facebook post and publish.

    Returns dict with facebook_text, facebook_status, facebook_post_id.
    """
    logger.info("--- FACEBOOK AGENT ---")

    insights = state.get("base_insights", "")
    strategy = state.get("ai_strategy")
    image_url = state.get("image_url")

    # Generate content
    fb_text = generate_facebook(insights, strategy)
    if not fb_text:
        return {"facebook_text": "", "facebook_status": "Skipped: empty", "facebook_post_id": ""}

    page_id = os.getenv("FACEBOOK_PAGE_ID")
    if not page_id:
        logger.error("FACEBOOK_PAGE_ID not set")
        return {"facebook_text": fb_text, "facebook_status": "Skipped: no page ID", "facebook_post_id": ""}

    # Resolve local image if available
    local_image = None
    if image_url:
        try:
            local_image = download_image(image_url)
        except Exception:
            local_image = None

    result = post_facebook(page_id, fb_text, photo_path=local_image)

    if result.get("success"):
        post_id = result.get("post_id", "")
        record_post(fb_text, "facebook", post_id=post_id, image_url=image_url)
        logger.info("Facebook posted: %s", post_id)
        return {"facebook_text": fb_text, "facebook_status": f"Posted: {post_id}", "facebook_post_id": post_id}
    else:
        err = result.get("error", "Unknown")
        # Detect expired/revoked account connections
        if "EXPIRED" in str(err).upper() or "410" in str(err):
            logger.error("Facebook account connection EXPIRED — reconnect at composio.dev")
            return {"facebook_text": fb_text, "facebook_status": "Failed: Account EXPIRED — reconnect at composio.dev", "facebook_post_id": ""}
        logger.error("Facebook post failed: %s", err)
        return {"facebook_text": fb_text, "facebook_status": f"Failed: {err}", "facebook_post_id": ""}


def comment_on_post(state: dict) -> dict:
    """Comment on our own Facebook post with LLM-generated CTA."""
    logger.info("--- FACEBOOK COMMENT ---")
    post_id = state.get("facebook_post_id")
    if not post_id:
        return {"comment_status": "Skipped: no post ID"}

    from src.agent.core.config import get_site_for_topic
    from src.agent.llm_router import route
    from src.agent.agents.content_agent import _llm_generate

    topic = (state.get("strategy") or {}).get("topic", "general")
    site = get_site_for_topic(topic)
    fb_text = state.get("facebook_text", "")[:400]

    prompt = (
        f"Write a single 1-line follow-up comment (<140 chars) on our own Facebook post. "
        f"Post topic: {topic}. Post excerpt: {fb_text}\n"
        f"End with the link {site}. No hashtags. Plain text, 1-2 emojis max."
    )
    comment_text = _llm_generate(prompt, "Facebook self-comment")
    if not comment_text:
        logger.warning("Facebook comment LLM empty — skipping self-comment")
        return {"comment_status": "Skipped: LLM empty"}

    time.sleep(10)
    result = comment_facebook(post_id, comment_text)

    if result.get("success"):
        return {"comment_status": f"Commented: {result.get('comment_id', 'ok')}"}
    return {"comment_status": f"Failed: {result.get('error', '?')}"}
