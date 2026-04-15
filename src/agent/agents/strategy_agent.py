"""Strategy Agent — synthesises engagement + GA + trends into a per-cycle brief.

Runs BETWEEN research_trends and generate_content. Reads:
  - state["engagement_summary"]       (fresh, from pull_engagement)
  - state["trend_data"]                (fresh, from research_trends)
  - previous cycle's GA snapshot       (loaded from disk)
  - state["topic_override"]            (optional, from /post <topic>)

Writes:
  - state["content_strategy_brief"]    (dict → topic, angle, avoid, tone,
                                        platform_priorities, reasoning)

Downstream `generate_content` and each `content_agent.generate_*` function
injects this brief into its LLM prompt so the next post is informed by what
actually performed yesterday instead of ignoring the data we already collect.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

GA_PREV_PATH = Path(os.getenv("GA_PREV_SNAPSHOT_PATH", ".ga_prev_snapshot.json"))


def _load_prev_ga() -> dict:
    try:
        if GA_PREV_PATH.exists():
            return json.loads(GA_PREV_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug("prev GA load failed: %s", e)
    return {}


def _ga_to_prose(snap: dict) -> str:
    """Flatten a GA snapshot dict into 1-3 lines of human-readable prose."""
    if not snap or snap.get("skipped"):
        return ""
    parts: list[str] = []
    daily = (snap.get("daily") or {}).get("data") or {}
    top = (snap.get("top_pages_7d") or {}).get("data") or {}

    rows = daily.get("rows") or []
    if rows:
        total_users = 0
        total_sessions = 0
        for r in rows:
            vals = r.get("metricValues") or []
            try:
                total_users += int(vals[0].get("value", 0))
                total_sessions += int(vals[1].get("value", 0))
            except Exception:
                pass
        parts.append(f"Yesterday: {total_users} users / {total_sessions} sessions")

    top_rows = top.get("rows") or []
    if top_rows:
        top_urls = []
        for r in top_rows[:3]:
            dims = r.get("dimensionValues") or []
            vals = r.get("metricValues") or []
            if dims and vals:
                path = dims[0].get("value", "?")
                views = vals[0].get("value", "?")
                top_urls.append(f"{path} ({views}v)")
        if top_urls:
            parts.append("Top 7d: " + ", ".join(top_urls))

    return " | ".join(parts)


PROMPT_SYSTEM = """You are FDWA's content strategist. You see yesterday's engagement,
site traffic, and today's fresh trend research. Output ONE JSON object:

{
  "topic": "<the single subject every platform will post about today>",
  "angle": "<how to frame it — specific hook, not generic>",
  "avoid": ["<anything to NOT repeat from yesterday's low performers>"],
  "tone": "<builder / analytical / hype / teaching — pick one>",
  "platform_priorities": {"linkedin": "<what to emphasise on LI>",
                           "facebook": "<what to emphasise on FB>",
                           "instagram": "<what to emphasise on IG>",
                           "telegram": "<what to emphasise on TG>"},
  "buffer_schedule": "<ONE OF: 'now' (default — publish immediately) | ISO-8601 UTC timestamp (e.g. '2026-03-10T15:00:00.000Z') for a better posting time if engagement data suggests waiting>",
  "reasoning": "<1-2 sentences justifying the call from the data, including why the chosen schedule time>"
}

Rules:
- Pick 'now' unless the engagement data clearly shows a better window within the next 24h (e.g. yesterday's top posts landed between 9-11am UTC and it's currently 3am).
- If picking a timestamp, it MUST be in the future and within 24h.
- No prose, no markdown fences, just the JSON."""


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:].strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    start, end = t.find("{"), t.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(t[start : end + 1])
        except Exception:
            return None
    return None


def run(state: dict) -> dict:
    """Build the strategy brief; return dict to merge into graph state."""
    topic_override = (state.get("topic_override") or "").strip()
    engagement_summary = (state.get("engagement_summary") or "")[:800]
    trend_data = (state.get("trend_data") or "")[:1200]
    prev_ga = _load_prev_ga()
    ga_prose = _ga_to_prose(prev_ga)

    user_msg = (
        f"Time: {datetime.utcnow().isoformat(timespec='minutes')}Z\n"
        f"Operator topic override: {topic_override or '(none — you pick)'}\n"
        f"Yesterday's engagement: {engagement_summary or '(none)'}\n"
        f"Prior-run GA traffic: {ga_prose or '(none)'}\n"
        f"Today's trend research: {trend_data}\n\n"
        "Produce the strategy JSON now. If operator topic is set, `topic` MUST match it."
    )

    brief: dict = {}
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        from src.agent.llm_router import route
        llm = route("strategy_brief", needs_long_context=True)
        resp = llm.invoke([SystemMessage(content=PROMPT_SYSTEM), HumanMessage(content=user_msg)])
        raw = resp.content if hasattr(resp, "content") else str(resp)
        brief = _extract_json(raw) or {}
    except Exception as e:
        logger.warning("Strategy LLM failed: %s", e)

    if topic_override and brief.get("topic") != topic_override:
        brief["topic"] = topic_override

    if not brief.get("topic"):
        brief["topic"] = topic_override or "AI agents for digital wealth"
    brief.setdefault("angle", "builder's-notebook — what we shipped and how")
    brief.setdefault("tone", "builder")
    brief.setdefault("avoid", [])
    brief.setdefault("platform_priorities", {})
    brief.setdefault("buffer_schedule", "now")
    brief.setdefault("reasoning", "defaults used (LLM unavailable or empty)")

    # Translate buffer_schedule → state["buffer_scheduled_at"] (empty means immediate)
    sched = str(brief.get("buffer_schedule", "now")).strip()
    buffer_scheduled_at = "" if sched.lower() in ("now", "immediate", "") else sched

    logger.info("Strategy brief: topic=%r angle=%r buffer_schedule=%r",
                brief.get("topic"), brief.get("angle"), sched)
    result: dict = {"content_strategy_brief": brief}
    if buffer_scheduled_at:
        result["buffer_scheduled_at"] = buffer_scheduled_at
    return result


def format_for_prompt(brief: dict | None) -> str:
    """Turn the brief into a ready-to-paste prompt fragment for content agents."""
    if not brief:
        return ""
    lines = ["TODAY'S STRATEGY BRIEF (follow this — derived from real engagement + GA data):"]
    if brief.get("topic"):
        lines.append(f"- Topic: {brief['topic']}")
    if brief.get("angle"):
        lines.append(f"- Angle: {brief['angle']}")
    if brief.get("tone"):
        lines.append(f"- Tone: {brief['tone']}")
    avoid = brief.get("avoid") or []
    if avoid:
        lines.append(f"- Avoid: {', '.join(str(a) for a in avoid[:4])}")
    if brief.get("reasoning"):
        lines.append(f"- Why: {brief['reasoning']}")
    return "\n".join(lines) + "\n"


def format_platform_hint(brief: dict | None, platform: str) -> str:
    """Per-platform emphasis line."""
    if not brief:
        return ""
    prios = brief.get("platform_priorities") or {}
    hint = prios.get(platform)
    if not hint:
        return ""
    return f"\nPlatform emphasis ({platform}): {hint}\n"
