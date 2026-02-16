"""Research Agent — fetches trending topics and market data.

Uses search_tools to call SERPAPI/Tavily/Firecrawl and returns clean trend insights.
Also scrapes FDWA sites periodically for fresh product/service data.
"""

import logging

from src.agent.tools.search_tools import search_trends

logger = logging.getLogger(__name__)


def research_trends() -> dict:
    """Run trend research. Returns dict with 'trend_data' and 'source'."""
    logger.info("--- RESEARCH AGENT: Fetching trends ---")
    result = search_trends()

    # Enrich with live FDWA site data when Firecrawl is available
    try:
        from src.agent.tools.web_tools import scrape_url
        site = scrape_url("https://fdwa.site")
        if "error" not in site and site.get("markdown"):
            snippet = site["markdown"][:500]
            result["trend_data"] += f"\n\nFDWA latest (fdwa.site):\n{snippet}"
            logger.info("Enriched with live fdwa.site data (%d chars)", len(snippet))
    except Exception as e:
        logger.debug("FDWA site scrape skipped: %s", e)

    logger.info("Research complete — source=%s, length=%d",
                result.get("source", "?"), len(result.get("trend_data", "")))
    return result
