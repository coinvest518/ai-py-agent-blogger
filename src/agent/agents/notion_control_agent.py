"""Notion two-way control surface.

Replaces the long-poll Telegram bot. The agent and user communicate via a
Notion database where each row is a message:

  Message  (title) — what the user typed, or the briefing title on status rows
  Type     (select) — command | question | status
  Status   (select) — pending | answered | error
  Response (rich text) — agent's reply

On each tick (scheduler-driven, every NOTION_POLL_MINUTES=2), we query rows
with Status=pending, dispatch them (commands via existing telegram_control
handlers with a reply-capture shim, questions via llm_router), and write
the answer back by updating Status + Response.

Env:
  NOTION_CONTROL_DB_ID   — required, the FDWA Control database id
  NOTION_POLL_MINUTES    — optional, default 2
  COMPOSIO_ENTITY_ID     — existing Composio connection
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _db_id() -> Optional[str]:
    return os.getenv("NOTION_CONTROL_DB_ID") or None


def _entity() -> Optional[str]:
    return os.getenv("COMPOSIO_ENTITY_ID") or os.getenv("COMPOSIO_USER_ID")


# ── Composio helpers ───────────────────────────────────────────────────────

def _exec(slug: str, args: Dict[str, Any]) -> Dict[str, Any]:
    entity = _entity()
    if not entity:
        return {"successful": False, "error": "COMPOSIO_ENTITY_ID not set"}
    try:
        from src.agent.tools.composio_tools import _execute_with_fallback
        return _execute_with_fallback(slug, args, entity)
    except Exception as e:
        logger.exception("Notion exec failed: %s %s", slug, e)
        return {"successful": False, "error": str(e)}


def _create_row(
    *,
    message: str,
    type_: str,
    status: str,
    response: str = "",
) -> Dict[str, Any]:
    """Create a new row in the FDWA Control DB."""
    db = _db_id()
    if not db:
        return {"success": False, "error": "NOTION_CONTROL_DB_ID not set"}

    properties = [
        {"name": "Message", "type": "title", "value": message[:1900]},
        {"name": "Type", "type": "select", "value": type_},
        {"name": "Status", "type": "select", "value": status},
    ]
    if response:
        properties.append({"name": "Response", "type": "rich_text", "value": response[:1900]})

    resp = _exec("NOTION_INSERT_ROW_DATABASE", {"database_id": db, "properties": properties})
    if resp.get("successful"):
        return {"success": True, "raw": resp.get("data")}
    return {"success": False, "error": resp.get("error") or "insert failed"}


def _update_row(page_id: str, *, status: str, response: str) -> Dict[str, Any]:
    """Update a row's Status + Response."""
    properties = [
        {"name": "Status", "type": "select", "value": status},
        {"name": "Response", "type": "rich_text", "value": response[:1900]},
    ]
    resp = _exec("NOTION_UPDATE_ROW_DATABASE", {"row_id": page_id, "properties": properties})
    if resp.get("successful"):
        return {"success": True}
    return {"success": False, "error": resp.get("error") or "update failed"}


def _query_pending() -> List[Dict[str, Any]]:
    """Return rows where Status=pending."""
    db = _db_id()
    if not db:
        return []
    resp = _exec("NOTION_QUERY_DATABASE", {"database_id": db, "page_size": 50})
    if not resp.get("successful"):
        return []
    data = resp.get("data") or {}
    results = data.get("results") or data.get("items") or []
    if not isinstance(results, list):
        return []
    return results


def _row_field(row: Dict[str, Any]) -> Dict[str, str]:
    """Extract title/type out of a Notion row payload."""
    props = row.get("properties") or {}

    def _title(key: str) -> str:
        p = props.get(key) or {}
        for arr_key in ("title", "rich_text"):
            arr = p.get(arr_key) or []
            if arr:
                return "".join((t.get("plain_text") or (t.get("text") or {}).get("content") or "")
                               for t in arr)
        return ""

    def _select(key: str) -> str:
        p = props.get(key) or {}
        sel = p.get("select") or {}
        return (sel.get("name") or "").lower() if isinstance(sel, dict) else ""

    return {
        "page_id": row.get("id") or "",
        "message": _title("Message"),
        "type": _select("Type") or "command",
        "status": _select("Status"),
    }


