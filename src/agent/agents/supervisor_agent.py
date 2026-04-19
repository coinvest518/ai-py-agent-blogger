"""Supervisor Agent — turns the single-shot cron DAG into a planned cycle.

Two entry points:

    plan(state)    — runs BEFORE the static DAG. Takes engagement snapshot,
                     recent Mem0 recalls, time, and brand context; produces
                     a JSON plan with `reasoning, goals, subagent_order,
                     skips, risk_notes`.

    reflect(state) — runs AFTER record_memory. Reviews what succeeded/failed
                     in the cycle; writes a reflection to Mem0 with
                     `kind="supervisor_reflection"` so the next plan() can
                     recall it.

Downstream post_* nodes should check `state["plan"].get("skips", [])` and
short-circuit if their platform is listed — this gives the supervisor
real authority without mutating the DAG shape.

Kill switch: set `SUPERVISOR_ENABLED=false` to make plan() return `{}` and
reflect() become a no-op; callers fall through to the old single-shot flow.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from src.agent.llm_router import route
from src.agent.realtime_status import broadcaster

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    return os.getenv("SUPERVISOR_ENABLED", "true").lower() not in ("0", "false", "no", "off")


def _broadcast(step: str, text: str) -> None:
    try:
        broadcaster.update(step, text)  # type: ignore[attr-defined]
    except Exception:
        pass


def _recent_mem0(query: str = "recent run", k: int = 5) -> list[dict]:
    try:
        from src.agent.mem0_adapter import recall_relevant
        return recall_relevant(query=query, top_k=k, user_id="fdwa_agent") or []
    except Exception as e:
        logger.warning("Mem0 recall failed in supervisor: %s", e)
        return []


PLAN_SYSTEM = """You are the FDWA supervisor agent. A scheduler wakes you every 6 hours.
Your job: decide what the pipeline should DO this cycle, not just run the default graph.

