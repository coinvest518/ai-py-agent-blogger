"""Notion subagent — mirrors agent run briefings to a Notion workspace.

Uses Composio NOTION toolkit via entity_id auto-resolve. Keep imports lazy
so that a missing Composio toolkit version doesn't break graph import.

Env:
  NOTION_RUNS_PAGE_ID — parent page ID for all run briefings.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _entity() -> Optional[str]:
    return os.getenv("COMPOSIO_ENTITY_ID") or os.getenv("COMPOSIO_USER_ID")


def _paragraph(text: str) -> Dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text[:1900]}}]},
    }


def _heading(text: str, level: int = 2) -> Dict[str, Any]:
    key = f"heading_{min(max(level, 1), 3)}"
    return {
        "object": "block",
        "type": key,
        key: {"rich_text": [{"type": "text", "text": {"content": text[:1900]}}]},
    }


def _markdown_to_blocks(md: str) -> List[Dict[str, Any]]:
    """Coarse markdown → Notion block conversion (headings + paragraphs).

    Good enough for briefings. For fidelity, use FETCH_PAGE_MARKDOWN /
    UPDATE_DOCUMENT_MARKDOWN via Composio instead.
    """
    blocks: List[Dict[str, Any]] = []
    for raw in (md or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("### "):
            blocks.append(_heading(line[4:], 3))
        elif line.startswith("## "):
            blocks.append(_heading(line[3:], 2))
        elif line.startswith("# "):
            blocks.append(_heading(line[2:], 1))
        else:
            blocks.append(_paragraph(line))
    return blocks[:95]  # Notion limit is 100 block children per call


def create_briefing_page(title: str, markdown_body: str,
                         parent_page_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a new Notion page for this run's briefing."""
    entity = _entity()
    if not entity:
        return {"success": False, "error": "COMPOSIO_ENTITY_ID not set"}
    parent = parent_page_id or os.getenv("NOTION_RUNS_PAGE_ID")
    if not parent:
        return {"success": False, "error": "NOTION_RUNS_PAGE_ID not set"}

    try:
        from src.agent.tools.composio_tools import get_composio_client, _execute_with_fallback
        client = get_composio_client()
    except Exception as e:
        return {"success": False, "error": f"Composio client init failed: {e}"}

    blocks = _markdown_to_blocks(markdown_body)
    try:
        resp = _execute_with_fallback(
            "NOTION_CREATE_NOTION_PAGE",
            {"parent_id": parent, "title": title[:180], "children": blocks},
            entity,
        )
        if not resp.get("successful"):
            return {"success": False, "error": resp.get("error", "Unknown")}
        data = resp.get("data", {}) or {}
        page_id = data.get("id") or data.get("page_id") or ""
        url = data.get("url", "")
        return {"success": True, "page_id": page_id, "url": url}
    except Exception as e:
        logger.exception("Notion create_briefing_page failed: %s", e)
        return {"success": False, "error": str(e)}


def append_run_log(page_id: str, summary: str) -> Dict[str, Any]:
    """Append a paragraph to an existing Notion page."""
    entity = _entity()
    if not entity:
        return {"success": False, "error": "COMPOSIO_ENTITY_ID not set"}
    if not page_id:
        return {"success": False, "error": "page_id required"}
    try:
        from src.agent.tools.composio_tools import get_composio_client, _execute_with_fallback
        client = get_composio_client()
        resp = _execute_with_fallback(
            "NOTION_APPEND_BLOCK_CHILDREN",
            {"block_id": page_id, "children": _markdown_to_blocks(summary)},
            entity,
        )
        if not resp.get("successful"):
            return {"success": False, "error": resp.get("error", "Unknown")}
        return {"success": True}
    except Exception as e:
        logger.exception("Notion append_run_log failed: %s", e)
        return {"success": False, "error": str(e)}


def run(state: dict) -> dict:
    """Graph-compatible entry — reads `final_briefing_markdown` from state."""
    md = state.get("final_briefing_markdown") or state.get("briefing_markdown")
    if not md:
        return {"notion_status": "Skipped: no briefing in state"}
    title = state.get("briefing_title") or "FDWA agent run"
    result = create_briefing_page(title=title, markdown_body=md)
    if result.get("success"):
        return {"notion_status": f"Posted: {result.get('page_id', '')[:32]}",
                "notion_page_id": result.get("page_id"),
                "notion_url": result.get("url")}
    return {"notion_status": f"Failed: {result.get('error', '?')[:120]}"}
