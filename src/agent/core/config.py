"""Centralized configuration for FDWA AI Agent.

All platform limits, site routing, environment variable lookups, and
constants live here so agents and tools never hardcode values.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# Directory paths
# =============================================================================
BASE_DIR = Path(__file__).parent.parent.parent.parent  # ai-agent/
SRC_DIR = BASE_DIR / "src"
AGENT_DIR = SRC_DIR / "agent"

# Knowledge / data files
BUSINESS_PROFILE_PATH = BASE_DIR / "business_profile.json"
KNOWLEDGE_BASE_PATH = BASE_DIR / "FDWA_KNOWLEDGE_BASE.md"
PRODUCTS_CATALOG_PATH = BASE_DIR / "FDWA_PRODUCTS_CATALOG.md"
LINKEDIN_BRAIN_PATH = BASE_DIR / "LINKEDIN_CONTENT_BRAIN.md"
MEMORY_PATH = BASE_DIR / "agent_memory.json"
SENT_POSTS_FILE = BASE_DIR / "sent_blog_posts.json"
SOCIAL_POSTS_FILE = BASE_DIR / "social_media_history.json"
TREND_CACHE_FILE = BASE_DIR / "trend_cache.json"
TEMP_IMAGES_DIR = BASE_DIR / "temp_images"

# =============================================================================
# Platform character limits (hard enforced)
# =============================================================================
PLATFORM_LIMITS = {
    "twitter": 275,
    "facebook": 4000,
    "linkedin": 3000,  # LinkedIn API max = 3000 chars (optimal engagement: 600-1200)
    "instagram": 2000,
    "telegram": 4096,
    "telegram_caption": 1024,
    "blog": 800,  # Word target (effectively unlimited chars)
}

# =============================================================================
# Site routing — maps topic category → correct URL
# Post-pivot priority: AI agents / digital products > credit > crypto (side)
# =============================================================================
SITE_ROUTES = {
    # Primary brands (high priority)
    "openclaw": "https://futuristicwealth.gumroad.com",
    "ai_agent": "https://futuristicwealth.gumroad.com",
    "skill": "https://futuristicwealth.gumroad.com",
    "build": "https://futuristicwealth.gumroad.com",
    "tutorial": "https://futuristicwealth.gumroad.com",
    "ai_automation": "https://fdwa.site",
    "automation": "https://fdwa.site",
    # Credit (rebrand)
    "credit_repair": "https://reportdisputer.xyz",
    "dispute": "https://reportdisputer.xyz",
    "credit": "https://reportdisputer.xyz",
    "report": "https://reportdisputer.xyz",
    "credit_analyzer": "https://reportdisputer.xyz",
    "consumerai": "https://reportdisputer.xyz",
    # Side projects
    "real_estate": "https://ai-realestate-agents.vercel.app",
    "gmail_security": "https://clawhub.ai/coinvest518/secure-gmail",
    # Crypto (side sub-brand — deprioritized but kept)
    "crypto": "https://yieldbot.cc",
    "defi": "https://yieldbot.cc",
    "trading": "https://yieldbot.cc",
    # Default
    "general": "https://fdwa.site",
}

# Topic priority — higher number wins when multiple topics match
TOPIC_PRIORITY = {
    "openclaw": 100,
    "ai_agent_dev": 95,
    "ai_automation": 90,
    "credit_repair": 70,
    "real_estate": 60,
    "crypto": 30,  # deprioritized
    "general": 10,
}

DEFAULT_SITE = "https://fdwa.site"
CRYPTO_SITE = "https://yieldbot.cc"
CONSUMERAI_SITE = "https://reportdisputer.xyz"  # rebrand
GUMROAD_SITE = "https://futuristicwealth.gumroad.com"
REPORTDISPUTER_SITE = "https://reportdisputer.xyz"
REAL_ESTATE_SITE = "https://ai-realestate-agents.vercel.app"
CLAWHUB_GMAIL = "https://clawhub.ai/coinvest518/secure-gmail"

# Affiliate links (used by content agent for relevant CTA injection)
AFFILIATE_LINKS = {
    "publish0x": "https://www.publish0x.com?a=K9b69y37aE",
    "creditrepaircloud": "https://get.creditrepaircloud.com/naq3utx717o0",
    "public_stocks": "https://public.com/user-referral?referrer=Investor703044",
    "identityiq_securemax": "https://www.identityiq.com/sc-securemax.aspx?offercode=4312970S",
    "identityiq_securepreferred": "https://www.identityiq.com/securepreferred.aspx?offercode=4312970R",
    "identityiq_securemax_trial": "https://www.identityiq.com/sc-securemax.aspx?offercode=4312970Q",
    "helloskip_grants": "https://links.helloskip.com/s/c/R55N7e0g2ytcWJXR8sdTfqVewfpWuwsKFOKquabEfTNIAD629ngVb8TKWN37D5RMQzF-bD_26l3aRSkovwjdcQCO6RgqpW6XLbURQ6DeYgTHiBQoBT-DuMvGVfiM6iWaHTsR9LB8t9UuF6mf6vvyb3zqcbLdC_ohZQG0PNk6Z-4wV2QC4i97C4fupf3JmczxEktEo5dvFXb_0r9lOqlod2lMaAxHBXvAnARN8KXWAlF3RW_i-mDwMg2F786C4YQWm4as0ay6swlWmX3nOChkZ-RAhn5bWRBE5L-Q74YIbf4VWVt3MRwWAg_sPdSaFrtQ2gVc5MwDNoQYfGjsUnCs5-hkIc6UP2cpATo28ypYj2U_W85PltWbglqFE0oetKNKzS8AA2LaS-f3xBaByzGZkz1g30ghjMIjr_BcUhK1m_iceATjD8W05v-t6ruQYOmgiVA3VvPCUXIdiLVqAY806TgEsbwxun0ltayCz7X2Er-oHw0F/oeQ_JwkoWPfPCd56OWiwhrCGT9Wx-3ki/16",
}

# =============================================================================
# Composio account IDs (from .env)
# =============================================================================
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")
COMPOSIO_ENTITY_ID = os.getenv("COMPOSIO_ENTITY_ID") or os.getenv("COMPOSIO_USER_ID")
GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def _compose_account(name: str) -> str | None:
    """Accept both NAME_ACCOUNT_ID and COMPOSIO_NAME_ACCOUNT_ID env var forms."""
    return os.getenv(f"{name}_ACCOUNT_ID") or os.getenv(f"COMPOSIO_{name}_ACCOUNT_ID")


FACEBOOK_ACCOUNT_ID = _compose_account("FACEBOOK")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
LINKEDIN_ACCOUNT_ID = _compose_account("LINKEDIN")
LINKEDIN_AUTHOR_URN = os.getenv("LINKEDIN_AUTHOR_URN")
INSTAGRAM_ACCOUNT_ID = _compose_account("INSTAGRAM")
INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID") or os.getenv("INSTAGRAM_USER_NAME")
TELEGRAM_ACCOUNT_ID = _compose_account("TELEGRAM")
TELEGRAM_GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID") or os.getenv("TELEGRAM_AI_OWNER_CHAT_ID")
TELEGRAM_GROUP_USERNAME = os.getenv("TELEGRAM_GROUP_USERNAME")
TELEGRAM_ENTITY_ID = os.getenv("TELEGRAM_ENTITY_ID")
SERPAPI_ACCOUNT_ID = _compose_account("SERPAPI")
TAVILY_ACCOUNT_ID = _compose_account("TAVILY")
COINMARKETCAP_API_KEY = os.getenv("COINMARKETCAP_API_KEY")
GOOGLESHEETS_ACCOUNT_ID = _compose_account("GOOGLESHEETS")
GMAIL_ACCOUNT_ID = _compose_account("GMAIL")

# =============================================================================
# Topic detection helpers
# =============================================================================

def detect_topic(text: str) -> str:
    """Detect topic category from text content.

    Post-pivot ordering: openclaw > ai_agent_dev > ai_automation > credit > real_estate > crypto > general.
    Returns the highest-priority matching topic.
    """
    t = text.lower()
    matches = []
    if any(w in t for w in ["openclaw", "open claw", "open-claw", "claude skill", "mcp server"]):
        matches.append("openclaw")
    if any(w in t for w in ["build ai agent", "first ai agent", "build your first", "ai agent tutorial",
                              "how to build", "agent dev", "langchain", "langgraph", "composio"]):
        matches.append("ai_agent_dev")
    if any(w in t for w in ["ai", "automation", "agent", "workflow", "coding", "saas", "llm", "rag"]):
        matches.append("ai_automation")
    if any(w in t for w in ["credit", "score", "dispute", "repair", "fico", "debt", "report"]):
        matches.append("credit_repair")
    if any(w in t for w in ["real estate", "property", "mls", "rental", "investor"]):
        matches.append("real_estate")
    if any(w in t for w in ["crypto", "defi", "trading", "token", "blockchain", "bitcoin", "ethereum", "yieldbot"]):
        matches.append("crypto")

    if not matches:
        return "general"
    return max(matches, key=lambda m: TOPIC_PRIORITY.get(m, 0))


def get_site_for_topic(topic: str) -> str:
    """Get the correct website URL based on content topic."""
    topic_lower = topic.lower()
    # ConsumerAI check first
    if any(k in topic_lower for k in ["consumerai", "consumer ai", "credit analyzer"]):
        return CONSUMERAI_SITE
    for key, url in SITE_ROUTES.items():
        if key in topic_lower:
            return url
    return DEFAULT_SITE


def validate_account_ids() -> dict:
    """Check which credentials are configured. Composio auto-resolves by entity_id,
    so per-platform account IDs are no longer required."""
    ids = {
        "COMPOSIO_ENTITY_ID": COMPOSIO_ENTITY_ID,
        "FACEBOOK_PAGE_ID": FACEBOOK_PAGE_ID,
        "COINMARKETCAP_API_KEY": COINMARKETCAP_API_KEY,
    }
    return ids
