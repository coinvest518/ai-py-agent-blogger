"""Research Agent — fetches trending topics and market data.

Uses search_tools to call SERPAPI/Tavily and returns clean trend insights.
"""

import logging

from src.agent.tools.search_tools import search_trends

logger = logging.getLogger(__name__)


def research_trends() -> dict:
    """Run trend research. Returns dict with 'trend_data' and 'source'."""
    logger.info("--- RESEARCH AGENT: Fetching trends ---")
    result = search_trends()
    logger.info("Research complete — source=%s, length=%d",
                result.get("source", "?"), len(result.get("trend_data", "")))
    return result
