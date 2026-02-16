"""Instagram Agent — generate and post Instagram content (image REQUIRED).

Instagram is visual-first. Posts without images are skipped.
"""

import logging
import os
import time

from src.agent.agents.content_agent import generate_instagram
from src.agent.duplicate_detector import record_post

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

    ig_user_id = os.getenv("INSTAGRAM_USER_ID")
    ig_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
    if not ig_user_id or not ig_account_id:
        logger.error("Instagram creds missing")
        return {"instagram_caption": caption, "instagram_status": "Skipped: creds missing", "instagram_post_id": ""}

    try:
        from composio import Composio
        composio_client = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))

        # Step 1: create media container
        container_resp = composio_client.tools.execute(
            "INSTAGRAM_CREATE_MEDIA_CONTAINER",
            {
                "ig_user_id": ig_user_id,
                "image_url": image_url,
                "caption": caption,
                "content_type": "photo",
            },
            connected_account_id=ig_account_id,
        )

        if not container_resp.get("successful"):
            err = container_resp.get("error", "Container creation failed")
            logger.error("IG container failed: %s", err)
            return {"instagram_caption": caption, "instagram_status": f"Failed: {err}", "instagram_post_id": ""}

        container_id = container_resp.get("data", {}).get("id", "")
        logger.info("IG container created: %s — waiting 10 s", container_id)
        time.sleep(10)

        # Step 2: publish
        pub_resp = composio_client.tools.execute(
            "INSTAGRAM_CREATE_POST",
            {"ig_user_id": ig_user_id, "creation_id": container_id},
            connected_account_id=ig_account_id,
        )

        if pub_resp.get("successful"):
            post_id = pub_resp.get("data", {}).get("id", "")
            record_post(caption, "instagram", post_id=post_id, image_url=image_url)
            logger.info("Instagram posted: %s", post_id)
            return {"instagram_caption": caption, "instagram_status": "Posted", "instagram_post_id": post_id}
        else:
            err = pub_resp.get("error", "Publish failed")
            logger.error("IG publish failed: %s", err)
            return {"instagram_caption": caption, "instagram_status": f"Failed: {err}", "instagram_post_id": ""}

    except Exception as e:
        logger.exception("Instagram error: %s", e)
        return {"instagram_caption": caption, "instagram_status": f"Failed: {e!s}", "instagram_post_id": ""}
