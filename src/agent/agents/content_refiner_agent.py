"""Content Refiner Agent — second-pass polish for platform drafts.

Takes the per-platform drafts produced by content_agent + the CFO
monetization angle and rewrites each for clarity, hook strength, and
CTA crispness. Uses a different LLM purpose tag than the drafter so
the cascade routes to a different model when possible (delegation
pattern: drafter writes, refiner edits).

Hard rules preserved:
- Twitter ≤ 280 chars (refiner never expands)
- LinkedIn ≤ 1200 chars
- Plain text only
- Lead magnet first, paid upsell second in the CTA
- Framework tags kept intact

If refinement fails for a platform, the original draft passes through
unchanged.
"""

import logging
from typing import Optional

from src.agent.agents.content_agent import strip_markdown
from src.agent.core.config import PLATFORM_LIMITS
from src.agent.llm_router import route

logger = logging.getLogger(__name__)


def _angle_summary(strategy: dict | None) -> str:
    if not strategy:
        return ""
    angle = strategy.get("monetization_angle") or {}
    parts = []
    if angle.get("free_guide"):
        fg = angle["free_guide"]
        parts.append(f"FREE: {fg.get('name')} → {fg.get('url')}")
    if angle.get("paid_skill"):
        ps = angle["paid_skill"]
        parts.append(f"PAID: {ps.get('name')} (${ps.get('price')}) → {ps.get('url')}")
    fws = angle.get("framework_used") or []
    if fws:
        parts.append(f"Frameworks: {', '.join(fws[:3])}")
    return " | ".join(parts)


def _refine(draft: str, platform: str, char_limit: int, strategy: dict | None,
            extra_rules: str = "") -> str:
    """Run a single platform draft through the refiner LLM."""
    if not draft or not draft.strip():
        return draft

    angle = _angle_summary(strategy)
    topic = (strategy or {}).get("topic", "")

    prompt = f"""You are an editor polishing a {platform} post for a builder-audience funnel.

DRAFT:
{draft}

TOPIC: {topic}
MONETIZATION ANGLE: {angle or "n/a"}

EDITING RULES:
- Keep total length ≤ {char_limit} characters (HARD limit, count carefully)
- Sharpen the opening hook — first line must earn a stop-scroll
- Tighten the CTA — lead magnet first, paid upsell second
- Keep framework tags / handles already present in the draft
- Keep all URLs already present
- Plain text only — no Markdown, no headers, no extra commentary
- Voice: builder-to-builder, concrete, no fluff
{extra_rules}

Return ONLY the polished post text — no preamble, no quotes, no explanation."""

    try:
        llm = route(task=f"refine_{platform}")
        resp = llm.invoke(prompt)
        text = resp.content if hasattr(resp, "content") else str(resp)
        polished = strip_markdown(text.strip())
        if not polished or len(polished) < 20:
            return draft
        if len(polished) > char_limit:
            polished = polished[:char_limit - 3].rstrip() + "..."
        return polished
    except Exception as e:
        logger.warning("Refiner failed for %s: %s — keeping draft", platform, e)
        return draft


def run(state: dict) -> dict:
    """Refine all platform drafts in-place. Returns updated state slices."""
    logger.info("--- CONTENT REFINER AGENT ---")
    strategy = state.get("ai_strategy")

    tweet = state.get("tweet_text", "")
    fb = state.get("facebook_text", "")
    li = state.get("linkedin_text", "")
    ig = state.get("instagram_caption", "")

    out: dict = {}

    if tweet:
        out["tweet_text"] = _refine(
            tweet, "twitter", PLATFORM_LIMITS["twitter"], strategy,
            extra_rules="- Keep the URL the system appended at the end intact",
        )
    if fb:
        out["facebook_text"] = _refine(fb, "facebook", PLATFORM_LIMITS["facebook"], strategy)
    if li:
        out["linkedin_text"] = _refine(li, "linkedin", 1200, strategy,
            extra_rules="- Keep ✅ bullet structure if present")
    if ig:
        out["instagram_caption"] = _refine(
            ig, "instagram", PLATFORM_LIMITS["instagram"], strategy,
            extra_rules="- Do NOT add URLs (Instagram strips them) — say 'link in bio'",
        )

    logger.info("Refined: TW=%d FB=%d LI=%d IG=%d",
                len(out.get("tweet_text", "")), len(out.get("facebook_text", "")),
                len(out.get("linkedin_text", "")), len(out.get("instagram_caption", "")))
    return out
