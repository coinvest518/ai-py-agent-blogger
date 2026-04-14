"""Blog Email Agent wrapper — delegates to existing blog_email_agent.py.

✅ FIX: Passes context so the blog system has richer input and fewer false-positive
duplicate blocks.
"""

import logging
import os

from src.agent.blog_email_agent import generate_and_send_blog

logger = logging.getLogger(__name__)


def run(state: dict) -> dict:
    """Generate blog post and send via email.

    Returns dict with blog_status, blog_title.
    """
    logger.info("--- BLOG EMAIL AGENT ---")

    trend_data = state.get("trend_data", "")
    image_url = state.get("image_url")
    video_url = state.get("video_url")

    if image_url:
        os.environ["BLOG_IMAGE_URL"] = image_url
    if video_url:
        os.environ["BLOG_VIDEO_URL"] = video_url

    # Build context from state — intentionally DROP tweet_text so the blog does
    # not parrot social captions or reference "my Twitter/Facebook post".
    # The blog is a standalone educational artifact.
    ctx = {
        "insight": state.get("insight"),
    }

    try:
        result = generate_and_send_blog(trend_data, image_url=image_url, context=ctx)

        if "error" in result:
            logger.error("Blog failed: %s", result["error"])
            return {"blog_status": f"Failed: {result['error']}", "blog_title": ""}

        logger.info("Blog sent: %s", result.get("blog_title", "?"))
        return {
            "blog_status": result.get("email_status", "Sent"),
            "blog_title": result.get("blog_title", ""),
        }
    except Exception as e:
        logger.exception("Blog error: %s", e)
        return {"blog_status": f"Failed: {e!s}", "blog_title": ""}
