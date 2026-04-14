"""Google Docs subagent — weekly rollup + per-run appends.

Uses Composio GOOGLEDOCS toolkit via entity_id auto-resolve.

Env:
  GOOGLEDOCS_WEEKLY_DOC_ID (optional) — pinned doc id for the weekly report.
    If unset, a new doc is created on the first call and the id is logged.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _entity() -> Optional[str]:
    return os.getenv("COMPOSIO_ENTITY_ID") or os.getenv("COMPOSIO_USER_ID")


def create_document(title: str, markdown: str) -> Dict[str, Any]:
    """Create a new Google Doc from markdown. Returns {success, document_id, url}."""
    entity = _entity()
    if not entity:
        return {"success": False, "error": "COMPOSIO_ENTITY_ID not set"}
    try:
        from src.agent.tools.composio_tools import get_composio_client, _execute_with_fallback
        client = get_composio_client()
        resp = _execute_with_fallback(
            "GOOGLEDOCS_CREATE_DOCUMENT_MARKDOWN",
            {"title": title[:200], "markdown_content": markdown},
            entity,
        )
        if not resp.get("successful"):
            return {"success": False, "error": resp.get("error", "Unknown")}
        data = resp.get("data", {}) or {}
        doc_id = data.get("documentId") or data.get("document_id") or data.get("id") or ""
        return {
            "success": True,
            "document_id": doc_id,
            "url": f"https://docs.google.com/document/d/{doc_id}/edit" if doc_id else "",
        }
    except Exception as e:
        logger.exception("gdocs create failed: %s", e)
        return {"success": False, "error": str(e)}


def _get_body(document_id: str) -> str:
    """Fetch current doc body as markdown (best-effort)."""
    entity = _entity()
    if not entity:
        return ""
    try:
        from src.agent.tools.composio_tools import get_composio_client, _execute_with_fallback
        client = get_composio_client()
        resp = _execute_with_fallback(
            "GOOGLEDOCS_GET_DOCUMENT_BY_ID", {"document_id": document_id}, entity
        )
        if not resp.get("successful"):
            return ""
        data = resp.get("data", {}) or {}
        return data.get("markdown_content") or data.get("body") or ""
    except Exception:
        return ""


def append_section(document_id: str, markdown: str) -> Dict[str, Any]:
    """Append a new section to an existing doc via full markdown rewrite."""
    entity = _entity()
    if not entity:
        return {"success": False, "error": "COMPOSIO_ENTITY_ID not set"}
    if not document_id:
        return {"success": False, "error": "document_id required"}
    current = _get_body(document_id)
    new_body = (current + "\n\n---\n\n" + markdown) if current else markdown
    try:
        from src.agent.tools.composio_tools import get_composio_client, _execute_with_fallback
        client = get_composio_client()
        resp = _execute_with_fallback(
            "GOOGLEDOCS_UPDATE_DOCUMENT_MARKDOWN",
            {"document_id": document_id, "markdown_content": new_body},
            entity,
        )
        if not resp.get("successful"):
            return {"success": False, "error": resp.get("error", "Unknown")}
        return {"success": True, "document_id": document_id}
    except Exception as e:
        logger.exception("gdocs append failed: %s", e)
        return {"success": False, "error": str(e)}


def create_or_append_weekly(markdown: str) -> Dict[str, Any]:
    """Append to the pinned weekly doc if `GOOGLEDOCS_WEEKLY_DOC_ID` is set,
    otherwise create a new weekly doc and log the id."""
    doc_id = os.getenv("GOOGLEDOCS_WEEKLY_DOC_ID")
    if doc_id:
        return append_section(doc_id, markdown)
    title = f"FDWA Weekly Report {datetime.utcnow().strftime('%Y-W%W')}"
    result = create_document(title, markdown)
    if result.get("success"):
        logger.info("Weekly GDoc created — set GOOGLEDOCS_WEEKLY_DOC_ID=%s in .env to reuse",
                    result.get("document_id"))
    return result


def run(state: dict) -> dict:
    """Graph entry — appends `final_briefing_markdown` to the weekly doc."""
    md = state.get("final_briefing_markdown") or state.get("briefing_markdown")
    if not md:
        return {"gdocs_status": "Skipped: no briefing in state"}
    result = create_or_append_weekly(md)
    if result.get("success"):
        return {
            "gdocs_status": f"Appended: {result.get('document_id', '')[:32]}",
            "gdocs_document_id": result.get("document_id"),
            "gdocs_url": result.get("url") or f"https://docs.google.com/document/d/{result.get('document_id')}/edit",
        }
    return {"gdocs_status": f"Failed: {result.get('error', '?')[:120]}"}
