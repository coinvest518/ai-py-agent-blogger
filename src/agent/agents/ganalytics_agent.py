"""Google Analytics 4 subagent — surfaces real traffic data into the graph.

Uses Composio GOOGLE_ANALYTICS toolkit via entity_id auto-resolve.

Env:
  GA_PROPERTY_ID — e.g. `properties/123456789`. If unset, every call is a
    graceful skip (not a failure) so the graph keeps flowing.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _entity() -> Optional[str]:
    return os.getenv("COMPOSIO_ENTITY_ID") or os.getenv("COMPOSIO_USER_ID")


def _property_id() -> Optional[str]:
    pid = os.getenv("GA_PROPERTY_ID")
    if pid and not pid.startswith("properties/"):
        pid = f"properties/{pid}"
    return pid


def _run_report(dimensions: List[Dict[str, str]], metrics: List[Dict[str, str]],
                start: str = "yesterday", end: str = "today",
                limit: Optional[int] = None,
                order_by_metric: Optional[str] = None) -> Dict[str, Any]:
    entity = _entity()
    pid = _property_id()
    if not entity or not pid:
        return {"skipped": True, "reason": "GA_PROPERTY_ID or COMPOSIO_ENTITY_ID not set"}
    args: Dict[str, Any] = {
        "property": pid,
        "dateRanges": [{"startDate": start, "endDate": end}],
        "dimensions": dimensions,
        "metrics": metrics,
    }
    if limit:
        args["limit"] = limit
    if order_by_metric:
        args["orderBys"] = [{"metric": {"metricName": order_by_metric}, "desc": True}]
    try:
        from src.agent.tools.composio_tools import get_composio_client, _execute_with_fallback
        client = get_composio_client()
        resp = _execute_with_fallback("GOOGLE_ANALYTICS_RUN_REPORT", args, entity)
        if not resp.get("successful"):
            return {"success": False, "error": resp.get("error", "Unknown")}
        return {"success": True, "data": resp.get("data", {})}
    except Exception as e:
        logger.exception("GA run_report failed: %s", e)
        return {"success": False, "error": str(e)}


def daily_traffic() -> Dict[str, Any]:
    """Sessions / users / pageviews for yesterday→today."""
    return _run_report(
        dimensions=[{"name": "pagePath"}, {"name": "sessionSource"}],
        metrics=[{"name": "activeUsers"}, {"name": "sessions"}, {"name": "screenPageViews"}],
        start="yesterday",
        end="today",
    )


def top_pages_7d(limit: int = 10) -> Dict[str, Any]:
    """Top N pages by pageviews over the last 7 days."""
    return _run_report(
        dimensions=[{"name": "pagePath"}],
        metrics=[{"name": "screenPageViews"}, {"name": "engagementRate"}],
        start="7daysAgo",
        end="today",
        limit=limit,
        order_by_metric="screenPageViews",
    )


def summary() -> Dict[str, Any]:
    """One-shot summary combining daily + top-pages for the final report agent."""
    pid = _property_id()
    if not pid:
        return {"skipped": True, "reason": "GA_PROPERTY_ID not set"}
    return {
        "property_id": pid,
        "daily": daily_traffic(),
        "top_pages_7d": top_pages_7d(10),
    }


def run(state: dict) -> dict:
    """Graph entry — writes GA snapshot into state for downstream agents."""
    snap = summary()
    return {"ga_snapshot": snap}
