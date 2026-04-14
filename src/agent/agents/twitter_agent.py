"""Twitter Agent — direct X API v2 primary, upload-post.com fallback.

Primary path: OAuth 1.0a user context via requests_oauthlib → POST /2/tweets.
  Env keys: TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN,
            TWITTER_ACCESS_TOKEN_SECRET.

Fallback: upload_post_agent (counts against weekly cap, needs public image URL).

Text-only tweets use the direct path. Image tweets try direct first (which
currently posts text-only; native X media upload requires v1.1 media/upload
chunked flow — to be added) and fall back to upload-post for image delivery.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional, Tuple

import requests
from requests_oauthlib import OAuth1Session

from src.agent.agents import upload_post_agent
from src.agent.agents.content_agent import generate_twitter
from src.agent.duplicate_detector import is_duplicate_post, record_post

logger = logging.getLogger(__name__)

TWEETS_URL = "https://api.x.com/2/tweets"
MEDIA_UPLOAD_URL = "https://upload.x.com/1.1/media/upload.json"


def _load_oauth_keys() -> Optional[Tuple[str, str, str, str]]:
    ck = (
        os.getenv("TWITTER_API_KEY")
        or os.getenv("TWITTER_CONSUMER_KEY")
        or os.getenv("X_API_KEY")
        or os.getenv("TWITTER_API_KEY_KEY")
        or os.getenv("X_API_KEY_KEY")
    )
    cs = (
        os.getenv("TWITTER_API_SECRET")
        or os.getenv("TWITTER_API_SECRET_KEY")
        or os.getenv("TWITTER_CONSUMER_SECRET")
        or os.getenv("X_API_SECRET")
        or os.getenv("X_API_SECRET_KEY")
    )
    at = (
        os.getenv("TWITTER_ACCESS_TOKEN")
        or os.getenv("X_ACCESS_TOKEN")
        or os.getenv("TWITTER_ACCESS_TOKEN_KEY")
        or os.getenv("X_ACCESS_TOKEN_KEY")
    )
    ats = (
        os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        or os.getenv("TWITTER_ACCESS_TOKEN_SECRET_KEY")
        or os.getenv("X_ACCESS_TOKEN_SECRET")
        or os.getenv("X_ACCESS_TOKEN_SECRET_KEY")
    )
    if ck and cs and at and ats:
        return ck, cs, at, ats
    return None


def _oauth_session() -> Optional[OAuth1Session]:
    keys = _load_oauth_keys()
    if not keys:
        return None
    ck, cs, at, ats = keys
    return OAuth1Session(
        client_key=ck,
        client_secret=cs,
        resource_owner_key=at,
        resource_owner_secret=ats,
    )


def _upload_media_v1(session: OAuth1Session, image_url: str) -> Optional[str]:
    """Download image from URL, upload to X v1.1 media/upload, return media_id string.

    Uses the simple (non-chunked) path — fine for images ≤ 5MB.
    """
    try:
        img = requests.get(image_url, timeout=30)
        if img.status_code != 200 or not img.content:
            logger.warning("Twitter media: could not fetch image_url (%s)", img.status_code)
            return None
        resp = session.post(MEDIA_UPLOAD_URL, files={"media": img.content}, timeout=60)
        if resp.status_code >= 400:
            logger.warning("Twitter media/upload failed %d: %s", resp.status_code, resp.text[:200])
            return None
        body = resp.json()
        return str(body.get("media_id_string") or body.get("media_id") or "") or None
    except Exception as e:
        logger.warning("Twitter media/upload exception: %s", e)
        return None


def _post_direct(tweet: str, image_url: Optional[str]) -> dict:
    """POST directly to X API v2. Returns {success, tweet_id, error}."""
    session = _oauth_session()
    if not session:
        return {"success": False, "error": "Twitter OAuth keys not configured"}

    payload: dict = {"text": tweet[:280]}
    if image_url:
        media_id = _upload_media_v1(session, image_url)
        if media_id:
            payload["media"] = {"media_ids": [media_id]}

    try:
        resp = session.post(TWEETS_URL, json=payload, timeout=30)
    except Exception as e:
        return {"success": False, "error": f"Direct request failed: {e}"}

    if resp.status_code == 201:
        data = (resp.json() or {}).get("data") or {}
        return {"success": True, "tweet_id": str(data.get("id") or "")}
    return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:240]}"}


def run(state: dict) -> dict:
    """Generate tweet and publish (direct X API first, upload-post fallback)."""
    logger.info("--- TWITTER AGENT (direct + upload-post fallback) ---")

    tweet = state.get("tweet_text", "")
    if not tweet:
        insights = state.get("base_insights", "")
        strategy = state.get("ai_strategy")
        tweet = generate_twitter(insights, strategy)
    if not tweet:
        return {"tweet_text": "", "twitter_url": "Skipped: empty content", "twitter_post_id": ""}

    if is_duplicate_post(tweet, "twitter"):
        suffix = f"\n⏰ {datetime.now().strftime('%I:%M %p')}"
        tweet = tweet[: 280 - len(suffix)] + suffix
        logger.info("Added timestamp to bypass duplicate check")

    image_url = state.get("image_url")

    # --- 1. Direct X API ---
    direct = _post_direct(tweet, image_url)
    if direct.get("success"):
        tid = direct.get("tweet_id") or ""
        url = f"https://twitter.com/i/status/{tid}" if tid.isdigit() else "Posted (direct)"
        record_post(tweet, "twitter", post_id=tid or "direct", image_url=image_url)
        logger.info("Twitter posted via direct API: %s", tid)
        return {"tweet_text": tweet, "twitter_url": url, "twitter_post_id": tid}

    direct_err = direct.get("error", "Unknown")
    logger.warning("Twitter direct failed: %s — trying upload-post fallback", direct_err)

    # --- 2. Upload-post fallback (needs public image URL + weekly quota) ---
    if not image_url:
        return {
            "tweet_text": tweet,
            "twitter_url": f"Failed: direct={direct_err[:80]} (no image for fallback)",
            "twitter_post_id": "",
        }
    if upload_post_agent.remaining_quota() <= 0:
        return {
            "tweet_text": tweet,
            "twitter_url": f"Failed: direct={direct_err[:80]} (upload-post cap reached)",
            "twitter_post_id": "",
        }

    result = upload_post_agent.upload(
        platforms=["x"],
        caption=tweet[:280],
        image_url=image_url,
    )
    if result.get("success"):
        body = result.get("response") or {}
        tid = ""
        if isinstance(body, dict):
            results = body.get("results") or body.get("data") or {}
            if isinstance(results, dict):
                x_data = results.get("x") or results.get("twitter") or {}
                if isinstance(x_data, dict):
                    tid = str(x_data.get("id") or x_data.get("tweet_id") or "")
        url = f"https://twitter.com/i/status/{tid}" if tid.isdigit() else "Posted via upload-post"
        record_post(tweet, "twitter", post_id=tid or "upload-post", image_url=image_url)
        logger.info("Twitter posted via upload-post fallback (remaining=%s)", result.get("remaining"))
        return {"tweet_text": tweet, "twitter_url": url, "twitter_post_id": tid}

    err = result.get("error", "Unknown")
    logger.error("Twitter fallback failed: %s", err)
    return {
        "tweet_text": tweet,
        "twitter_url": f"Failed: direct={direct_err[:60]}; uploadpost={err[:60]}",
        "twitter_post_id": "",
    }


def reply_to_own_tweet(state: dict) -> dict:
    """Reply to our most recent tweet using the direct X API."""
    session = _oauth_session()
    if not session:
        return {"twitter_reply_status": "Skipped: OAuth keys missing"}

    parent_id = state.get("twitter_post_id")
    reply_text = state.get("twitter_reply_text") or ""
    if not parent_id or not reply_text:
        return {"twitter_reply_status": "Skipped: no parent or reply text"}

    try:
        resp = session.post(
            TWEETS_URL,
            json={"text": reply_text[:280], "reply": {"in_reply_to_tweet_id": str(parent_id)}},
            timeout=30,
        )
        if resp.status_code == 201:
            return {"twitter_reply_status": "Posted"}
        return {"twitter_reply_status": f"Failed: HTTP {resp.status_code}: {resp.text[:120]}"}
    except Exception as e:
        return {"twitter_reply_status": f"Failed: {e}"}
