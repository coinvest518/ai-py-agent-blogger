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
    """Comment on our own Facebook post with CTA link."""
    logger.info("--- FACEBOOK COMMENT ---")
    post_id = state.get("facebook_post_id")
    if not post_id:
        return {"comment_status": "Skipped: no post ID"}

    time.sleep(10)
    result = comment_facebook(post_id, "Learn more at https://fdwa.site 🚀")

    if result.get("success"):
        return {"comment_status": f"Commented: {result.get('comment_id', 'ok')}"}
    return {"comment_status": f"Failed: {result.get('error', '?')}"}
