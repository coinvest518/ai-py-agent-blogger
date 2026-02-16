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
# =============================================================================
SITE_ROUTES = {
    "crypto": "https://yieldbot.cc",
    "defi": "https://yieldbot.cc",
    "trading": "https://yieldbot.cc",
    "consumerai": "https://consumerai.info",
    "credit_analyzer": "https://consumerai.info",
    "credit_repair": "https://fdwa.site",
    "ai_automation": "https://fdwa.site",
    "general": "https://fdwa.site",
}

DEFAULT_SITE = "https://fdwa.site"
CRYPTO_SITE = "https://yieldbot.cc"
CONSUMERAI_SITE = "https://consumerai.info"

# =============================================================================
# Composio account IDs (from .env)
# =============================================================================
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")
TWITTER_ACCOUNT_ID = os.getenv("TWITTER_ACCOUNT_ID")
FACEBOOK_ACCOUNT_ID = os.getenv("FACEBOOK_ACCOUNT_ID")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
LINKEDIN_ACCOUNT_ID = os.getenv("LINKEDIN_ACCOUNT_ID")
LINKEDIN_AUTHOR_URN = os.getenv("LINKEDIN_AUTHOR_URN")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")
INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID")
TELEGRAM_ACCOUNT_ID = os.getenv("TELEGRAM_ACCOUNT_ID")
TELEGRAM_GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID")
TELEGRAM_GROUP_USERNAME = os.getenv("TELEGRAM_GROUP_USERNAME")
TELEGRAM_ENTITY_ID = os.getenv("TELEGRAM_ENTITY_ID")
SERPAPI_ACCOUNT_ID = os.getenv("SERPAPI_ACCOUNT_ID")
TAVILY_ACCOUNT_ID = os.getenv("TAVILY_ACCOUNT_ID")
COINMARKETCAP_API_KEY = os.getenv("COINMARKETCAP_API_KEY")
GOOGLESHEETS_ACCOUNT_ID = os.getenv("GOOGLESHEETS_ACCOUNT_ID")
GMAIL_ACCOUNT_ID = os.getenv("GMAIL_ACCOUNT_ID")

# =============================================================================
# Topic detection helpers
# =============================================================================

def detect_topic(text: str) -> str:
    """Detect topic category from text content.
    
    Returns: 'crypto', 'credit_repair', 'ai_automation', or 'general'
    """
    t = text.lower()
    if any(w in t for w in ["crypto", "defi", "trading", "token", "blockchain", "bitcoin", "ethereum", "yieldbot"]):
        return "crypto"
    if any(w in t for w in ["credit", "score", "dispute", "repair", "fico", "debt"]):
        return "credit_repair"
    if any(w in t for w in ["ai", "automation", "agent", "workflow", "coding", "saas"]):
        return "ai_automation"
    return "general"


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
    """Check which account IDs are configured. Returns {name: id_or_None}."""
    ids = {
        "TWITTER_ACCOUNT_ID": TWITTER_ACCOUNT_ID,
        "FACEBOOK_ACCOUNT_ID": FACEBOOK_ACCOUNT_ID,
        "FACEBOOK_PAGE_ID": FACEBOOK_PAGE_ID,
        "LINKEDIN_ACCOUNT_ID": LINKEDIN_ACCOUNT_ID,
        "INSTAGRAM_ACCOUNT_ID": INSTAGRAM_ACCOUNT_ID,
        "TELEGRAM_ACCOUNT_ID": TELEGRAM_ACCOUNT_ID,
        "SERPAPI_ACCOUNT_ID": SERPAPI_ACCOUNT_ID,
        "COINMARKETCAP_API_KEY": COINMARKETCAP_API_KEY,
    }
    return ids
