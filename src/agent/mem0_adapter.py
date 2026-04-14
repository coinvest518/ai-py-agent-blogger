"""Mem0 cloud adapter — long-term episodic memory layer.

Best-effort wrapper. If `mem0ai` package isn't installed or `MEM0_API_KEY`
isn't set, all calls become no-ops so the rest of the agent keeps working.

Use cases:
- remember_conversation(user_id, msg) — stash chat with the /ask endpoint
- recall_relevant(query, top_k) — pull episodic context for any agent
- record_run(state) — store a per-run summary for self-reflection
"""

from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

_client: Optional[Any] = None
_disabled = False


def _get_client():
    """Lazy-init Mem0 cloud client. Returns None if unavailable."""
    global _client, _disabled
    if _disabled:
        return None
    if _client is not None:
        return _client
    api_key = os.getenv("MEM0_API_KEY")
    if not api_key:
        _disabled = True
        return None
    try:
        from mem0 import MemoryClient
        _client = MemoryClient(api_key=api_key)
        logger.info("✅ Mem0 cloud client initialised")
        return _client
    except Exception as e:
        logger.warning("Mem0 unavailable (%s) — disabling adapter", e)
        _disabled = True
        return None


def remember(content: str, user_id: str = "fdwa_agent", metadata: dict | None = None) -> bool:
    """Store a memory snippet directly (no LLM fact-extraction). Returns True on success.

    Uses infer=False so the snippet is indexed immediately and searchable
    without waiting on the async fact-extraction queue.
    """
    client = _get_client()
    if not client or not content:
        return False
    try:
        client.add(
            messages=[{"role": "user", "content": content[:4000]}],
            user_id=user_id,
            metadata=metadata or {},
            infer=False,
        )
        return True
    except Exception as e:
        logger.debug("Mem0 add failed: %s", e)
        return False


def remember_conversation(user_id: str, user_msg: str, assistant_msg: str) -> bool:
    """Store a conversation turn."""
    client = _get_client()
    if not client:
        return False
    try:
        client.add(
            messages=[
                {"role": "user", "content": user_msg[:4000]},
                {"role": "assistant", "content": assistant_msg[:4000]},
            ],
            user_id=user_id,
        )
        return True
    except Exception as e:
        logger.debug("Mem0 conversation add failed: %s", e)
        return False


def recall_relevant(query: str, top_k: int = 5, user_id: str = "fdwa_agent") -> List[dict]:
    """Search episodic memory for the query. Returns [] when unavailable.

    Mem0 cloud v2 requires `filters={user_id: ...}` and returns `{"results": [...]}`.
    We normalize both shapes and always return a plain list of hit dicts.
    """
    client = _get_client()
    if not client or not query:
        return []
    try:
        raw = client.search(
            query=query,
            filters={"user_id": user_id},
            version="v2",
            limit=top_k,
        )
        if isinstance(raw, dict):
            raw = raw.get("results", []) or []
        return raw if isinstance(raw, list) else []
    except Exception as e:
        logger.debug("Mem0 search failed: %s", e)
        return []


def record_run(state: dict, user_id: str = "fdwa_agent") -> bool:
    """Summarise this run into Mem0 for future self-reflection."""
    strategy = state.get("ai_strategy") or {}
    angle = strategy.get("monetization_angle") or {}
    summary_parts = []
    if strategy.get("topic"):
        summary_parts.append(f"Topic: {strategy['topic']}")
    if angle.get("free_guide"):
        summary_parts.append(f"Free guide: {angle['free_guide'].get('name')}")
    if angle.get("paid_skill"):
        summary_parts.append(f"Paid: {angle['paid_skill'].get('name')}")
    if angle.get("framework_used"):
        summary_parts.append(f"Frameworks: {', '.join(angle['framework_used'])}")
    sent = state.get("content_sentiment") or {}
    if sent.get("label"):
        summary_parts.append(f"Sentiment: {sent['label']}")
    if not summary_parts:
        return False
    return remember(
        " | ".join(summary_parts),
        user_id=user_id,
        metadata={"kind": "run_summary"},
    )
