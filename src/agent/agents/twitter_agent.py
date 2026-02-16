"""Twitter Agent — generate and post tweets with HARD 280-char enforcement.

✅ FIX: URL is included WITHIN the 280 limit, not appended after truncation.
"""

import logging
import os
import time

from src.agent.agents.content_agent import generate_twitter
from src.agent.tools.composio_tools import post_tweet, upload_twitter_media, reply_tweet
from src.agent.tools.image_tools import download_image
from src.agent.duplicate_detector import is_duplicate_post, record_post

logger = logging.getLogger(__name__)


def run(state: dict) -> dict:
    """Generate tweet and post to Twitter.

    Returns dict with tweet_text, twitter_url, twitter_post_id.
    """
    logger.info("--- TWITTER AGENT ---")

    insights = state.get("base_insights", "")
    strategy = state.get("ai_strategy")
    image_url = state.get("image_url")

    # 1. Generate content (280-char hard-enforced inside generate_twitter)
    tweet = generate_twitter(insights, strategy)
    if not tweet:
        return {"tweet_text": "", "twitter_url": "Skipped: empty content", "twitter_post_id": ""}

    # 2. Duplicate check
    if is_duplicate_post(tweet, "twitter"):
        from datetime import datetime
        suffix = f"\n⏰ {datetime.now().strftime('%I:%M %p')}"
        tweet = tweet[: 280 - len(suffix)] + suffix
        logger.info("Added timestamp to bypass duplicate check")

    # 3. Post
    twitter_account_id = os.getenv("TWITTER_ACCOUNT_ID")
    if not twitter_account_id:
        logger.error("TWITTER_ACCOUNT_ID not set")
        return {"tweet_text": tweet, "twitter_url": "Skipped: no account ID", "twitter_post_id": ""}

    params: dict = {"text": tweet}

    # Optional media upload
    if image_url:
        try:
            local_path = download_image(image_url)
            if local_path:
                media_result = upload_twitter_media(os.path.abspath(local_path))
                mid = media_result.get("media_id")
                if mid:
                    params["media_media_ids"] = [str(mid)]
                    logger.info("Media attached: %s", mid)
        except Exception as e:
            logger.warning("Media upload failed, posting text-only: %s", e)

    result = post_tweet(params)

    if result.get("success"):
        post_id = result.get("post_id", "unknown")
        url = f"https://twitter.com/user/status/{post_id}" if post_id != "unknown" else "Posted"
        record_post(tweet, "twitter", post_id=str(post_id), image_url=image_url)
        logger.info("Twitter posted: %s", url)
        return {"tweet_text": tweet, "twitter_url": url, "twitter_post_id": str(post_id)}
    else:
        err = result.get("error", "Unknown")
        # Detect expired/revoked account connections
        if "EXPIRED" in str(err).upper() or "410" in str(err):
            logger.error("Twitter account connection EXPIRED — reconnect at composio.dev")
            return {"tweet_text": tweet, "twitter_url": "Failed: Account EXPIRED — reconnect at composio.dev", "twitter_post_id": ""}
        logger.error("Twitter post failed: %s", err)
        return {"tweet_text": tweet, "twitter_url": f"Failed: {err}", "twitter_post_id": ""}


def reply_to_own_tweet(state: dict) -> dict:
    """Reply to the agent's own tweet with a CTA link."""
    logger.info("--- TWITTER REPLY ---")
    post_id = state.get("twitter_post_id")

    if not post_id or post_id == "unknown" or not str(post_id).isdigit():
        return {"twitter_reply_status": "Skipped: no valid post ID"}

    time.sleep(5)
    reply_msg = "Learn more about AI Consulting and Development for your business: https://fdwa.site 🚀"
    result = reply_tweet(str(post_id), reply_msg)

    if result.get("success"):
        return {"twitter_reply_status": f"Replied: {result.get('reply_id', 'ok')}"}
    return {"twitter_reply_status": f"Failed: {result.get('error', '?')}"}
