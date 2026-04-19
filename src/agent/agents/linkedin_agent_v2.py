"""LinkedIn Agent — generate and post LinkedIn content.

LinkedIn posts about OUR tools, products, launches — not generic AI trend articles.
Loads LINKEDIN_CONTENT_BRAIN.md for proven formulas.

Daily-cap: enforced via LINKEDIN_DAILY_LIMIT env var (default 1) — checks
social_media_history.json for today's LinkedIn post count before posting.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from src.agent.agents.content_agent import generate_linkedin, strip_markdown
from src.agent.agents import upload_post_agent
from src.agent.tools import pipedream_mcp
from src.agent.tools.composio_tools import (
    get_linkedin_author_urn,
    post_linkedin as _composio_post,
    post_linkedin_with_image,
)
from src.agent.duplicate_detector import record_post

logger = logging.getLogger(__name__)

# Path to the post-history file used for the daily cap check.
_HISTORY_PATH = Path(__file__).resolve().parent.parent.parent.parent / "social_media_history.json"


def _linkedin_posts_today() -> int:
    """Return the number of LinkedIn posts already recorded for today (UTC)."""
    try:
        if not _HISTORY_PATH.exists():
            return 0
        with open(_HISTORY_PATH, encoding="utf-8") as f:
            history = json.load(f)
    except (json.JSONDecodeError, OSError):
        return 0

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entries = history if isinstance(history, list) else history.get("posts", [])
    count = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("platform", "").lower() != "linkedin":
            continue
        ts = str(entry.get("timestamp") or entry.get("posted_at") or "")
        if ts.startswith(today):
            count += 1
    return count


def _clean_for_linkedin(text: str) -> str:
    """Extra sanitization for LinkedIn (defense-in-depth)."""
    # Run global strip first
    text = strip_markdown(text)
    # Remove any surviving markdown bold/italic
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"_{2,}", "", text)
    # Fix malformed hashtags: "hashtag#Tag" → "#Tag"
    text = re.sub(r"\bhashtag#", "#", text, flags=re.IGNORECASE)
    # Collapse excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def run(state: dict) -> dict:
    """Generate LinkedIn post and publish.

    Returns dict with linkedin_text, linkedin_status.
    """
    logger.info("--- LINKEDIN AGENT ---")

    daily_limit = int(os.getenv("LINKEDIN_DAILY_LIMIT", "3"))
    posted_today = _linkedin_posts_today()
    if posted_today >= daily_limit:
        logger.info("LinkedIn daily cap reached (%d/%d) — skipping", posted_today, daily_limit)
        return {"linkedin_text": "", "linkedin_status": f"Skipped: daily cap {posted_today}/{daily_limit}"}

    insights = state.get("base_insights", "")
    strategy = state.get("ai_strategy")

    li_text = generate_linkedin(insights, strategy)
    if not li_text:
        return {"linkedin_text": "", "linkedin_status": "Skipped: empty"}

    # Defense-in-depth: strip any residual markdown before posting
    li_text = _clean_for_linkedin(li_text)

    # Attach a short excerpt of the LinkedIn brain file so callers can diff
    # the agent's output vs the formula/template used.
    brain_snippet = ""
    try:
        from src.agent.core.config import LINKEDIN_BRAIN_PATH
        if LINKEDIN_BRAIN_PATH.exists():
            brain_snippet = LINKEDIN_BRAIN_PATH.read_text(encoding="utf-8")[:1000]
    except Exception:
        brain_snippet = ""

    # Primary: Pipedream MCP (reliable OAuth with w_member_social scope)
    pd_err = None
    if pipedream_mcp.is_configured():
        img = state.get("image_url")
        if img and not str(img).startswith("file://"):
            pd_res = pipedream_mcp.post_linkedin_image(li_text, img)
        else:
            pd_res = pipedream_mcp.post_linkedin_text(li_text)
        if pd_res.get("success"):
            record_post(li_text, "linkedin")
            logger.info("LinkedIn posted via Pipedream MCP")
            return {"linkedin_text": li_text, "linkedin_status": "Posted (pipedream)", "linkedin_brain_snippet": brain_snippet}
        if pd_res.get("connect_url"):
            logger.warning("Pipedream LinkedIn needs authorization: %s", pd_res["connect_url"])
            return {
                "linkedin_text": li_text,
                "linkedin_status": f"Failed: pipedream-auth-required: {pd_res['connect_url']}",
                "linkedin_brain_snippet": brain_snippet,
            }
        pd_err = pd_res.get("error", "Unknown")
        logger.warning("LinkedIn Pipedream failed: %s — trying Composio", pd_err)

    # Fallback 1: Composio
    author_urn = get_linkedin_author_urn(os.getenv("LINKEDIN_AUTHOR_URN"))
    composio_err = None
    if not author_urn:
        composio_err = "creds missing"
    else:
        image_url = state.get("image_url")
        try:
            if image_url:
                result = post_linkedin_with_image(author_urn, li_text, image_url=image_url)
            else:
                result = _composio_post(author_urn, li_text)
        except Exception as e:
            result = {"success": False, "error": str(e)}
        if result.get("success"):
            record_post(li_text, "linkedin")
            logger.info("LinkedIn posted via Composio")
            return {"linkedin_text": li_text, "linkedin_status": "Posted (composio)", "linkedin_brain_snippet": brain_snippet}
        composio_err = result.get("error", "Unknown")
        logger.warning("LinkedIn Composio failed: %s — trying upload-post", composio_err)

    # Fallback 2: upload-post (image-only path)
    image_url = state.get("image_url")
    if not image_url:
        return {"linkedin_text": li_text, "linkedin_status": f"Failed: pipedream={pd_err}; composio={composio_err} (no image for fallback)", "linkedin_brain_snippet": brain_snippet}
    if upload_post_agent.remaining_quota() <= 0:
        return {"linkedin_text": li_text, "linkedin_status": f"Failed: pipedream={pd_err}; composio={composio_err} (upload-post cap reached)", "linkedin_brain_snippet": brain_snippet}

    fb = upload_post_agent.upload(
        platforms=["linkedin"],
        title=(li_text.split("\n", 1)[0] or "FDWA Update")[:90],
        caption=li_text[:2900],
        image_url=image_url,
    )
    if fb.get("success"):
        record_post(li_text, "linkedin")
        logger.info("LinkedIn posted via upload-post fallback")
        return {"linkedin_text": li_text, "linkedin_status": "Posted (upload-post fallback)", "linkedin_brain_snippet": brain_snippet}

    err2 = fb.get("error", "Unknown")
    logger.error("LinkedIn fallback failed: %s", err2)
    return {"linkedin_text": li_text, "linkedin_status": f"Failed: composio={composio_err}; uploadpost={err2[:80]}", "linkedin_brain_snippet": brain_snippet}
