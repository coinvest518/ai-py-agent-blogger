"""Engagement Reader Agent — pulls yesterday's performance data from
Facebook, LinkedIn, Instagram, and Telegram so the research + supervisor
nodes can bias the next cycle toward what actually performed.

Writes a snapshot to Mem0 under `user_id="fdwa_agent"` with
`metadata={"kind":"engagement_snapshot"}` and caches the result in
`.engagement_cache.json` with a 6h TTL to respect Meta/LinkedIn rate limits.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.agent.tools import composio_tools as ct

logger = logging.getLogger(__name__)

CACHE_PATH = Path(os.getenv("ENGAGEMENT_CACHE_PATH", ".engagement_cache.json"))
HISTORY_PATH = Path("social_media_history.json")
CACHE_TTL_SECONDS = 6 * 3600


def _load_cache() -> dict | None:
    if not CACHE_PATH.exists():
        return None
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if time.time() - payload.get("_cached_at", 0) < CACHE_TTL_SECONDS:
            return payload
    except Exception as e:
        logger.warning("Engagement cache read failed: %s", e)
    return None


def _save_cache(payload: dict) -> None:
    try:
        payload = {**payload, "_cached_at": time.time()}
        CACHE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Engagement cache write failed: %s", e)


def _yesterdays_posts() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=36)
    picks: list[dict] = []
    for post in (data.get("posts") or []):
        ts = post.get("timestamp")
        if not ts:
            continue
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if t >= cutoff:
            picks.append(post)
    return picks


def _summarize(results: dict) -> str:
    parts = []
    for platform, payload in results.items():
        if platform.startswith("_"):
            continue
        if isinstance(payload, dict) and payload.get("_error"):
            parts.append(f"{platform}: (error) {payload['_error']}")
            continue
        parts.append(f"{platform}: {json.dumps(payload)[:220]}")
    return " | ".join(parts) or "no engagement data"


def read_yesterday(force: bool = False) -> dict:
    """Pull engagement for posts made in the last 36h across all 4 surfaces.

    Returns dict like:
        {"engagement": {...}, "summary": "...", "source": "cache|live"}
    """
    cached = None if force else _load_cache()
    if cached:
        logger.info("Engagement cache hit (age=%ds)", int(time.time() - cached.get("_cached_at", 0)))
        return {**cached, "source": "cache"}

    recent = _yesterdays_posts()
    results: dict[str, object] = {
        "facebook_insights": {},
        "facebook_posts": {},
        "linkedin": [],
        "instagram_insights": [],
        "instagram_comments": [],
        "telegram": {},
    }

    try:
        results["facebook_insights"] = ct.fetch_facebook_page_insights()
        results["facebook_posts"] = ct.fetch_facebook_recent_posts(limit=5)
    except Exception as e:
        results["facebook_insights"] = {"_error": str(e)}

    for post in recent:
        platform = (post.get("platform") or "").lower()
        pid = post.get("post_id")
        if not pid:
            continue
        if platform == "linkedin":
            results["linkedin"].append({"post_id": pid, "stats": ct.fetch_linkedin_post_stats(pid)})
        elif platform == "instagram":
            results["instagram_insights"].append({"media_id": pid, "insights": ct.fetch_instagram_media_insights(pid)})
            results["instagram_comments"].append({"media_id": pid, "comments": ct.fetch_instagram_media_comments(pid)})

    try:
        results["telegram"] = ct.fetch_telegram_recent_updates(limit=20)
    except Exception as e:
        results["telegram"] = {"_error": str(e)}

    summary = _summarize(results)
    payload = {"engagement": results, "summary": summary, "post_count": len(recent)}

    try:
        from src.agent.mem0_adapter import remember
        remember(
            content=f"engagement_snapshot: {summary[:800]}",
            user_id="fdwa_agent",
            metadata={"kind": "engagement_snapshot", "post_count": len(recent)},
        )
    except Exception as e:
        logger.warning("Mem0 engagement write failed: %s", e)

    _save_cache(payload)
    payload["source"] = "live"
    return payload


def run(state: dict) -> dict:
    """Graph node entry point — adds `engagement` to state."""
    logger.info("──── ENGAGEMENT READ ────")
    try:
        payload = read_yesterday()
        return {"engagement": payload.get("engagement"), "engagement_summary": payload.get("summary")}
    except Exception as e:
        logger.exception("Engagement read failed: %s", e)
        return {"engagement": None, "engagement_summary": f"error: {e}"}
