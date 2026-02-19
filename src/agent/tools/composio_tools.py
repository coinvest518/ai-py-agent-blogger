"""Composio client setup and platform posting tools.

Centralizes all Composio tool.execute() calls so agents never import Composio directly.
"""

import logging
import os

from composio import Composio
from dotenv import load_dotenv

from src.agent.core.config import (
    COMPOSIO_API_KEY,
    FACEBOOK_PAGE_ID,
    INSTAGRAM_ACCOUNT_ID,
    INSTAGRAM_USER_ID,
    LINKEDIN_ACCOUNT_ID,
    LINKEDIN_AUTHOR_URN,
    TWITTER_ACCOUNT_ID,
)

load_dotenv()
logger = logging.getLogger(__name__)

# Shared Composio client (singleton)
_client = None


def get_composio_client() -> Composio:
    """Get or create the shared Composio client."""
    global _client
    if _client is None:
        _client = Composio(api_key=COMPOSIO_API_KEY)
    return _client


# =============================================================================
# Twitter
# =============================================================================

def post_tweet(params: dict) -> dict:
    """Post a tweet. Accepts full params dict (text, media_media_ids, etc).

    Returns dict with success, post_id, url, or error.
    """
    if not TWITTER_ACCOUNT_ID:
        return {"success": False, "error": "TWITTER_ACCOUNT_ID not set"}

    client = get_composio_client()
    try:
        resp = client.tools.execute(
            "TWITTER_CREATION_OF_A_POST",
            params,
            connected_account_id=TWITTER_ACCOUNT_ID,
        )
        data = resp.get("data", {})
        nested = data.get("data", {}) if isinstance(data, dict) else {}
        tweet_id = nested.get("id") or data.get("id") or "unknown"
        url = f"https://twitter.com/user/status/{tweet_id}" if tweet_id != "unknown" else ""
        return {"success": True, "post_id": tweet_id, "url": url}
    except Exception as e:
        logger.exception("Twitter post failed: %s", e)
        return {"success": False, "error": str(e)}


def upload_twitter_media(local_image_path: str) -> dict:
    """Upload media to Twitter. Returns dict with media_id or None."""
    if not TWITTER_ACCOUNT_ID:
        return {"media_id": None}
    client = get_composio_client()
    try:
        resp = client.tools.execute(
            "TWITTER_UPLOAD_MEDIA",
            {"media": os.path.abspath(local_image_path), "media_category": "tweet_image"},
            connected_account_id=TWITTER_ACCOUNT_ID,
        )
        if resp.get("successful"):
            nested = resp.get("data", {}).get("data", {})
            mid = nested.get("id")
            if mid and str(mid) not in ("{}", "None", ""):
                return {"media_id": str(mid)}
    except Exception as e:
        logger.warning("Twitter media upload error: %s", e)
    return {"media_id": None}


