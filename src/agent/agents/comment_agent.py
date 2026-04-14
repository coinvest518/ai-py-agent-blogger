"""Comment Agent — Instagram comment monitoring + Twitter reply + Facebook comment.

Handles all post-publish engagement in one node.
"""

import logging
import os
import time

from src.agent.instagram_comment_agent import generate_instagram_reply
from src.agent.tools.composio_tools import get_composio_client, _execute_with_fallback

logger = logging.getLogger(__name__)


def monitor_instagram(state: dict) -> dict:
    """Check Instagram post for comments and reply to the first one."""
    logger.info("--- INSTAGRAM COMMENT MONITOR ---")
    post_id = state.get("instagram_post_id")
    if not post_id:
        return {"instagram_comment_status": "Skipped: no post ID"}

    time.sleep(30)

    try:
        client = get_composio_client()
        entity = os.getenv("COMPOSIO_ENTITY_ID") or os.getenv("COMPOSIO_USER_ID")
        if not entity:
            return {"instagram_comment_status": "Skipped: COMPOSIO_ENTITY_ID not set"}

        resp = _execute_with_fallback("INSTAGRAM_GET_POST_COMMENTS", {"ig_post_id": post_id, "limit": 5}, entity)

        if not resp.get("successful"):
            return {"instagram_comment_status": "No comments yet"}

        comments = resp.get("data", {}).get("data", [])
        if not comments:
            return {"instagram_comment_status": "No comments yet"}

        first = comments[0]
        cid = first.get("id", "")
        text = first.get("text", "")
        username = first.get("username", "user")

        reply = generate_instagram_reply(text, username)
        reply_resp = _execute_with_fallback(
            "INSTAGRAM_REPLY_TO_COMMENT", {"ig_comment_id": cid, "message": reply}, entity
        )

        if reply_resp.get("successful"):
            return {"instagram_comment_status": f"Replied to @{username}"}
        return {"instagram_comment_status": f"Failed: {reply_resp.get('error', '?')}"}

    except Exception as e:
        logger.exception("IG comment error: %s", e)
        return {"instagram_comment_status": f"Failed: {e!s}"}
