"""Parse natural-language schedule requests into APScheduler spec dicts.

Example inputs → outputs:
    "every day at 9am"              → {"kind": "cron", "cron": "0 9 * * *"}
    "every monday morning"          → {"kind": "cron", "cron": "0 8 * * 1"}
    "every 2 hours"                 → {"kind": "interval", "minutes": 120}
    "weekdays at 6pm crypto"        → {"kind": "cron", "cron": "0 18 * * 1-5", "topic": "crypto"}

LLM-first with a deterministic regex fallback so `/schedule every 4 hours`
never hard-fails even when the router is offline.
"""

from __future__ import annotations

import json
import logging
import re

from src.agent.llm_router import route

logger = logging.getLogger(__name__)

SYSTEM = """You convert a short natural-language schedule request into a JSON spec for APScheduler.

Output ONLY JSON (no prose, no backticks). Required shape — use ONE of:
  {"kind": "cron", "cron": "<minute> <hour> <day> <month> <dow>", "topic": "<optional>"}
  {"kind": "interval", "minutes": <int>, "topic": "<optional>"}

Rules:
- 24-hour time; "morning" = 08:00, "noon" = 12:00, "evening" = 18:00, "night" = 21:00
- Days: mon=1 tue=2 wed=3 thu=4 fri=5 sat=6 sun=0; "weekdays"=1-5, "weekends"=0,6
- If a topic/word like "crypto", "openclaw", "credit" appears, capture it in "topic"
- Never output comments, markdown, or extra keys"""


_WORD_TO_HOUR = {
    "morning": 8, "noon": 12, "afternoon": 14, "evening": 18, "night": 21, "midnight": 0,
}


def _regex_fallback(text: str) -> dict | None:
    t = text.lower().strip()

    # every N hours / minutes
    m = re.search(r"every\s+(\d+)\s*(hour|hr|hours|hrs|minute|minutes|min|mins)", t)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        minutes = n * 60 if "h" in unit else n
        return {"kind": "interval", "minutes": minutes}

    # at Hh(am|pm)
    m = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", t)
    hour = None
    minute = 0
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ap = m.group(3)
        if ap == "pm" and hour < 12:
            hour += 12
        elif ap == "am" and hour == 12:
            hour = 0
    else:
        for word, h in _WORD_TO_HOUR.items():
            if word in t:
                hour = h
                break

    if hour is None:
        return None

    # day-of-week
    dow = "*"
    if "weekday" in t:
        dow = "1-5"
    elif "weekend" in t:
        dow = "0,6"
    else:
        for name, idx in {"mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 0}.items():
            if name in t:
                dow = str(idx)
                break

    topic = None
    for tkw in ("crypto", "openclaw", "credit", "ai automation", "ai_agent_dev", "general"):
        if tkw in t:
            topic = tkw
            break

    spec = {"kind": "cron", "cron": f"{minute} {hour} * * {dow}"}
    if topic:
        spec["topic"] = topic
    return spec


def parse_nl(text: str) -> dict:
    """Return a spec dict. Keys: kind, cron|minutes, topic?"""
    if not text or not text.strip():
        return {"error": "empty input"}

    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        llm = route("schedule_parse")
        resp = llm.invoke([SystemMessage(content=SYSTEM), HumanMessage(content=text.strip()[:400])])
        raw = resp.content if hasattr(resp, "content") else str(resp)
        spec = _extract_json(raw)
        if spec and isinstance(spec, dict) and spec.get("kind") in ("cron", "interval"):
            return spec
        logger.info("LLM parse returned unusable spec %r — falling back to regex", raw[:120])
    except Exception as e:
        logger.warning("LLM schedule parse failed: %s", e)

    fb = _regex_fallback(text)
    if fb:
        return fb
    return {"error": f"could not parse: {text!r}"}


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