def reply_tweet(tweet_id: str, text: str) -> dict:
    """Reply to a tweet."""
    if not tweet_id or tweet_id == "unknown" or not str(tweet_id).isdigit():
        return {"success": False, "error": "No valid post ID"}
    client = get_composio_client()
    try:
        resp = client.tools.execute(
            "TWITTER_CREATION_OF_A_POST",
            {"text": text, "reply_in_reply_to_tweet_id": str(tweet_id)},
            connected_account_id=TWITTER_ACCOUNT_ID,
        )
        reply_id = resp.get("data", {}).get("id", "replied")
        return {"success": True, "reply_id": reply_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Facebook
# =============================================================================

def post_facebook(page_id: str | None, text: str, photo_path: str | None = None) -> dict:
    """Post to Facebook page. Returns dict with success, post_id, or error."""
    page_id = page_id or FACEBOOK_PAGE_ID
    account_id = os.getenv("FACEBOOK_ACCOUNT_ID", "ca_ztimDVH28syB")
    if not page_id:
        return {"error": "FACEBOOK_PAGE_ID not set"}

    client = get_composio_client()
    params = {"page_id": page_id, "message": text, "published": True}

    tool_name = "FACEBOOK_CREATE_POST"
    if photo_path and os.path.exists(photo_path):
        params["photo"] = photo_path
        tool_name = "FACEBOOK_CREATE_PHOTO_POST"

    try:
        resp = client.tools.execute(tool_name, params, connected_account_id=account_id)
        if not resp.get("successful"):
            return {"success": False, "error": resp.get("error", "Unknown")}
        data = resp.get("data", {}).get("response_data", {})
        post_id = data.get("post_id", "")
        return {"success": True, "post_id": post_id}
    except Exception as e:
        logger.exception("Facebook post failed: %s", e)
        return {"success": False, "error": str(e)}


def comment_facebook(post_id: str, message: str) -> dict:
    """Comment on a Facebook post."""
    if not post_id:
        return {"success": False, "error": "No post ID"}
    account_id = os.getenv("FACEBOOK_ACCOUNT_ID", "ca_ztimDVH28syB")
    client = get_composio_client()
    try:
        resp = client.tools.execute(
            "FACEBOOK_CREATE_COMMENT",
            {"message": message, "object_id": post_id},
            connected_account_id=account_id,
        )
        cid = resp.get("data", {}).get("id", "commented")
        return {"success": True, "comment_id": cid}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# LinkedIn
# =============================================================================

def post_linkedin(author_urn: str | None, text: str) -> dict:
    """Post to LinkedIn. Returns dict with success or error."""
    urn = author_urn or LINKEDIN_AUTHOR_URN
    acct = LINKEDIN_ACCOUNT_ID
    if not acct or not urn:
        return {"success": False, "error": "LinkedIn credentials not configured"}
    client = get_composio_client()
    try:
        resp = client.tools.execute(
            "LINKEDIN_CREATE_LINKED_IN_POST",
            {
                "author": urn,
                "commentary": text,
                "lifecycleState": "PUBLISHED",
                "visibility": "PUBLIC",
            },
            connected_account_id=acct,
        )
        if resp.get("successful"):
            return {"success": True}
        return {"success": False, "error": resp.get("error", "Unknown")}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Instagram
# =============================================================================

def post_instagram(caption: str, image_url: str) -> dict:
    """Post to Instagram (image required). Returns dict with instagram_status."""
    if not INSTAGRAM_ACCOUNT_ID or not INSTAGRAM_USER_ID:
        return {"error": "Instagram credentials not configured"}
    if not image_url:
        return {"error": "Image required for Instagram"}
    client = get_composio_client()
    try:
        container = client.tools.execute(
            "INSTAGRAM_CREATE_MEDIA_CONTAINER",
            {
                "ig_user_id": INSTAGRAM_USER_ID,
                "image_url": image_url,
                "caption": caption,
                "content_type": "photo",
            },
            connected_account_id=INSTAGRAM_ACCOUNT_ID,
        )
        if not container.get("successful"):
            return {"error": container.get("error", "Container failed")}
        container_id = container.get("data", {}).get("id", "")
        import time
        time.sleep(10)
        pub = client.tools.execute(
            "INSTAGRAM_CREATE_POST",
            {"ig_user_id": INSTAGRAM_USER_ID, "creation_id": container_id},
            connected_account_id=INSTAGRAM_ACCOUNT_ID,
        )
        if pub.get("successful"):
            post_id = pub.get("data", {}).get("id", "")
            return {"instagram_status": "Posted", "instagram_post_id": post_id}
        return {"error": pub.get("error", "Publish failed")}
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# Telegram (text only — NO images for Telegram)
# =============================================================================

def send_telegram_text(message: str) -> dict:
    """Send text-only message to Telegram group (no images)."""
    from src.agent import telegram_agent
    chat_id = telegram_agent.TELEGRAM_GROUP_USERNAME or telegram_agent.TELEGRAM_GROUP_CHAT_ID
    if not chat_id:
        return {"error": "No Telegram group configured"}
    try:
        result = telegram_agent.send_message(chat_id=chat_id, text=message)
        if result.get("success"):
            msg_id = result.get("data", {}).get("result", {}).get("message_id", "N/A")
            return {"telegram_status": f"Posted: message_id={msg_id}"}
        return {"error": result.get("error", "Unknown")}
    except Exception as e:
        return {"error": str(e)}


def send_telegram_alert(message: str) -> dict:
    """Send alert text to a dedicated Telegram failure chat if configured.

    Falls back to the primary group when no failure-specific target is configured.
    Configure `TELEGRAM_FAILURE_GROUP_USERNAME` (e.g. @omniai_ai) or
    `TELEGRAM_FAILURE_GROUP_CHAT_ID` (numeric chat id) in the environment.
    """
    from src.agent import telegram_agent

    # Prefer explicit failure-chat settings
    failure_chat = os.getenv("TELEGRAM_FAILURE_GROUP_USERNAME") or os.getenv("TELEGRAM_FAILURE_GROUP_CHAT_ID")
    target = failure_chat or (telegram_agent.TELEGRAM_GROUP_USERNAME or telegram_agent.TELEGRAM_GROUP_CHAT_ID)
    if not target:
        return {"error": "No Telegram group configured for alerts"}
    try:
        result = telegram_agent.send_message(chat_id=target, text=message)
        if result.get("success"):
            msg_id = result.get("data", {}).get("result", {}).get("message_id", "N/A")
            return {"telegram_status": f"Posted: message_id={msg_id}"}
        return {"error": result.get("error", "Unknown")}
    except Exception as e:
        return {"error": str(e)}
