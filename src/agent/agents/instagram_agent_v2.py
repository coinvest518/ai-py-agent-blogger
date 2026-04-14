"""Instagram Agent — generate and post Instagram content (image REQUIRED).

Instagram is visual-first. Posts without images are skipped.
"""

import logging
import os
import time

from src.agent.agents.content_agent import generate_instagram
from src.agent.core.config import COMPOSIO_ENTITY_ID, INSTAGRAM_USER_ID
from src.agent.duplicate_detector import record_post
from src.agent.tools.composio_tools import post_instagram

logger = logging.getLogger(__name__)


def run(state: dict) -> dict:
    """Generate Instagram caption and post with image.

    Returns dict with instagram_caption, instagram_status, instagram_post_id.
    """
    logger.info("--- INSTAGRAM AGENT ---")

    insights = state.get("base_insights", "")
    strategy = state.get("ai_strategy")
    image_url = state.get("image_url")

    if not image_url or str(image_url).startswith("file://"):
        logger.warning("Instagram requires a public HTTP image URL — skipping")
        return {"instagram_caption": "", "instagram_status": "Skipped: no public image URL", "instagram_post_id": ""}

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
