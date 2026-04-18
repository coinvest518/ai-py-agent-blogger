"""Retry middleware with Mem0 error→fix recall.

Wrap a graph node function to get:
  1. Automatic retry on exception OR when the result dict carries a `*_status`
     that starts with "Failed".
  2. Mem0 lookup of `kind=agent_error_fix` memories before each retry — if a
     prior fix for the same error class is remembered, log the hint so the
     next attempt has a chance to consult it.
  3. On success-after-retry, store the (error → fix) pair back into Mem0.

Usage:

    from src.agent.middleware.retry import with_retry

    @with_retry(max_attempts=2)
    def post_linkedin_node(state):
        ...
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Dict

from src.agent import mem0_adapter

try:
    from langsmith import traceable
except Exception:
    def traceable(*_a, **_kw):
        def _decor(fn):
            return fn
        return _decor

logger = logging.getLogger(__name__)

ERROR_USER_ID = "agent-errors"


def _extract_error(result: Any) -> str:
    """Inspect a node return value for a failure signal. Empty string = success."""
    if not isinstance(result, dict):
        return ""
    for key, val in result.items():
        if not isinstance(val, str):
            continue
        low = val.lower()
        if key.endswith("status") and low.startswith("failed"):
            return val
        if key == "error" and val:
            return val
    return ""


def _error_class(err: str) -> str:
    """Collapse an error string to a coarse class for Mem0 lookup."""
    s = err.lower()
    if "426" in s or "nonexistent_version" in s:
        return "composio_toolkit_version"
    if "401" in s or "unauthorized" in s:
        return "auth_401"
    if "403" in s:
        return "auth_403"
    if "429" in s or "rate" in s:
        return "rate_limited"
    if "timeout" in s or "timed out" in s:
        return "timeout"
    if "quota" in s or "cap" in s:
        return "quota_exhausted"
    return "generic"


def _recall_fix(err: str) -> str:
    """Look up a remembered fix for this error class. Returns "" if none."""
    cls = _error_class(err)
    hits = mem0_adapter.recall_relevant(
        query=f"fix for error class {cls}: {err[:200]}",
        top_k=3,
        user_id=ERROR_USER_ID,
    )
    if not hits:
        return ""
    first = hits[0] if isinstance(hits, list) else {}
    if isinstance(first, dict):
        return (first.get("memory") or first.get("text") or "")[:300]
    return ""


def _remember_fix(err: str, fix_desc: str) -> None:
    cls = _error_class(err)
    mem0_adapter.remember(
        content=f"[{cls}] error: {err[:300]} -> fix: {fix_desc[:300]}",
        user_id=ERROR_USER_ID,
        metadata={"kind": "agent_error_fix", "class": cls},
    )


def with_retry(max_attempts: int = 2) -> Callable:
    """Decorator that wraps a graph node with retry + Mem0 learning."""
    def decorator(fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Callable:
        @functools.wraps(fn)
        def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
            last_err = ""
            for attempt in range(1, max_attempts + 1):
                try:
                    result = fn(state)
                except Exception as e:
                    last_err = f"exception: {e}"
                    logger.warning("[retry] %s attempt %d crashed: %s", fn.__name__, attempt, e)
                    result = None

                err = _extract_error(result) if result is not None else last_err
                if not err:
                    if last_err and attempt > 1:
                        _remember_fix(last_err, f"retry succeeded on attempt {attempt} of {fn.__name__}")
                    return result or {}

                hint = _recall_fix(err)
                if hint:
                    logger.info("[retry] %s mem0 hint for '%s': %s",
                                fn.__name__, _error_class(err), hint[:160])
                if attempt < max_attempts:
                    logger.info("[retry] %s attempt %d failed (%s) — retrying",
                                fn.__name__, attempt, _error_class(err))
                last_err = err

            logger.error("[retry] %s exhausted %d attempts: %s", fn.__name__, max_attempts, last_err[:200])
            return result if isinstance(result, dict) else {"error": last_err[:300]}

        return wrapper
    return decorator


@traceable(name="llm_retry", run_type="chain")
def invoke_llm_with_retry(llm, prompt, max_attempts: int = 2):
    """Invoke an LLM wrapper with Mem0-assisted retry.

    This mirrors the node-level retry behavior but is scoped to LLM
    invocations (so skill/tool calls and download middleware remain
    separate). It recalls mem0 hints before retries and remembers
    a successful fix when a retry succeeds.
    """
    last_err = ""
    for attempt in range(1, max_attempts + 1):
        try:
            resp = llm.invoke(prompt)
            content = getattr(resp, "content", None) if resp is not None else None
            if content and str(content).strip():
                if last_err and attempt > 1:
                    _remember_fix(last_err, f"LLM retry succeeded on attempt {attempt}")
                return resp
            # Empty response treated as error
            last_err = "empty response"
            logger.warning("[llm_retry] attempt %d returned empty response", attempt)
        except Exception as e:
            last_err = f"exception: {e}"
            logger.warning("[llm_retry] LLM invoke attempt %d failed: %s", attempt, e)

        hint = _recall_fix(last_err)
        if hint:
            logger.info("[llm_retry] mem0 hint for LLM: %s", hint[:160])
        if attempt < max_attempts:
            logger.info("[llm_retry] retrying LLM (attempt %d/%d)", attempt + 1, max_attempts)

    logger.error("[llm_retry] exhausted %d attempts: %s", max_attempts, last_err[:200])
    raise RuntimeError(f"LLM invoke failed after {max_attempts} attempts: {last_err}")
