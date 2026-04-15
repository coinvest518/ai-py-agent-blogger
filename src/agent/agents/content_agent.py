"""Content Agent — master content generator that produces platform-specific posts.

Consults the AI Decision Engine, then delegates to per-platform generators.
Each platform gets independently crafted content — NOT the same text adapted.
"""

import logging
import re
from datetime import datetime

from src.agent.core.config import (
    PLATFORM_LIMITS,
    get_site_for_topic,
    detect_topic,
)
from src.agent.llm_provider import get_llm

logger = logging.getLogger(__name__)


# =============================================================================
# Markdown stripper (social platforms don't render markdown)
# =============================================================================

def strip_markdown(text: str) -> str:
    """Remove Markdown formatting for plain-text platforms."""
    # Bold (handles multiline)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"__(.+?)__", r"\1", text, flags=re.DOTALL)
    # Italic
    text = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)
    # Links: [text](url) → url (platforms auto-link)
    text = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r"\2", text)
    # Headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Inline code
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Horizontal rules
    text = re.sub(r"^[-*_]{3,}$", "", text, flags=re.MULTILINE)
    # Blockquotes
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    # Cleanup
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _llm_generate(prompt: str, purpose: str) -> str:
    """Call cascading LLM and return cleaned text."""
    try:
        llm = get_llm(purpose=purpose)
        resp = llm.invoke(prompt)
        text = resp.content if hasattr(resp, "content") else str(resp)
        return strip_markdown(text.strip())
    except Exception as e:
        logger.warning("LLM failed for %s: %s", purpose, e)
        return ""


# Twitter handle map for framework tagging
_FRAMEWORK_HANDLES = {
    "LangChain": "@LangChainAI",
    "LangGraph": "@LangChainAI",
    "Composio": "@composiohq",
    "LangSmith": "@LangChainAI",
    "Mistral": "@MistralAI",
    "OpenRouter": "@OpenRouterAI",
    "Hugging Face": "@huggingface",
    "Cloudflare Workers AI": "@cloudflare",
    "Astra DB (DataStax)": "@datastax",
    "Anthropic Claude / OpenClaw": "@AnthropicAI",
}


def _brief_block(strategy: dict | None, platform: str) -> str:
    """Render the strategy_agent brief (engagement+GA-derived) into the prompt.

    The brief wins over generic insights — it's the cycle's marching order.
    Empty string when no brief was produced (e.g. supervisor disabled).
    """
    if not strategy:
        return ""
    brief = strategy.get("brief") or {}
    if not brief:
        return ""
    try:
        from src.agent.agents.strategy_agent import format_for_prompt, format_platform_hint
        head = format_for_prompt(brief)
        tail = format_platform_hint(brief, platform)
        return (head + tail) if head else ""
    except Exception:
        return ""


def _monetization_block(strategy: dict | None, platform: str) -> str:
    """Render the CFO monetization angle into a prompt fragment.

    Tells the LLM: which product to push, the framework angle, and the CTA
    line. Empty string when no strategy is provided.
    """
    if not strategy:
        return ""
    angle = strategy.get("monetization_angle") or {}
    if not angle:
        return ""

    # Belt-and-braces: if the strategy brief said "avoid X", drop X from the
    # monetization block even if the decision engine slipped it back in.
    avoid_list = [str(a).lower() for a in ((strategy.get("brief") or {}).get("avoid") or [])]

    def _blocked(prod: dict | None) -> bool:
        if not prod or not avoid_list:
            return False
        name = str(prod.get("name", "")).lower()
        return any(a and (a in name or name in a) for a in avoid_list)

    lines = ["", "MONETIZATION ANGLE (this post must support our funnel):"]
    if angle.get("free_guide") and not _blocked(angle["free_guide"]):
        fg = angle["free_guide"]
        lines.append(f"- Free lead magnet: {fg.get('name')} → {fg.get('url')}")
    if angle.get("paid_skill") and not _blocked(angle["paid_skill"]):
        ps = angle["paid_skill"]
        lines.append(f"- Paid upsell: {ps.get('name')} (${ps.get('price')}) → {ps.get('url')}")
    frameworks = angle.get("framework_used") or []
    if frameworks:
        if platform == "twitter":
            handles = " ".join(_FRAMEWORK_HANDLES.get(f, "") for f in frameworks if _FRAMEWORK_HANDLES.get(f))
            if handles:
                lines.append(f"- Tag these accounts: {handles.strip()}")
        else:
            lines.append(f"- Frameworks we used: {', '.join(frameworks)} (mention them so devs find us)")
    if angle.get("affiliate"):
        aff = angle["affiliate"]
        lines.append(f"- Optional affiliate (only if contextually relevant): {aff.get('name')} → {aff.get('url')}")
    lines.append("- Position content as 'how we built X with [framework]', NOT generic advice")
    return "\n".join(lines) + "\n"


