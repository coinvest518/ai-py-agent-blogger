"""Google Docs subagent — weekly rollup + per-run appends.

Uses Composio GOOGLEDOCS toolkit via entity_id auto-resolve.

Env:
  GOOGLEDOCS_WEEKLY_DOC_ID (optional) — pinned doc id for the weekly report.
    If unset, a new doc is created on the first call and the id is logged.
"""

from __future__ import annotations

import json
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

        # Prefer the markdown-aware variants so headings/bold render as
        # formatted doc content, not literal "##" / "**" characters.
        tried = []
        tried_order = [
            ("GOOGLEDOCS_CREATE_DOCUMENT_MARKDOWN", "markdown"),
            ("GOOGLEDOCS_CREATE_DOCUMENT", "markdown_content"),
            ("GOOGLEDOCS_CREATE_DOCUMENT", "markdown"),
            ("GOOGLEDOCS_CREATE_DOCUMENT", "text"),
            ("GOOGLEDOCS_CREATE_DOCUMENT", "content"),
        ]
        for slug, key in tried_order:
            args = {"title": title[:200]}
            args[key] = markdown
            tried.append((slug, key))
            resp = _execute_with_fallback(slug, args, entity)
            logger.debug("GOOGLEDOCS create attempt: slug=%s key=%s successful=%s error=%s", slug, key, resp.get("successful"), resp.get("error"))
            if resp.get("successful"):
                data = resp.get("data", {}) or {}
                doc_id = data.get("documentId") or data.get("document_id") or data.get("id") or ""
                if not doc_id:
                    logger.warning("GOOGLEDOCS create succeeded without document_id: slug=%s data=%s", slug, data)

                # Verify the body — fetch document body if possible
                body = _get_body(doc_id) if doc_id else ""
                if body:
                    try:
                        body_text = body if isinstance(body, str) else json.dumps(body)
                    except Exception:
                        body_text = str(body)
                    if len(body_text.strip()) > 5:
                        return {"success": True, "document_id": doc_id,
                                "url": f"https://docs.google.com/document/d/{doc_id}/edit"}

                # If the create call succeeded but body is empty, attempt an explicit update
                try:
                    upd = _execute_with_fallback(
                        "GOOGLEDOCS_UPDATE_DOCUMENT_MARKDOWN",
                        {"document_id": doc_id, "markdown": markdown},
                        entity,
                    )
                    logger.debug("GOOGLEDOCS update-after-create body-empty attempt: result=%s", upd.get("successful"))
                    if upd.get("successful"):
                        return {"success": True, "document_id": doc_id,
                                "url": f"https://docs.google.com/document/d/{doc_id}/edit"}
                    logger.warning("GOOGLEDOCS update-after-create failed: %s", upd.get("error"))
                except Exception as e:
                    logger.warning("GOOGLEDOCS update-after-create exception: %s", e)

                return {"success": True, "document_id": doc_id,
                        "url": f"https://docs.google.com/document/d/{doc_id}/edit"}

        # If no create path succeeded, return error with diagnostics
        return {"success": False, "error": f"Create attempts failed: tried={tried}"}
    except Exception as e:
        logger.exception("gdocs create failed: %s", e)
        return {"success": False, "error": str(e)}


def _get_body(document_id: str) -> str:
    """Fetch current doc body as plaintext (best-effort).

    Prefers `markdown_content` if present; otherwise if the returned body is
    a structured dict (Google Docs format), extract all `textRun.content`
    pieces and concatenate them into a plaintext string.
    """
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
        # Prefer explicit markdown if provided
        md = data.get("markdown_content")
        if isinstance(md, str) and md.strip():
            return md
        # If 'body' is a plain string, return it
        body = data.get("body") or data.get("document") or data
        if isinstance(body, str):
            return body
        # Recursively collect any textRun.content values from structured body
        pieces: list = []
        def _collect(o: Any) -> None:
            if isinstance(o, dict):
                tr = o.get("textRun")
                if isinstance(tr, dict):
                    ct = tr.get("content")
                    if isinstance(ct, str):
                        pieces.append(ct)
                for v in o.values():
                    _collect(v)
            elif isinstance(o, list):
                for item in o:
                    _collect(item)
        _collect(body)
        if pieces:
            return "".join(pieces)
        return ""
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
        # Note: Composio GOOGLEDOCS_UPDATE_DOCUMENT_MARKDOWN expects a 'markdown' field.
        resp = _execute_with_fallback(
            "GOOGLEDOCS_UPDATE_DOCUMENT_MARKDOWN",
            {"document_id": document_id, "markdown": new_body},
            entity,
        )
        if not resp.get("successful"):
            return {"success": False, "error": resp.get("error", "Unknown")}
        return {"success": True, "document_id": document_id}
    except Exception as e:
        logger.exception("gdocs append failed: %s", e)
        return {"success": False, "error": str(e)}


def create_per_run(markdown: str, briefing_title: str | None = None) -> Dict[str, Any]:
    """Create a new Google Doc for each run's briefing."""
    title = briefing_title or f"FDWA Run Briefing {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    return create_document(title, markdown)


def run(state: dict) -> dict:
    """Graph entry — creates a new Google Doc per run with the full briefing."""
    md = state.get("final_briefing_markdown") or state.get("briefing_markdown")
    if not md:
        return {"gdocs_status": "Skipped: no briefing in state"}
    result = create_per_run(md, state.get("briefing_title"))
    if result.get("success"):
        return {
            "gdocs_status": f"Appended: {result.get('document_id', '')[:32]}",
            "gdocs_document_id": result.get("document_id"),
            "gdocs_url": result.get("url") or f"https://docs.google.com/document/d/{result.get('document_id')}/edit",
        }
    return {"gdocs_status": f"Failed: {result.get('error', '?')[:120]}"}
