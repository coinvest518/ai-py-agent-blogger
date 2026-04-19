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
# Firecrawl + Hyperbrowser clients (lazy singleton)
# ---------------------------------------------------------------------------
_firecrawl_client = None
_hyperbrowser_client = None


def _get_firecrawl():
    """Return a Firecrawl client, or None if key not set."""
    global _firecrawl_client
    if _firecrawl_client is not None:
        return _firecrawl_client

    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        logger.debug("FIRECRAWL_API_KEY not set — scraping disabled")
        return None

    try:
        from firecrawl import Firecrawl
        _firecrawl_client = Firecrawl(api_key=api_key)
        logger.info("✅ Firecrawl client initialized")
        return _firecrawl_client
    except Exception as e:
        logger.warning("Firecrawl init failed: %s", e)
        return None


def _get_hyperbrowser():
    """Return a Hyperbrowser client, or None if key not set."""
    global _hyperbrowser_client
    if _hyperbrowser_client is not None:
        return _hyperbrowser_client

    api_key = os.getenv("HYPERBROWSER_API_KEY")
    if not api_key:
        logger.debug("HYPERBROWSER_API_KEY not set — hyperbrowser disabled")
        return None

    try:
        from hyperbrowser.client.sync import Hyperbrowser

        kwargs = {"api_key": api_key}
        base_url = os.getenv("HYPERBROWSER_BASE_URL")
        if base_url:
            kwargs["base_url"] = base_url

        _hyperbrowser_client = Hyperbrowser(**kwargs)
        logger.info("✅ Hyperbrowser client initialized")
        return _hyperbrowser_client
    except Exception as e:
        logger.warning("Hyperbrowser init failed: %s", e)
        return None


def _normalize_hyperbrowser_fetch(result: Any) -> dict[str, Any]:
    if getattr(result, "status", None) and result.status != "completed":
        return {"error": f"Hyperbrowser fetch status={result.status}"}

    data = getattr(result, "data", None) or result
    markdown = getattr(data, "markdown", None) or getattr(data, "html", None) or ""
    metadata = getattr(data, "metadata", None) or {}
    title = getattr(metadata, "title", "") if not isinstance(metadata, dict) else metadata.get("title", "")
    description = getattr(metadata, "description", "") if not isinstance(metadata, dict) else metadata.get("description", "")
    return {
        "markdown": markdown,
        "title": title or "",
        "description": description or "",
        "url": getattr(data, "url", "") or "",
    }


def _normalize_hyperbrowser_search(result: Any) -> list[dict]:
    if getattr(result, "status", None) != "completed":
        logger.warning("Hyperbrowser search returned status=%s", getattr(result, "status", None))
        return []

    data = getattr(result, "data", None)
    if not data:
        return []

    results = getattr(data, "results", []) or []
    out: list[dict] = []
    for item in results:
        if hasattr(item, "url"):
            out.append({
                "url": item.url,
                "title": getattr(item, "title", ""),
                "description": getattr(item, "description", ""),
            })
        elif isinstance(item, dict):
            out.append({
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "description": item.get("description", ""),
            })
    return out


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def scrape_url(url: str, formats: list[str] | None = None) -> dict[str, Any]:
    """Scrape a single URL and return its content.

    Returns dict with 'markdown', 'title', 'description', 'url', or 'error'.
    """
    fc = _get_firecrawl()
    if fc:
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

    hb = _get_hyperbrowser()
    if hb:
        try:
            from hyperbrowser.models.web.fetch import FetchParams
            from hyperbrowser.models.web.common import FetchOutputOptions, FetchOutputMarkdown

            params = FetchParams(
                url=url,
                outputs=FetchOutputOptions(
                    formats=[FetchOutputMarkdown(type="markdown")],
                ),
            )
            result = hb.web.fetch(params)
            normalized = _normalize_hyperbrowser_fetch(result)
            if normalized.get("markdown"):
                logger.info("Hyperbrowser scraped %s — %d chars", url, len(normalized["markdown"]))
                return normalized
            return {"error": normalized.get("error", "Hyperbrowser returned no content"), "url": url}
        except Exception as e:
            logger.warning("Hyperbrowser scrape failed for %s: %s", url, e)

    return {"error": "Scrape failed: Firecrawl and Hyperbrowser unavailable or returned no content", "url": url}


def search_web(query: str, limit: int = 5) -> list[dict]:
    """Search the web via Firecrawl and return results.

    Returns list of dicts with 'url', 'title', 'description'.
    Falls back to Hyperbrowser on error or when Firecrawl is unavailable.
    """
    fc = _get_firecrawl()
    if fc:
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
            if out:
                return out
        except Exception as e:
            logger.warning("Firecrawl search failed: %s", e)

    hb = _get_hyperbrowser()
    if not hb:
        return []

    try:
        from hyperbrowser.models.web.search import WebSearchParams

        params = WebSearchParams(query=query, page=1)
        response = hb.web.search(params)
        results = _normalize_hyperbrowser_search(response)
        logger.info("Hyperbrowser search '%s' — %d results", query[:40], len(results))
        return results[:limit]
    except Exception as e:
        logger.warning("Hyperbrowser search failed: %s", e)
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