# ── Boot + briefing writes ─────────────────────────────────────────────────

def boot_notification(next_run_iso: str) -> Dict[str, Any]:
    """Called on FastAPI startup — writes one status row so user sees the deploy is live."""
    tracing = "on" if os.getenv("LANGSMITH_TRACING", "").lower() in ("1", "true", "yes") else "off"
    msg = f"FDWA online at {datetime.utcnow().isoformat()}Z — next run ~{next_run_iso}, tracing={tracing}"
    return _create_row(message=msg, type_="status", status="answered")


def write_briefing(markdown: str, title: str | None = None) -> Dict[str, Any]:
    """Called from the graph's post_notion node — writes per-run briefing."""
    t = title or f"FDWA run briefing {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    return _create_row(message=t, type_="status", status="answered", response=markdown)


# ── Inbox poll ─────────────────────────────────────────────────────────────

def _dispatch_command(message: str) -> str:
    """Run a slash command via telegram_control_agent handlers with reply capture.

    The telegram handlers call `_reply(chat_id, text)` for each message they
    want to send. We monkey-patch `_reply` to append to a local buffer so the
    handler runs unchanged and we return the concatenated text.
    """
    try:
        from src.agent.agents import telegram_control_agent as tca
    except Exception as e:
        return f"control handlers unavailable: {e}"

    buf: List[str] = []

    def _capture(_chat_id: str, text: str) -> None:
        buf.append(text)

    original = tca._reply
    tca._reply = _capture  # type: ignore[assignment]
    try:
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(tca._dispatch(message, chat_id="notion"))
        finally:
            try:
                loop.close()
            except Exception:
                pass
    except Exception as e:
        logger.exception("notion command dispatch failed")
        buf.append(f"command failed: {e}")
    finally:
        tca._reply = original  # type: ignore[assignment]

    return "\n\n".join(buf) if buf else "(no reply from handler)"


def _answer_question(question: str) -> str:
    """Free-form Q&A — route to the LLM with live agent context."""
    try:
        from src.agent.agents.telegram_control_agent import _collect_self_context
        from src.agent.llm_router import route
        from langchain_core.messages import SystemMessage, HumanMessage

        ctx = _collect_self_context(question=question)
        system = (
            "You are the FDWA agent answering the operator via a Notion row. "
            "Answer ONLY from the live system data below — connections, LLM health, "
            "engagement, memory. Be concrete and short. If the data doesn't cover "
            "the question, say so — don't hallucinate."
        )
        data = json.dumps(ctx, default=str)[:6000]
        user = f"QUESTION: {question}\n\nLIVE DATA:\n{data}"
        llm = route(task="explain_self", needs_long_context=True)
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return (getattr(resp, "content", None) or str(resp)).strip()[:1900]
    except Exception as e:
        logger.exception("notion question failed")
        return f"question failed: {e}"


def poll_inbox() -> Dict[str, Any]:
    """Scheduler entry point — process every row with Status=pending."""
    if not _db_id():
        return {"skipped": True, "reason": "NOTION_CONTROL_DB_ID not set"}
    processed = 0
    errors = 0
    for row in _query_pending():
        meta = _row_field(row)
        page_id = meta["page_id"]
        msg = (meta["message"] or "").strip()
        kind = meta["type"]
        if meta.get("status") != "pending":
            continue
        if not page_id or not msg:
            continue
        try:
            if kind == "command" or msg.startswith("/"):
                response = _dispatch_command(msg if msg.startswith("/") else f"/{msg}")
            elif kind == "question":
                response = _answer_question(msg)
            else:
                response = f"Unknown Type='{kind}'. Expected command/question."
            _update_row(page_id, status="answered", response=response[:1900])
            processed += 1
        except Exception as e:
            logger.exception("notion row %s failed", page_id[:8])
            _update_row(page_id, status="error", response=f"{e}"[:1900])
            errors += 1
    return {"processed": processed, "errors": errors}