def _framework_footer(strategy: dict | None) -> str:
    """Builder-tag footer line for non-Twitter platforms."""
    if not strategy:
        return ""
    angle = strategy.get("monetization_angle") or {}
    fws = angle.get("framework_used") or []
    if not fws:
        return ""
    return f"Built with {' + '.join(fws[:3])}"


# =============================================================================
# Per-platform content generators
# =============================================================================

def generate_twitter(insights: str, strategy: dict | None = None) -> str:
    """Generate Twitter post — MAX 280 chars, enforced AFTER all additions."""
    year = datetime.now().year
    topic = (strategy or {}).get("topic", "general")
    site = get_site_for_topic(topic)

    # Inject memory examples from past high-performing posts
    memory_hint = ""
    if strategy and strategy.get("memory_examples"):
        examples = strategy["memory_examples"]
        if isinstance(examples, list):
            memory_hint = "\nPast high-performing posts (use as style reference):\n" + "\n".join(
                f"- {ex}" for ex in examples[:3]
            ) + "\n"
        elif isinstance(examples, str) and len(examples) > 10:
            memory_hint = f"\nPast high-performing posts:\n{examples[:300]}\n"

    brief = _brief_block(strategy, "twitter")
    monetization = _monetization_block(strategy, "twitter")
    prompt = f"""Current year: {year}. Create a Twitter post based on this insight:

{insights[:300]}
{brief}{memory_hint}{monetization}
HARD RULES:
- MAXIMUM 250 characters (leave room for link)
- Plain text only — NO Markdown
- Use {year} for dates
- Include 1-2 relevant emojis
- 1-2 hashtags max — prefer #OpenClaw #AIAgents over generic tags
- Frame as "how we built X" — builder voice, not generic advice
- Do NOT include any URL — the system appends one automatically

Output ONLY the tweet text."""

    tweet = _llm_generate(prompt, "Twitter content")
    if not tweet:
        logger.warning("Twitter LLM returned empty — skipping tweet (no hardcoded fallback)")
        return ""

    # Append correct site link
    suffix = f" {site}"
    max_text = PLATFORM_LIMITS["twitter"] - len(suffix)
    if len(tweet) > max_text:
        tweet = tweet[:max_text - 3].rstrip() + "..."
    tweet = tweet + suffix

    # Final hard enforcement
    if len(tweet) > PLATFORM_LIMITS["twitter"]:
        tweet = tweet[:277] + "..."

    logger.info("Twitter: %d chars", len(tweet))
    return tweet


def generate_facebook(insights: str, strategy: dict | None = None) -> str:
    """Generate Facebook post — conversational, 400-600 chars."""
    topic = (strategy or {}).get("topic", "general")
    site = get_site_for_topic(topic)

    brief = _brief_block(strategy, "facebook")
    monetization = _monetization_block(strategy, "facebook")
    prompt = f"""Create a Facebook post based on this insight:

{insights[:500]}
{brief}{monetization}
Requirements:
- Conversational, builder-to-builder tone
- 400-600 characters
- Plain text only (NO Markdown)
- Relevant emojis
- Frame as "we built X with [framework] — here is how" — not generic advice
- Promote the free guide first (lead magnet), upsell the paid skill second
- CTA: {site}
- 3-4 hashtags: #OpenClaw #AIAgents #LangChain
- Value-driven and engaging

Output ONLY the Facebook post text."""

    post = _llm_generate(prompt, "Facebook content")
    if not post:
        logger.warning("Facebook LLM returned empty — skipping post (no hardcoded fallback)")
        return ""

    if site not in post:
        post += f"\n\nLearn more: {site}"

    footer = _framework_footer(strategy)
    if footer and footer not in post:
        post += f"\n\n{footer}"

    limit = PLATFORM_LIMITS["facebook"]
    if len(post) > limit:
        post = post[:limit - 3] + "..."
    logger.info("Facebook: %d chars", len(post))
    return post


