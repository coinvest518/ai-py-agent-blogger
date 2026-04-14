"""Analytics Agent — daily rollup of post performance, products, frameworks.

Aggregates from `social_media_history.json` (and current run state) into a
rolling local store `agent_analytics_daily.json`, and best-effort syncs the
day's row to a "Daily Analytics" tab in the posts spreadsheet.

Schema per day:
  {
    "date": "2026-04-11",
    "posts_per_platform": {twitter: N, facebook: N, ...},
    "products_promoted": {product_name: count, ...},
    "frameworks_tagged": {LangChain: count, ...},
    "topics": {openclaw: count, ...},
    "errors": int,
    "runs": int,
  }
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parent.parent.parent.parent
_HISTORY_PATH = _BASE / "social_media_history.json"
_ANALYTICS_PATH = _BASE / "agent_analytics_daily.json"


def _load_json(path: Path, default):
    try:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Could not read %s: %s", path.name, e)
    return default


def _save_json(path: Path, data) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except OSError as e:
        logger.error("Could not write %s: %s", path.name, e)


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _aggregate_today() -> Dict:
    """Build today's rollup from social_media_history.json."""
    history = _load_json(_HISTORY_PATH, [])
    entries = history if isinstance(history, list) else history.get("posts", [])
    today = _today_iso()

    posts_per_platform: Dict[str, int] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        ts = str(entry.get("timestamp") or entry.get("posted_at") or "")
        if not ts.startswith(today):
            continue
        plat = (entry.get("platform") or "unknown").lower()
        posts_per_platform[plat] = posts_per_platform.get(plat, 0) + 1

    return {
        "date": today,
        "posts_per_platform": posts_per_platform,
        "products_promoted": {},
        "frameworks_tagged": {},
        "topics": {},
        "errors": 0,
        "runs": 0,
    }


def _merge_run_state(rollup: Dict, state: dict) -> Dict:
    """Layer this run's strategy + statuses onto the day's rollup."""
    rollup["runs"] = rollup.get("runs", 0) + 1

    strategy = state.get("ai_strategy") or {}
    topic = strategy.get("topic", "")
    if topic:
        rollup["topics"][topic] = rollup["topics"].get(topic, 0) + 1

    angle = strategy.get("monetization_angle") or {}
    for slot in ("free_guide", "paid_skill"):
        prod = angle.get(slot)
        if prod and prod.get("name"):
            n = prod["name"]
            rollup["products_promoted"][n] = rollup["products_promoted"].get(n, 0) + 1
    for fw in angle.get("framework_used", []) or []:
        rollup["frameworks_tagged"][fw] = rollup["frameworks_tagged"].get(fw, 0) + 1

    for key in ("twitter_url", "facebook_status", "linkedin_status",
                "instagram_status", "telegram_status"):
        val = str(state.get(key, "") or "").lower()
        if "fail" in val or "error" in val:
            rollup["errors"] = rollup.get("errors", 0) + 1

    return rollup


def _best_effort_sheets_sync(rollup: Dict) -> bool:
    """Append today's row to a Daily Analytics tab. Skips silently on failure."""
    sheet_id = os.getenv("GOOGLESHEETS_POSTS_SPREADSHEET_ID")
    if not sheet_id:
        return False
    try:
        from src.agent.sheets_agent import sheets_agent
        row = [
            rollup["date"],
            json.dumps(rollup["posts_per_platform"]),
            json.dumps(rollup["products_promoted"]),
            json.dumps(rollup["frameworks_tagged"]),
            json.dumps(rollup["topics"]),
            rollup["errors"],
            rollup["runs"],
            datetime.now(timezone.utc).isoformat(),
        ]
        resp = sheets_agent._execute_tool(
            "GOOGLESHEETS_BATCH_UPDATE",
            {
                "spreadsheet_id": sheet_id,
                "sheet_name": "Daily Analytics",
                "values": [row],
                "first_cell_location": "A2",
            },
        )
        return bool(resp.get("successful"))
    except Exception as e:
        logger.debug("Sheets analytics sync skipped: %s", e)
        return False


def run(state: dict) -> dict:
    """Build today's rollup from history + this run's state, persist locally + sheets."""
    logger.info("--- ANALYTICS AGENT ---")
    today = _today_iso()
    store = _load_json(_ANALYTICS_PATH, {})
    if not isinstance(store, dict):
        store = {}

    base = _aggregate_today()
    existing = store.get(today, {})
    base["products_promoted"] = existing.get("products_promoted", {})
    base["frameworks_tagged"] = existing.get("frameworks_tagged", {})
    base["topics"] = existing.get("topics", {})
    base["errors"] = existing.get("errors", 0)
    base["runs"] = existing.get("runs", 0)

    rollup = _merge_run_state(base, state)
    store[today] = rollup
    _save_json(_ANALYTICS_PATH, store)

    synced = _best_effort_sheets_sync(rollup)
    logger.info("Analytics rollup: %d platforms, %d runs, sheets_synced=%s",
                len(rollup["posts_per_platform"]), rollup["runs"], synced)

    return {
        "analytics_today": rollup,
        "analytics_sheets_synced": synced,
    }
