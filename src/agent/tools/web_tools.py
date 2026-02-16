"""Web tools — Firecrawl scraping, search, and URL extraction.

Provides scrape_url(), search_web(), and extract_urls() for the chat agent
and any other module that needs web data.
"""

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Firecrawl client (lazy singleton)
# ---------------------------------------------------------------------------
_firecrawl_client = None


def _get_firecrawl():
    """Return a Firecrawl client, or None if key not set."""
    global _firecrawl_client
    if _firecrawl_client is not None:
        return _firecrawl_client

    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        logger.warning("FIRECRAWL_API_KEY not set — scraping disabled")
        return None

    try:
        from firecrawl import Firecrawl
        _firecrawl_client = Firecrawl(api_key=api_key)
        logger.info("✅ Firecrawl client initialized")
        return _firecrawl_client
    except Exception as e:
        logger.warning("Firecrawl init failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def scrape_url(url: str, formats: list[str] | None = None) -> dict[str, Any]:
    """Scrape a single URL and return its content.

    Returns dict with 'markdown', 'title', 'description', 'url', or 'error'.
    """
    fc = _get_firecrawl()
    if not fc:
        return {"error": "Firecrawl not configured (FIRECRAWL_API_KEY missing)"}

    try:
        result = fc.scrape(url, formats=formats or ["markdown"])

        # The SDK returns a Document or dict — normalize
        if hasattr(result, "markdown"):
            md = result.markdown or ""
            meta = result.metadata if hasattr(result, "metadata") else {}
        elif isinstance(result, dict):
            data = result.get("data", result)
            md = data.get("markdown", "")
            meta = data.get("metadata", {})
        else:
            md = str(result)
            meta = {}

        # Handle metadata that might be an object or dict
        if hasattr(meta, "title"):
            title = meta.title
            desc = getattr(meta, "description", "")
        elif isinstance(meta, dict):
            title = meta.get("title", "")
            desc = meta.get("description", "")
        else:
            title = ""
            desc = ""

        # Truncate very long pages to keep LLM context reasonable
        if len(md) > 8000:
            md = md[:8000] + "\n\n[... content truncated for brevity ...]"

        logger.info("Scraped %s — %d chars, title=%s", url, len(md), title[:60] if title else "?")
        return {
            "markdown": md,
            "title": title,
            "description": desc,
            "url": url,
        }
    except Exception as e:
        logger.warning("Firecrawl scrape failed for %s: %s", url, e)
        return {"error": f"Scrape failed: {e}", "url": url}


def search_web(query: str, limit: int = 5) -> list[dict]:
    """Search the web via Firecrawl and return results.

    Returns list of dicts with 'url', 'title', 'description'.
    Falls back to empty list on error.
    """
    fc = _get_firecrawl()
    if not fc:
        return []

    try:
        results = fc.search(query, limit=limit)

        # Normalize response
        if hasattr(results, "data"):
            raw = results.data
        elif isinstance(results, dict):
            raw = results.get("data", results)
        else:
            raw = results

        # Handle nested web/images/news structure
        if isinstance(raw, dict) and "web" in raw:
            items = raw["web"]
        elif isinstance(raw, list):
            items = raw
        else:
            items = []

        out = []
        for item in items[:limit]:
            if hasattr(item, "url"):
                out.append({"url": item.url, "title": getattr(item, "title", ""), "description": getattr(item, "description", "")})
            elif isinstance(item, dict):
                out.append({"url": item.get("url", ""), "title": item.get("title", ""), "description": item.get("description", "")})

        logger.info("Firecrawl search '%s' — %d results", query[:40], len(out))
        return out
    except Exception as e:
        logger.warning("Firecrawl search failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# URL detection helper
# ---------------------------------------------------------------------------

_URL_RE = re.compile(
    r"https?://[^\s<>\"'\)\]\},;]+",
    re.IGNORECASE,
)


def extract_urls(text: str) -> list[str]:
    """Extract HTTP/HTTPS URLs from text."""
    return _URL_RE.findall(text)
