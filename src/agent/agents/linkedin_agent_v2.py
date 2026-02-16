"""LinkedIn Agent — generate and post LinkedIn content.

✅ FIX: LinkedIn now posts about YOUR tools, products, launches, client wins —
not generic AI trend articles.  Loads LINKEDIN_CONTENT_BRAIN.md for proven formulas.
"""

import logging
import os
import re

from src.agent.agents.content_agent import generate_linkedin, strip_markdown
from src.agent.tools.composio_tools import post_linkedin as _composio_post
from src.agent.duplicate_detector import record_post

logger = logging.getLogger(__name__)


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

    insights = state.get("base_insights", "")
    strategy = state.get("ai_strategy")

    li_text = generate_linkedin(insights, strategy)
    if not li_text:
        return {"linkedin_text": "", "linkedin_status": "Skipped: empty"}

    # Defense-in-depth: strip any residual markdown before posting
    li_text = _clean_for_linkedin(li_text)

    account_id = os.getenv("LINKEDIN_ACCOUNT_ID")
    author_urn = os.getenv("LINKEDIN_AUTHOR_URN")
    if not account_id or not author_urn:
        logger.error("LinkedIn creds missing: LINKEDIN_ACCOUNT_ID=%s, LINKEDIN_AUTHOR_URN=%s",
                      account_id, author_urn)
        return {"linkedin_text": li_text, "linkedin_status": "Skipped: creds missing"}

    result = _composio_post(author_urn, li_text)

    if result.get("success"):
        record_post(li_text, "linkedin")
        logger.info("LinkedIn posted")
        return {"linkedin_text": li_text, "linkedin_status": "Posted"}
    else:
        err = result.get("error", "Unknown")
        logger.error("LinkedIn failed: %s", err)
        return {"linkedin_text": li_text, "linkedin_status": f"Failed: {err}"}
