"""Shared FDWA knowledge base, identity, and system prompt.

Used by both the main LangGraph agent pipeline AND the /chat endpoint
so they share the same identity, knowledge, and tools awareness.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from src.agent.core.config import (
    BUSINESS_PROFILE_PATH,
    KNOWLEDGE_BASE_PATH,
    PRODUCTS_CATALOG_PATH,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cached knowledge context (loaded once per process)
# ---------------------------------------------------------------------------
_KNOWLEDGE_CACHE: str | None = None


def load_knowledge_context(force: bool = False) -> str:
    """Load FDWA knowledge base, business profile, and products catalog.

    Returns a combined string suitable for injection into any system prompt.
    Cached after first call unless *force* is True.
    """
    global _KNOWLEDGE_CACHE
    if _KNOWLEDGE_CACHE is not None and not force:
        return _KNOWLEDGE_CACHE

    parts: list[str] = []

    # 1) Knowledge base markdown
    try:
        if KNOWLEDGE_BASE_PATH.exists():
            kb = KNOWLEDGE_BASE_PATH.read_text(encoding="utf-8")
            parts.append(kb[:6000])
    except Exception:
        pass

    # 2) Business profile (JSON → readable bullets)
    try:
        if BUSINESS_PROFILE_PATH.exists():
            bp = json.loads(BUSINESS_PROFILE_PATH.read_text(encoding="utf-8"))
            products_str = "\n".join(
                f"- {p.get('title', '?')} (${p.get('price', 0)}) — {p.get('type', 'product')}"
                for p in bp.get("products", [])
            )
            parts.append(
                f"## Products\n{products_str}\n\n"
                f"Primary site: {bp.get('primary_site', 'https://fdwa.site')}\n"
                f"Shop: {bp.get('shop_page', '')}\n"
                f"Linktree: {bp.get('linktree', '')}"
            )
    except Exception:
        pass

    # 3) Products catalog markdown
    try:
        if PRODUCTS_CATALOG_PATH.exists():
            pc = PRODUCTS_CATALOG_PATH.read_text(encoding="utf-8")
            parts.append(pc[:4000])
    except Exception:
        pass

    context = "\n\n---\n\n".join(parts) if parts else "You are the FDWA AI assistant."
    _KNOWLEDGE_CACHE = context
    return _KNOWLEDGE_CACHE


# ---------------------------------------------------------------------------
# FDWA identity block  (shared across chat + content generation)
# ---------------------------------------------------------------------------

FDWA_IDENTITY = """IDENTITY:
- FDWA = Futurist Digital Wealth Agency (NOT Food & Drug / NOT government)
- Founded by Daniel Wray — "The Street Smart Entrepreneur"
- Core services: AI automation, credit repair, digital products, business automation
- Websites: fdwa.site (main), yieldbot.cc (crypto), consumerai.info (credit analyzer)
- Voice: Authoritative, data-driven, conversational, action-oriented"""


def build_system_prompt(
    *,
    purpose: str = "chat",
    extra_context: str = "",
) -> str:
    """Build a full system prompt for any FDWA agent or chat session.

    Args:
        purpose: 'chat' for the /chat endpoint,
                 'content' for the content generation pipeline,
                 or any custom label.
        extra_context: Additional context (scraped URLs, search results, etc.)
    """
    kb = load_knowledge_context()
    today = datetime.now().strftime("%B %d, %Y")

    prompt = f"""You are Daniel Wray's FDWA AI assistant — the main AI agent for Futurist Digital Wealth Agency.

{FDWA_IDENTITY}

TODAY: {today}

CAPABILITIES:
- Answer questions about FDWA's products, services, and strategies
- Scrape and analyze any URL using Firecrawl
- Search the web for real-time information (SERPAPI, Tavily, Firecrawl)
- Access conversation history and persistent memory (Astra DB)
- Full knowledge of FDWA's product catalog and business profile

RULES:
- Never use markdown formatting (no **bold**, no [links](url), no # headers)
- Use plain text with emojis for emphasis
- Be concise but thorough
- Always relate answers back to how FDWA can help when relevant
- For crypto topics, reference yieldbot.cc
- For credit repair, reference fdwa.site or consumerai.info
- For AI automation, reference fdwa.site

KNOWLEDGE BASE:
{kb}
"""

    if extra_context:
        prompt += f"\n\nADDITIONAL CONTEXT:\n{extra_context}"

    return prompt