Consider:
- Yesterday's engagement (which platform performed well, which flopped)
- Recent Mem0 entries (what the agent already did, what failed, what's been tried)
- Known transports:
  - Twitter/X: Zernio MCP (ZERNIO_API_KEY) — PRIMARY, unlimited text+image. Upload-post is media-only fallback.
  - LinkedIn: Pipedream MCP PRIMARY, Composio fallback, upload-post last resort.
  - Facebook/Instagram: Composio primary, Pipedream fallback.
  - Buffer MCP: Pinterest/YouTube/TikTok (image+text).
- Known quotas:
  - upload_post: DISABLED (no video generator yet). Always include "post_upload_post" in `skips`.
  - LinkedIn: soft-cap is enforced inside the LinkedIn node itself (LINKEDIN_DAILY_LIMIT default 3). Do NOT add post_linkedin to skips — let the node decide.
- Current UTC time

HARD RULES for `skips`:
- NEVER include post_facebook, post_instagram, post_twitter, or post_linkedin — these core channels always run and enforce their own caps internally.
- `post_upload_post` may be skipped only when Upload-Post is unavailable, not configured, or no compatible media exists.
- Do not invent new skip targets.

Output ONLY a JSON object (no prose, no markdown fences) with this shape:
{
  "reasoning": "<2-3 sentences on why this plan>",
  "goals": ["<short goal>", "..."],
  "subagent_order": ["research_trends", "generate_content", "..."],
  "skips": ["<node names to skip, e.g. post_linkedin if quota hit>"],
  "risk_notes": ["<things to watch>"]
}"""

REFLECT_SYSTEM = """You are the FDWA supervisor agent reviewing the cycle you just ran.
Read the state dict snapshot. Output ONLY a JSON object:
{
  "what_worked": ["..."],
  "what_failed": ["..."],
  "next_cycle_adjustments": ["..."]
}"""


def plan(state: dict) -> dict:
    """Compute the plan; return dict to merge into state."""
    if not _enabled():
        return {"plan": {"reasoning": "supervisor disabled", "skips": [], "goals": []}}

    _broadcast("supervisor_plan", "Planning cycle…")

    engagement_summary = state.get("engagement_summary") or "no engagement snapshot yet"
    recent = _recent_mem0("recent cycle performance", k=5)
    recent_brief = "; ".join(
        (m.get("memory") or m.get("content") or "")[:160] for m in recent
    )[:1200]

    def _upload_post_enabled() -> bool:
        return bool(
            os.getenv("UPLOAD_POST_ENABLE", "").lower() in ("1", "true", "yes")
            or os.getenv("UPLOADPOST_API_KEY")
            or os.getenv("UPLOAD_POST_API_KEY")
        )

    try:
        from src.agent.agents.upload_post_agent import remaining_quota as _up_remaining
        upload_post_remaining = _up_remaining()
    except Exception:
        upload_post_remaining = None
    upload_post_enabled = _upload_post_enabled()
    linkedin_daily_limit = os.getenv("LINKEDIN_DAILY_LIMIT", "1")

    now = datetime.utcnow().isoformat(timespec="minutes") + "Z"
    user_msg = (
        f"Time: {now}\n"
        f"Engagement: {engagement_summary[:600]}\n"
        f"Upload-Post available: {upload_post_enabled}\n"
        f"Recent Mem0: {recent_brief or '(none)'}\n"
        f"Quotas: upload_post_weekly_remaining={upload_post_remaining}, "
        f"linkedin_daily_limit={linkedin_daily_limit}\n"
        "Produce the JSON plan now."
    )

    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        llm = route("supervisor_plan", needs_long_context=True)
        resp = llm.invoke([SystemMessage(content=PLAN_SYSTEM), HumanMessage(content=user_msg)])
        raw = resp.content if hasattr(resp, "content") else str(resp)
        plan_obj = _extract_json(raw) or {"reasoning": raw[:400], "skips": [], "goals": []}
    except Exception as e:
        logger.exception("Supervisor plan failed: %s", e)
        plan_obj = {"reasoning": f"plan error: {e}", "skips": [], "goals": []}

    # Belt-and-suspenders: normalize skips regardless of what LLM returned.
    skips = plan_obj.setdefault("skips", [])
    # Only skip upload-post if the API is not configured.
    if not upload_post_enabled and "post_upload_post" not in skips:
        skips.append("post_upload_post")
    # Core channels must always run — strip if LLM put them in skips (LinkedIn
    # enforces its own daily cap inside the node; supervisor must not skip it).
    for core in ("post_facebook", "post_instagram", "post_twitter", "post_linkedin"):
        if core in skips:
            skips.remove(core)
    plan_obj["skips"] = skips

    narrative = plan_obj.get("reasoning", "")[:240]
    _broadcast("supervisor_plan", f"Plan: {narrative}")
    logger.info("Supervisor plan: %s", narrative)
    return {
        "plan": plan_obj,
        "upload_post_remaining": upload_post_remaining,
    }


def reflect(state: dict) -> dict:
    """Review the cycle, persist reflection to Mem0."""
    if not _enabled():
        return {"reflection": {"skipped": True}}

    _broadcast("supervisor_reflect", "Reflecting on cycle…")

    snapshot = {
        k: (str(v)[:200] if not isinstance(v, (int, float, bool)) else v)
        for k, v in state.items()
        if k in (
            "engagement_summary", "trend_data", "tweet_text", "twitter_url",
            "facebook_status", "linkedin_status", "instagram_status",
            "telegram_status", "blog_status", "video_url", "image_url",
            "memory_status", "error",
        )
    }

    user_msg = f"State snapshot:\n{json.dumps(snapshot, default=str)[:3000]}\nReflect now."

    reflection_obj: dict
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        llm = route("supervisor_reflect", needs_long_context=True)
        resp = llm.invoke([SystemMessage(content=REFLECT_SYSTEM), HumanMessage(content=user_msg)])
        raw = resp.content if hasattr(resp, "content") else str(resp)
        reflection_obj = _extract_json(raw) or {"what_worked": [], "what_failed": [raw[:400]], "next_cycle_adjustments": []}
    except Exception as e:
        logger.exception("Supervisor reflect failed: %s", e)
        reflection_obj = {"what_worked": [], "what_failed": [f"reflect error: {e}"], "next_cycle_adjustments": []}

    try:
        from src.agent.mem0_adapter import remember
        remember(
            content=f"supervisor_reflection: {json.dumps(reflection_obj)[:800]}",
            user_id="fdwa_agent",
            metadata={"kind": "supervisor_reflection"},
        )
    except Exception as e:
        logger.warning("Mem0 reflection write failed: %s", e)

    _broadcast("supervisor_reflect", "Reflection stored")
    return {"reflection": reflection_obj}


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return None
    return None


def should_skip(state: dict, node: str) -> bool:
    """Helper for downstream nodes: did the plan tell us to skip this node?"""
    plan_obj = (state.get("plan") or {})
    skips = plan_obj.get("skips") or []
    return node in skips
