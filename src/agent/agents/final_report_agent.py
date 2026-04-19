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
                "twitter_url", "twitter_status", "facebook_status", "linkedin_status",
                "instagram_status", "telegram_status", "upload_post_status",
                "blog_status", "comment_status",
            ] if state.get(k)
        },
        "errors": state.get("error"),
    }


_SYSTEM_PROMPT = """You are the FDWA agent's end-of-run analyst. Build a comprehensive
post-run briefing in markdown that fully documents what THIS run did. Use ## headings
in this exact order:

## Run summary
One-paragraph narrative: what the agent set out to do, what topic/angle it chose,
and the outcome at a glance.

## Platforms posted
Per platform (Twitter, Facebook, LinkedIn, Instagram, Telegram, Upload-Post, Buffer,
Blog), list: status, URL if available, and a short preview of what was posted.

## Sources & data pulled
List every source this run pulled from: trend research APIs (SerpAPI/Tavily),
engagement reader (yesterday's FB/LI/IG/TG numbers), Mem0 recall, CoinMarketCap,
on-chain wallet snapshot, Google Analytics. For each, state exactly what was
retrieved (topics, counts, key figures).

## Google Analytics snapshot
Pull the GA metrics from context (sessions, top pages, conversions). If empty,
say "no GA data this run".

## Wallet + on-chain
Address, balance, network, any notable tx from the snapshot.

## Engagement learned
What yesterday's engagement told us and how it shaped today's content/topic pick.

## What's missing / failed
Every error or skipped step, with the cause from context.

## Next actions
3-6 concrete, specific next steps based on gaps in this run.

Use bullet points under each heading. Use REAL numbers from context only — if a
number isn't in the context, say "no data yet". No word limit, but be dense and
skimmable, not padded."""


def _synthesize(context: Dict[str, Any]) -> str:
    try:
        from src.agent.llm_router import route
    except Exception as e:
        return _fallback_briefing(context, f"router unavailable: {e}")

    try:
        llm = route(task="final_analysis", needs_long_context=True)
        prompt = _SYSTEM_PROMPT + "\n\nCONTEXT:\n" + json.dumps(context, default=str)[:12000]
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


def run(state: dict) -> dict:
    """Graph entry — build the briefing and store it in state.

    Does NOT push to Telegram/Notion/GDocs directly; those nodes read
    `final_briefing_markdown` from state so they run in parallel after this.
    Gmail self-send fires here because there's no dedicated graph node for it.
    """
    md = build_briefing(state)
    try:
        from src.agent.agents.content_agent import strip_markdown
        text = strip_markdown(md)
    except Exception:
        text = md.replace("#", "").replace("**", "")[:3500]

    return {
        "final_briefing_markdown": md,
        "final_briefing_text": text[:3500],
        "briefing_title": f"FDWA run {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
    }
