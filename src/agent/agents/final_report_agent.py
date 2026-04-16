"""Final Report subagent — the real end-of-run intelligence briefing.

Reads actual data (posts, analytics, wallet, upload-post quota, Mem0 last-7)
and asks the LLM router for a synthesis. Writes to four destinations:
  1. Telegram (truncated 3500 chars)
  2. Notion (full markdown)
  3. Google Docs weekly (appended)
  4. Gmail self-send (full markdown)

Returns a dict with a `final_briefing_markdown` field so downstream nodes
(post_telegram, notion, gdocs) can reuse the same string.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SOCIAL_HISTORY = REPO_ROOT / "social_media_history.json"
DAILY_ANALYTICS = REPO_ROOT / "agent_analytics_daily.json"


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return default


def _today_posts() -> List[dict]:
    hist = _read_json(SOCIAL_HISTORY, {})
    # Support both legacy list-format and current dict with a "posts" key
    posts = []
    if isinstance(hist, dict):
        posts = hist.get("posts", []) or []
    elif isinstance(hist, list):
        posts = hist
    else:
        return []
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return [p for p in posts if isinstance(p, dict) and str(p.get("timestamp", ""))[:10] == today]


def _upload_post_quota() -> Dict[str, Any]:
    try:
        from src.agent.agents import upload_post_agent
        return {"remaining": upload_post_agent.remaining_quota(),
                "cap": upload_post_agent.MONTHLY_CAP}
    except Exception as e:
        return {"error": str(e)}


def _ga_snapshot() -> Dict[str, Any]:
    try:
        from src.agent.agents import ganalytics_agent
        return ganalytics_agent.summary()
    except Exception as e:
        return {"error": str(e)}


def _wallet_snapshot() -> Dict[str, Any]:
    try:
        from src.agent.agents import onchain_agent
        return onchain_agent.snapshot()
    except Exception as e:
        return {"error": str(e)}


def _recent_mem0(limit: int = 5) -> List[str]:
    try:
        from src.agent import mem0_adapter
        hits = mem0_adapter.recall_relevant(
            query="recent agent run summary",
            top_k=limit,
            user_id="fdwa_agent",
        )
        return [
            (h.get("memory") or h.get("text") or "")[:200]
            for h in (hits or []) if isinstance(h, dict)
        ]
    except Exception:
        return []


def gather_context(state: dict) -> Dict[str, Any]:
    """Pull every data source the briefing needs."""
    return {
        "run_started_at": datetime.utcnow().isoformat() + "Z",
        "today_posts": _today_posts(),
        "daily_analytics": _read_json(DAILY_ANALYTICS, {}),
        "upload_post": _upload_post_quota(),
        "ga": _ga_snapshot(),
        "wallet": _wallet_snapshot(),
        "recent_runs": _recent_mem0(),
        "strategy": state.get("ai_strategy") or {},
        "statuses": {
            k: state.get(k) for k in [
                "twitter_url", "facebook_status", "linkedin_status",
                "instagram_status", "telegram_status", "upload_post_status",
                "blog_status", "comment_status",
            ] if state.get(k)
        },
        "errors": state.get("error"),
    }


_SYSTEM_PROMPT = """You are the FDWA agent's end-of-run analyst. Build a concise
intelligence briefing in markdown with these sections (use ## headings):

## Posts today
## Engagement / analytics
## Trends captured
## What's missing
## Next actions
## Wallet + crypto signals

Keep it under 800 words. Use bullet points. Lead with what actually happened
(real numbers from the context), then what was missed, then concrete next
actions. Do not invent metrics — if a number isn't in the context, say
"no data yet"."""


def _synthesize(context: Dict[str, Any]) -> str:
    try:
        from src.agent.llm_router import route
    except Exception as e:
        return _fallback_briefing(context, f"router unavailable: {e}")

    try:
        llm = route(task="final_analysis", needs_long_context=True)
        prompt = _SYSTEM_PROMPT + "\n\nCONTEXT:\n" + json.dumps(context, default=str)[:6000]
        try:
            from src.agent.middleware.retry import invoke_llm_with_retry
            attempts = int(os.getenv("LLM_RETRY_ATTEMPTS", "2"))
            resp = invoke_llm_with_retry(llm, prompt, max_attempts=attempts)
        except Exception:
            resp = llm.invoke(prompt)
        text = getattr(resp, "content", None) or str(resp)
        if text and len(text.strip()) > 100:
            return text.strip()
    except Exception as e:
        logger.warning("final_report synthesis failed: %s", e)
    return _fallback_briefing(context, "LLM path skipped")


def _fallback_briefing(ctx: Dict[str, Any], reason: str) -> str:
    posts = ctx.get("today_posts") or []
    statuses = ctx.get("statuses") or {}
    up = ctx.get("upload_post") or {}
    wallet = (ctx.get("wallet") or {}).get("wallet") or {}
    lines = [
        "# FDWA agent run briefing (fallback)",
        f"_{ctx.get('run_started_at', '')}_",
        f"_Synth note: {reason}_",
        "",
        "## Posts today",
        f"- {len(posts)} post(s) recorded in social_media_history.json.",
    ]
    for k, v in statuses.items():
        lines.append(f"- {k}: {str(v)[:160]}")
    lines += [
        "",
        "## Upload-post quota",
        f"- Remaining this month: {up.get('remaining', '?')} / {up.get('cap', '?')}",
        "",
        "## Wallet",
        f"- Address: {wallet.get('address', '—')}",
        f"- Balance: {wallet.get('eth', 0)} ETH on {wallet.get('network', '?')}",
        "",
        "## Next actions",
        "- Review LLM cascade if briefing landed in fallback path.",
        "- Check errors in state: " + str(ctx.get("errors") or "none"),
    ]
    return "\n".join(lines)


def _plan_section(state: dict) -> str:
    plan = state.get("plan") or {}
    if not plan:
        return ""
    lines = ["", "## Supervisor plan"]
    if plan.get("reasoning"):
        lines.append(f"- Reasoning: {plan['reasoning']}")
    goals = plan.get("goals") or []
    if goals:
        lines.append("- Goals: " + "; ".join(str(g) for g in goals[:5]))
    skips = plan.get("skips") or []
    if skips:
        lines.append("- Skipped this cycle: " + ", ".join(str(s) for s in skips))
    risks = plan.get("risk_notes") or []
    if risks:
        lines.append("- Risk notes: " + "; ".join(str(r) for r in risks[:5]))
    return "\n".join(lines)


def build_briefing(state: dict) -> str:
    body = _synthesize(gather_context(state))
    plan_md = _plan_section(state)
    return body + plan_md if plan_md else body


def _send_gmail(md: str) -> Dict[str, Any]:
    """Self-send the briefing via Gmail (Composio). Silent on missing creds."""
    entity = os.getenv("COMPOSIO_ENTITY_ID") or os.getenv("COMPOSIO_USER_ID")
    to_addr = os.getenv("BRIEFING_EMAIL_TO") or os.getenv("BLOGGER_EMAIL")
    if not entity or not to_addr:
        return {"skipped": True}
    try:
        from src.agent.tools.composio_tools import get_composio_client, _execute_with_fallback
        client = get_composio_client()
        resp = _execute_with_fallback(
            "GMAIL_SEND_EMAIL",
            {
                "recipient_email": to_addr,
                "subject": f"FDWA briefing {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                "body": md,
                "is_html": False,
            },
            entity,
        )
        return {"success": bool(resp.get("successful")), "raw": resp.get("error")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run(state: dict) -> dict:
    """Graph entry — build the briefing and store it in state.

    Does NOT push to Telegram/Notion/GDocs directly; those nodes read
    `final_briefing_markdown` from state so they run in parallel after this.
    Gmail self-send fires here because there's no dedicated graph node for it.
    """
    md = build_briefing(state)
    # Provide a plain-text fallback for channels that don't need Markdown (Telegram)
    try:
        from src.agent.agents.content_agent import strip_markdown
        text = strip_markdown(md)
    except Exception:
        # best-effort fallback
        text = md.replace("#", "").replace("**", "")[:3500]

    gmail_result = _send_gmail(md)
    return {
        "final_briefing_markdown": md,
        "final_briefing_text": text[:3500],
        "briefing_title": f"FDWA run {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "briefing_gmail": gmail_result,
    }