def generate_linkedin(insights: str, strategy: dict | None = None) -> str:
    """Generate LinkedIn post — professional, focused on YOUR tools/products/client wins.

    ✅ FIX: LinkedIn is about your products, launches, case studies — not generic AI trends.
    """
    topic = (strategy or {}).get("topic", "general")
    site = get_site_for_topic(topic)
    products = strategy.get("products", []) if strategy else []
    year = datetime.now().year

    # Build product context
    product_lines = ""
    if products:
        product_lines = "\nProducts to showcase:\n" + "\n".join(
            f"- {p.get('name', '?')} ({p.get('price', 'Free')})" for p in products[:3]
        )

    # Load LinkedIn brain if available
    formula = ""
    try:
        from src.agent.core.config import LINKEDIN_BRAIN_PATH
        if LINKEDIN_BRAIN_PATH.exists():
            raw = LINKEDIN_BRAIN_PATH.read_text(encoding="utf-8")[:800]
            formula = f"\nFollow these proven formulas:\n{raw}\n"
    except Exception:
        pass

    # Inject memory examples for learning from past success
    memory_hint = ""
    if strategy and strategy.get("memory_examples"):
        examples = strategy["memory_examples"]
        if isinstance(examples, list):
            memory_hint = "\nPast high-performing LinkedIn posts (learn from the style):\n" + "\n".join(
                f"- {ex}" for ex in examples[:3]
            ) + "\n"
        elif isinstance(examples, str) and len(examples) > 10:
            memory_hint = f"\nPast high-performing posts:\n{examples[:300]}\n"

    brief = _brief_block(strategy, "linkedin")
    monetization = _monetization_block(strategy, "linkedin")
    prompt = f"""You are Daniel Wray, founder of FDWA — we build OpenClaw skills and AI agent tooling.
Write a LinkedIn post for {year}.

Context/insight:
{insights[:400]}
{product_lines}
{formula}
{brief}{memory_hint}{monetization}
LINKEDIN RULES:
- 600-1200 characters MAXIMUM (sweet spot for engagement — LinkedIn hard limit is 3000)
- NEVER exceed 1200 characters — shorter performs better
- Write as a BUILDER sharing what we shipped, the stack we used, the gotchas
- Start with a concrete result or build story (no generic intros)
- Include the framework names (LangChain, LangGraph, Composio, Mistral) where relevant
- Use ✅ bullet points for readability
- Plain text only (NO Markdown)
- 3-5 hashtags max — prefer #OpenClaw #AIAgents #LangChain #Composio
- CTA: lead magnet first → upsell second → {site}
- Topic focus: {topic}

THIS IS NOT a generic AI article — it's YOUR builder's notebook.

Output ONLY the LinkedIn post text."""

    post = _llm_generate(prompt, "LinkedIn content")
    if not post:
        logger.warning("LinkedIn LLM returned empty — skipping post (no hardcoded fallback)")
        return ""

    if site not in post:
        post += f"\n\nLearn more: {site}"

    footer = _framework_footer(strategy)
    if footer and footer not in post:
        post += f"\n\n{footer}"

    limit = PLATFORM_LIMITS["linkedin"]
    if len(post) > limit:
        post = post[:limit - 3] + "..."
    logger.info("LinkedIn: %d chars", len(post))
    return post


