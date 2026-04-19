"""Twitter/X agent — Zernio MCP.

Our direct + Composio X paths were removed; Zernio is now the sole transport
(unlimited text + image tweets via one bearer). Failures surface as
twitter_post_id=failed; the final report node logs them.
"""

from __future__ import annotations

import logging
import os

from src.agent.tools import zernio_mcp

logger = logging.getLogger(__name__)


def run(state: dict) -> dict:
    if os.getenv("SKIP_TWITTER", "").lower() in ("1", "true", "yes"):
        logger.info("SKIP_TWITTER set — twitter_agent skipping")
        return {"twitter_url": "", "twitter_post_id": "skipped", "twitter_status": "Skipped (env)"}

    text = (state.get("tweet_text") or "").strip()
    if not text:
        return {"twitter_url": "", "twitter_post_id": "skipped_no_text", "twitter_status": "Skipped (no text)"}

    image_url = state.get("image_url") or None

    if zernio_mcp.is_configured():
        res = zernio_mcp.post_twitter(text, image_url=image_url)
        if res.get("success"):
            data = res.get("data") or {}
            post_id = (data.get("post_id") if isinstance(data, dict) else "") or "posted"
            logger.info("Twitter posted via Zernio MCP")
            return {"twitter_url": "", "twitter_post_id": f"zernio:{post_id}", "twitter_status": "Posted (zernio)"}
        err = res.get("error", "unknown")
        logger.warning("Zernio X post failed: %s", err)
        return {"twitter_url": "", "twitter_post_id": "failed", "twitter_status": f"Failed: zernio={err}"}

    return {"twitter_url": "", "twitter_post_id": "failed", "twitter_status": "Failed: zernio not configured"}
