import logging
import os

logger = logging.getLogger(__name__)


def run(state: dict) -> dict:
    """Safe stub for Twitter agent used during local/dev runs.

    This stub avoids posting to Twitter. It returns a skipped response so the
    graph can proceed. If you want to enable real posting, replace this
    implementation with the real `twitter_agent` logic and ensure
    `SKIP_TWITTER` env is configured appropriately.
    """
    logger.info("twitter_agent stub invoked — skipping real post")
    return {"twitter_url": "", "twitter_post_id": "skipped_stub"}