def generate_instagram(insights: str, strategy: dict | None = None) -> str:
    """Generate Instagram caption — visual-first, emoji-heavy, 400-600 chars."""
    year = datetime.now().year
    topic = (strategy or {}).get("topic", "general")

    brief = _brief_block(strategy, "instagram")
    monetization = _monetization_block(strategy, "instagram")
    prompt = f"""Current year: {year}. Create an Instagram caption:

{insights[:400]}
{brief}{monetization}
Requirements:
- Visual-first, builder/maker tone
- 400-600 characters
- Plain text only (NO Markdown)
- Emoji-heavy (but tasteful)
- Frame as "we built this AI agent — here is what it does"
- Mention link in bio (free guide first, paid skill second)
- Hashtags: #OpenClaw #AIAgents #LangChain #BuildInPublic
- NO URLs in caption (Instagram doesn't allow clickable links)

Output ONLY the Instagram caption."""

    caption = _llm_generate(prompt, "Instagram content")
    if not caption:
        logger.warning("Instagram LLM returned empty — skipping caption (no hardcoded fallback)")
        return ""

    limit = PLATFORM_LIMITS["instagram"]
    if len(caption) > limit:
        caption = caption[:limit - 3] + "..."
    logger.info("Instagram: %d chars", len(caption))
    return caption


def generate_telegram(insights: str, strategy: dict | None = None) -> dict:
    """Generate Telegram message — internal FDWA status briefing.

    Replaces the old crypto market dump. Telegram is now the operator
    channel: what the agent researched this run, where it posted, which
    product it promoted, when the next run is. Crypto data is only added
    when the picked topic is crypto-related (yieldbot side-brand mode).

    Returns dict with:
      - message: str (the Telegram briefing)
      - crypto_analysis: dict (only populated when topic is crypto)
    """
    strategy = strategy or {}
    topic = strategy.get("topic", "general")
    angle = strategy.get("monetization_angle") or {}
    products = strategy.get("products", [])

    # Build internal briefing
    parts = ["🤖 FDWA Agent Briefing", ""]
    parts.append(f"• Researched: {topic}")

    brief = strategy.get("brief") or {}
    if brief.get("angle"):
        parts.append(f"• Angle: {brief['angle'][:140]}")
    if brief.get("reasoning"):
        parts.append(f"• Why this: {brief['reasoning'][:140]}")

    if products:
        names = ", ".join(p.get("name", "?")[:40] for p in products[:2])
        parts.append(f"• Promoting: {names}")

    if angle.get("free_guide"):
        fg = angle["free_guide"]
        parts.append(f"• Free lead magnet: {fg.get('name', '?')[:60]}")
    if angle.get("paid_skill"):
        ps = angle["paid_skill"]
        parts.append(f"• Paid upsell: {ps.get('name', '?')[:60]} (${ps.get('price')})")

    fws = angle.get("framework_used") or []
    if fws:
        parts.append(f"• Stack tagged: {', '.join(fws[:3])}")

    if angle.get("affiliate"):
        parts.append(f"• Affiliate angle: {angle['affiliate'].get('name')}")

    parts.append("• Posting to: Twitter, Facebook, LinkedIn, Instagram")
    parts.append("• Next run: ~6h")

    if angle.get("primary_url"):
        parts.append("")
        parts.append(f"🔗 {angle['primary_url']}")

    crypto_analysis = {}
    # Only fetch crypto data when topic is yieldbot/crypto-related
    if "crypto" in topic.lower() or "bitcoin" in topic.lower() or "yieldbot" in topic.lower():
        try:
            from src.agent.tools.crypto_tools import fetch_quality_tokens, CMC_AVAILABLE
            if CMC_AVAILABLE:
                data = fetch_quality_tokens(top_n=3)
                if data.get("success") and (data["gainers"] or data["losers"]):
                    parts.append("")
                    if data["gainers"]:
                        syms = " | ".join(
                            f"${t.get('symbol', '?').upper()} +{t.get('change_24h', 0):.1f}%"
                            for t in data["gainers"][:3]
                        )
                        parts.append(f"📈 {syms}")
                    crypto_analysis = {
                        "best_gainers": data["gainers"],
                        "best_losers": data["losers"],
                    }
        except Exception as e:
            logger.debug("Crypto enrichment skipped: %s", e)

    msg = "\n".join(parts)
    logger.info("Telegram briefing: %d chars, topic=%s", len(msg), topic)
    return {"message": msg, "crypto_analysis": crypto_analysis}
