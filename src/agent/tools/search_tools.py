"""Search tools — SERPAPI and Tavily wrappers.

Used by the research agent to fetch trending topics.
"""

import json
import logging
import os
import random
from datetime import datetime

from src.agent.core.config import SERPAPI_ACCOUNT_ID, TAVILY_ACCOUNT_ID, TREND_CACHE_FILE
from src.agent.tools.composio_tools import get_composio_client

logger = logging.getLogger(__name__)

# Diverse search queries across business verticals
SEARCH_QUERIES = [
    "credit repair tips {year}",
    "AI automation for credit repair",
    "digital products for financial freedom",
    "AI dispute letter generators",
    "passive income with ebooks",
    "credit score improvement hacks",
    "AI tools for business automation",
    "how to sell digital products online",
    "financial empowerment strategies",
    "credit repair laws and updates {year}",
    "AI credit report analyzers",
    "building wealth with digital tools",
    "credit denial solutions",
    "automate business workflows with AI",
    "create and sell step-by-step guides",
    "financial education for entrepreneurs",
    "credit repair digital products",
    "AI for passive income streams",
    "modern wealth building techniques {year}",
    "credit repair automation tools",
]


def search_trends() -> dict:
    """Search for trending topics using SERPAPI (primary) → Tavily (fallback) → cache.

    Returns:
        dict with 'trend_data' (str) and 'source' (str), or 'error'.
    """
    current_year = datetime.now().year
    query = random.choice(SEARCH_QUERIES).format(year=current_year)
    logger.info("Researching: %s", query)

    client = get_composio_client()
    today = datetime.now().strftime("%Y-%m-%d")

    # 1) SERPAPI
    if SERPAPI_ACCOUNT_ID:
        try:
            resp = client.tools.execute(
                "SERPAPI_SEARCH", {"query": query},
                connected_account_id=SERPAPI_ACCOUNT_ID,
            )
            data = resp.get("data", {})
            text = _extract_search_insights(data)
            if text and len(text) > 30:
                logger.info("SERPAPI success: %d chars", len(text))
                return {"trend_data": text, "source": "SERPAPI"}
        except Exception as e:
            logger.warning("SERPAPI failed: %s", e)

    # 2) Tavily (with daily cache)
    cache = _load_cache()
    if cache.get("date") == today and cache.get("trend_data"):
        logger.info("Using cached Tavily data")
        return {"trend_data": cache["trend_data"], "source": "Tavily (cached)"}

    if TAVILY_ACCOUNT_ID:
        try:
            resp = client.tools.execute(
                "TAVILY_SEARCH",
                {
                    "query": query,
                    "max_results": 10,
                    "search_depth": "advanced",
                    "include_answer": True,
                    "include_raw_content": True,
                    "exclude_domains": ["pinterest.com", "facebook.com", "instagram.com", "twitter.com", "tiktok.com"],
                },
                connected_account_id=TAVILY_ACCOUNT_ID,
            )
            data = resp.get("data", {})
            text = _extract_search_insights(data)
            if text and len(text) > 30:
                _save_cache({"date": today, "trend_data": text})
                logger.info("Tavily success: %d chars", len(text))
                return {"trend_data": text, "source": "Tavily"}
        except Exception as e:
            logger.warning("Tavily failed: %s", e)

    # 3) Fallback
    fallback = (
        "AI automation is transforming business operations. "
        "Smart entrepreneurs are using AI agents to scale their businesses, "
        "automate customer service, and build passive income streams. "
        "Financial empowerment through technology is now accessible to everyone."
    )
    return {"trend_data": fallback, "source": "fallback"}


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_cache() -> dict:
    try:
        if TREND_CACHE_FILE.exists():
            return json.loads(TREND_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_cache(data: dict):
    try:
        TREND_CACHE_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Search result extraction (supports both SERPAPI and Tavily nested structures)
# ---------------------------------------------------------------------------

def _extract_search_insights(search_data: dict) -> str:
    """Extract readable text from raw search API responses."""
    insights = []

    # SERPAPI organic results
    for path in [["results", "organic_results"], ["organic_results"], ["data", "organic_results"]]:
        node = _walk(search_data, path)
        if isinstance(node, list) and node:
            for r in node[:5]:
                if isinstance(r, dict):
                    t = r.get("title", "")
                    s = r.get("snippet", "")
                    if t and len(t) > 10:
                        insights.append(f"📰 {t}")
                    if s and len(s) > 20:
                        insights.append(f"   💡 {s[:150]}")
            break

    # Tavily results
    for path in [["response_data", "results"], ["results"], ["data", "results"]]:
        node = _walk(search_data, path)
        if isinstance(node, list) and node:
            for r in node[:5]:
                if isinstance(r, dict):
                    t = r.get("title", "")
                    c = r.get("content", "")
                    if t and len(t) > 10:
                        insights.append(f"🔍 {t}")
                    if c and len(c) > 20:
                        insights.append(f"   📝 {c[:150]}")
            break

    # Tavily answer
    for path in [["response_data", "answer"], ["answer"]]:
        node = _walk(search_data, path)
        if isinstance(node, str) and len(node) > 20:
            insights.insert(0, f"🎯 {node[:200]}")
            break

    # Deep fallback — grab any text-like values
    if not insights:
        for txt in _extract_text_recursive(search_data):
            insights.append(f"📄 {txt}")
            if len(insights) >= 3:
                break

    text = "\n".join(insights)
    return text[:1000] if text else ""


def _walk(obj, keys):
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            obj = obj[k]
        else:
            return None
    return obj


def _extract_text_recursive(obj, depth=0):
    if depth > 3:
        return []
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and len(v) > 30 and k in ("title", "snippet", "content", "description", "text"):
                found.append(v[:150])
            elif isinstance(v, (dict, list)):
                found.extend(_extract_text_recursive(v, depth + 1))
    elif isinstance(obj, list):
        for item in obj[:3]:
            found.extend(_extract_text_recursive(item, depth + 1))
    return found
