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

    prompt = f"""Current year: {year}. Create a Twitter post based on this insight:

{insights[:300]}
{memory_hint}
HARD RULES:
- MAXIMUM 250 characters (leave room for link)
- Plain text only — NO Markdown
- Use {year} for dates
- Include 1-2 relevant emojis
- 1-2 hashtags max: #YBOT #AIAutomation
- Be engaging and actionable
- Do NOT include any URL — the system appends one automatically

Output ONLY the tweet text."""

    tweet = _llm_generate(prompt, "Twitter content")
    if not tweet:
        first = insights.split("\n")[0][:100]
        tweet = f"🚀 {first}\n\n#YBOT #AIAutomation"

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

    prompt = f"""Create a Facebook post based on this insight:

{insights[:500]}

Requirements:
- Conversational, community-focused tone
- 400-600 characters
- Plain text only (NO Markdown)
- Relevant emojis
- Mention FDWA services naturally
- CTA: {site}
- 3-4 hashtags: #AIAutomation #BusinessGrowth #FinancialFreedom
- Value-driven and engaging

Output ONLY the Facebook post text."""

    post = _llm_generate(prompt, "Facebook content")
    if not post:
        first = insights.split("\n")[0][:150]
        post = (
            f"💡 {first}\n\n"
            f"AI automation is changing everything for small businesses.\n\n"
            f"Learn more: {site}\n\n"
            f"#AIAutomation #BusinessGrowth"
        )

    if site not in post:
        post += f"\n\nLearn more: {site}"

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

    prompt = f"""You are Daniel Wray, founder of FDWA — an AI automation agency.
Write a LinkedIn post for {year}.

Context/insight:
{insights[:400]}
{product_lines}
{formula}
{memory_hint}
LINKEDIN RULES:
- 600-1200 characters MAXIMUM (sweet spot for engagement — LinkedIn hard limit is 3000)
- NEVER exceed 1200 characters — shorter performs better
- Write as a FOUNDER sharing updates about tools you built, results for clients
- Start with a data-driven hook or personal story
- Include specific metrics or ROI outcomes when possible
- Use ✅ bullet points for readability
- Professional but conversational tone ("street smart entrepreneur")
- Plain text only (NO Markdown)
- 3-5 hashtags max at the end
- CTA: {site}
- Topic focus: {topic}

THIS IS NOT a generic AI article — it's YOUR thought leadership as a builder.

Output ONLY the LinkedIn post text."""

    post = _llm_generate(prompt, "LinkedIn content")
    if not post:
        first = insights.split("\n")[0][:120]
        post = (
            f"📊 {first}\n\n"
            f"We're building AI automation tools that help SMBs save 20+ hours/week.\n\n"
            f"✅ AI Stack Map — free workflow automation guide\n"
            f"✅ ConsumerAI — credit report analyzer\n"
            f"✅ Custom AI agents for any business need\n\n"
            f"Learn more: {site}\n\n"
            f"#AI #Automation #SmallBusiness #Entrepreneur"
        )

    if site not in post:
        post += f"\n\nLearn more: {site}"

    limit = PLATFORM_LIMITS["linkedin"]
    if len(post) > limit:
        post = post[:limit - 3] + "..."
    logger.info("LinkedIn: %d chars", len(post))
    return post


def generate_instagram(insights: str, strategy: dict | None = None) -> str:
    """Generate Instagram caption — visual-first, emoji-heavy, 400-600 chars."""
    year = datetime.now().year
    topic = (strategy or {}).get("topic", "general")

    prompt = f"""Current year: {year}. Create an Instagram caption:

{insights[:400]}

Requirements:
- Visual-first, lifestyle-focused, aspirational
- 400-600 characters
- Plain text only (NO Markdown)
- Emoji-heavy (but tasteful)
- Entrepreneurship / financial freedom angle
- Mention link in bio
- Hashtags: #AIAutomation #FinancialFreedom #Entrepreneur #PassiveIncome
- NO URLs in caption (Instagram doesn't allow clickable links)

Output ONLY the Instagram caption."""

    caption = _llm_generate(prompt, "Instagram content")
    if not caption:
        first = insights.split("\n")[0][:80]
        caption = (
            f"✨ {first}\n\n"
            f"🤖 AI automation isn't just for tech companies anymore\n"
            f"💎 It's for entrepreneurs who want freedom\n"
            f"🚀 It's for businesses ready to scale\n\n"
            f"🔗 Link in bio\n\n"
            f"#AIAutomation #FinancialFreedom #Entrepreneur #PassiveIncome"
        )

    limit = PLATFORM_LIMITS["instagram"]
    if len(caption) > limit:
        caption = caption[:limit - 3] + "..."
    logger.info("Instagram: %d chars", len(caption))
    return caption


def generate_telegram(insights: str, strategy: dict | None = None) -> dict:
    """Generate Telegram message — crypto token data ONLY.

    ✅ FIX: Telegram = crypto symbols + percentages. NO images, NO generic business.
    Uses CoinMarketCap data, not LLM generation.

    Returns dict with:
      - message: str (the Telegram text)
      - crypto_analysis: dict (gainers/losers for memory persistence)
    """
    from src.agent.tools.crypto_tools import fetch_quality_tokens, CMC_AVAILABLE

    if not CMC_AVAILABLE:
        logger.warning("CMC not available — sending minimal crypto update")
        return {"message": _telegram_minimal_update(), "crypto_analysis": {}}

    data = fetch_quality_tokens(top_n=5)
    if not data.get("success") or (not data["gainers"] and not data["losers"]):
        logger.warning("No quality tokens found — sending minimal crypto update")
        return {"message": _telegram_minimal_update(), "crypto_analysis": {}}

    parts = []

    # Gainers
    if data["gainers"]:
        parts.append("📈 Top Gainers (24h):")
        symbols = []
        for t in data["gainers"][:5]:
            sym = t.get("symbol", "?").upper()
            chg = t.get("change_24h", 0)
            symbols.append(f"${sym} +{chg:.1f}%")
        parts.append(" | ".join(symbols))
        parts.append("")

    # Losers
    if data["losers"]:
        parts.append("📉 Top Losers (24h):")
        symbols = []
        for t in data["losers"][:5]:
            sym = t.get("symbol", "?").upper()
            chg = t.get("change_24h", 0)
            symbols.append(f"${sym} {chg:.1f}%")
        parts.append(" | ".join(symbols))
        parts.append("")

    parts.append("💡 Learn more: https://yieldbot.cc")

    msg = "\n".join(parts)
    logger.info("Telegram: %d chars, %d gainers, %d losers",
                len(msg), len(data["gainers"]), len(data["losers"]))

    # Return both message and raw crypto data for memory persistence
    crypto_analysis = {
        "best_gainers": data["gainers"],
        "best_losers": data["losers"],
    }
    return {"message": msg, "crypto_analysis": crypto_analysis}


def _telegram_minimal_update() -> str:
    """Graceful fallback when CMC data is unavailable — NO admin debug messages."""
    return (
        "📊 Crypto Market Update\n\n"
        "Market data is being refreshed. "
        "Check back shortly for live token analysis.\n\n"
        "💡 Learn more: https://yieldbot.cc\n\n"
        "#DeFi #Crypto #YieldBot"
    )
