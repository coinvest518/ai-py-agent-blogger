"""Instagram Agent — generate and post Instagram content (image REQUIRED).

Instagram is visual-first. Posts without images are skipped.
"""

import logging
import os
import time

from src.agent.agents.content_agent import generate_instagram
from src.agent.core.config import COMPOSIO_ENTITY_ID, INSTAGRAM_USER_ID
from src.agent.duplicate_detector import record_post
from src.agent.tools.composio_tools import post_instagram, post_facebook

logger = logging.getLogger(__name__)


def run(state: dict) -> dict:
    """Generate Instagram caption and post with image.

    Returns dict with instagram_caption, instagram_status, instagram_post_id.
    """
    logger.info("--- INSTAGRAM AGENT ---")

    insights = state.get("base_insights", "")
    strategy = state.get("ai_strategy")
    image_url = state.get("image_url")

    # Allow operator to force text-only posting fallback (for debugging)
    skip_image_env = os.getenv("SKIP_INSTAGRAM_IMAGE", "false").lower() in ("1", "true", "yes")
    if not image_url or str(image_url).startswith("file://") or skip_image_env:
        logger.warning("Instagram image disabled or missing — using text-only fallback")
        caption = generate_instagram(insights, strategy)
        if not caption:
            return {"instagram_caption": "", "instagram_status": "Skipped: empty caption", "instagram_post_id": ""}

        # Try a safe fallback: post the caption to Facebook so the message still goes out.
        try:
            fb_res = post_facebook(None, caption)
            if fb_res.get("success"):
                post_id = fb_res.get("post_id", "")
                record_post(caption, "instagram_fallback", post_id=post_id)
                logger.info("Instagram text-only fallback posted to Facebook: %s", post_id)
                return {"instagram_caption": caption, "instagram_status": "Posted (fb fallback)", "instagram_post_id": "" , "facebook_status": f"Posted: {post_id}"}
            err = fb_res.get("error") or fb_res.get("raw") or "Unknown"
            logger.warning("IG fallback to FB failed: %s", err)
            return {"instagram_caption": caption, "instagram_status": f"Failed fallback: {err}", "instagram_post_id": ""}
        except Exception as e:
            logger.exception("IG fallback posting error: %s", e)
            return {"instagram_caption": caption, "instagram_status": f"Failed: {e!s}", "instagram_post_id": ""}

    caption = generate_instagram(insights, strategy)
    if not caption:
        return {"instagram_caption": "", "instagram_status": "Skipped: empty caption", "instagram_post_id": ""}

    ig_user_id = INSTAGRAM_USER_ID or os.getenv("INSTAGRAM_USER_ID") or os.getenv("INSTAGRAM_USER_NAME")
    entity = COMPOSIO_ENTITY_ID or os.getenv("COMPOSIO_ENTITY_ID") or os.getenv("COMPOSIO_USER_ID")
    if not ig_user_id or not entity:
        logger.error(
            "Instagram creds missing — INSTAGRAM_USER_ID=%r COMPOSIO_ENTITY_ID=%r",
            bool(ig_user_id), bool(entity),
        )
        return {"instagram_caption": caption, "instagram_status": "Skipped: creds missing", "instagram_post_id": ""}

    # Use composio_tools wrapper to handle client initialization and toolkit versions
    try:
        result = post_instagram(caption, image_url)
        if result.get("instagram_status") == "Posted" or result.get("instagram_post_id"):
            post_id = result.get("instagram_post_id", "")
            record_post(caption, "instagram", post_id=post_id, image_url=image_url)
            logger.info("Instagram posted: %s", post_id)
            return {"instagram_caption": caption, "instagram_status": "Posted", "instagram_post_id": post_id}
        err = result.get("error") or result.get("instagram_status") or "Unknown"
        logger.error("IG publish failed: %s", err)
        return {"instagram_caption": caption, "instagram_status": f"Failed: {err}", "instagram_post_id": ""}
    except Exception as e:
        logger.exception("Instagram error: %s", e)
        return {"instagram_caption": caption, "instagram_status": f"Failed: {e!s}", "instagram_post_id": ""}
