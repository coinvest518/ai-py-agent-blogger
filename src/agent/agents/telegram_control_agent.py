"""Telegram two-way control surface.

Long-polls TELEGRAM_GET_UPDATES, dispatches owner commands:

  /start    resume scheduler
  /stop     pause scheduler
  /status   dump agent_status.json
  /ask <q>  route through llm_router task="explain_self"
  /post <t> force graph run with topic override
  /brief    manually trigger final_report_agent

Only replies to messages whose chat id matches TELEGRAM_AI_OWNER_CHAT_ID.
Run as an asyncio background task (started from api.py lifespan).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.agent import telegram_agent

logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 5
LONG_POLL_TIMEOUT = 25
STATUS_FILE = Path("agent_status.json")
OFFSET_FILE = Path(".telegram_offset")


def _owner_chat_id() -> Optional[str]:
    raw = os.getenv("TELEGRAM_AI_OWNER_CHAT_ID") or os.getenv("TELEGRAM_GROUP_CHAT_ID")
    return str(raw).strip() if raw else None


def _load_offset() -> Optional[int]:
    try:
        if OFFSET_FILE.exists():
            return int(OFFSET_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        pass
    return None


def _save_offset(offset: int) -> None:
    try:
        OFFSET_FILE.write_text(str(offset), encoding="utf-8")
    except OSError as e:
        logger.debug("offset save failed: %s", e)


def _reply(chat_id: str, text: str) -> None:
    try:
        telegram_agent.send_message(chat_id=chat_id, text=text[:3900])
    except Exception as e:
        logger.warning("telegram reply failed: %s", e)


async def _handle_start(chat_id: str) -> None:
    from src.agent import scheduler as sched
    ok = sched.resume()
    _reply(chat_id, "▶️ Scheduler resumed." if ok else "⚠️ Scheduler not running.")


async def _handle_stop(chat_id: str) -> None:
    from src.agent import scheduler as sched
    ok = sched.pause()
    _reply(chat_id, "⏸️ Scheduler paused." if ok else "⚠️ Scheduler not running.")


def _format_status(data: Dict[str, Any]) -> str:
    """Render agent_status.json as a human-readable Telegram message."""
    if not data:
        return "No status recorded yet."
    results = data.get("results") or {}

    def _badge(val: Any) -> str:
        if not val:
            return "—"
        s = str(val)
        if s.lower().startswith(("posted", "sent", "commented", "success")):
            return "✅"
        if "error" in s.lower() or "fail" in s.lower() or "skip" in s.lower():
            return "⚠️"
        if s.startswith("http"):
            return "✅"
        return "✅"

    platforms = [
        ("Twitter", results.get("twitter") or results.get("twitter_url")),
        ("Facebook", results.get("facebook") or results.get("facebook_post_id")),
        ("LinkedIn", results.get("linkedin_status")),
        ("Instagram", results.get("instagram_status")),
        ("Telegram", results.get("telegram")),
        ("Comment", results.get("comment")),
        ("Blog", results.get("blog_status")),
    ]

    when = data.get("last_run") or "(no timestamp)"
    overall = data.get("status") or "?"
    lines = [
        f"📊 *FDWA status* — {overall}",
        f"🕒 Last run: {when}",
        "",
        "*Platforms*:",
    ]
    for name, val in platforms:
        if val is None:
            continue
        short = str(val)
        if len(short) > 60:
            short = short[:57] + "…"
        lines.append(f"  {_badge(val)} {name}: {short}")

    img = results.get("image")
    if img:
        lines += ["", f"🖼️ Image: {img}"]

    # Video (if available)
    vid = results.get("video") or results.get("video_url")
    if vid:
        short = str(vid)
        if len(short) > 200:
            short = short[:197] + "…"
        lines += ["", f"🎞️ Video: {short}"]

    tweet = results.get("tweet")
    if tweet:
        lines += ["", "*Caption preview*:", tweet[:320] + ("…" if len(tweet) > 320 else "")]

    return "\n".join(lines)


async def _handle_status(chat_id: str) -> None:
    try:
        if STATUS_FILE.exists():
            data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            text = _format_status(data)
        else:
            text = "No status recorded yet."
    except Exception as e:
        text = f"Status read failed: {e}"
    _reply(chat_id, text[:3800])


def _collect_self_context(question: str = "") -> Dict[str, Any]:
    """Gather live system context for /ask and /self — connections, LLMs, data.

    Best-effort everywhere; any failing probe returns a short error string
    instead of raising so the chat path never dies on a missing service.
    """
    ctx: Dict[str, Any] = {}

    # Last agent status (from disk)
    try:
        if STATUS_FILE.exists():
            ctx["last_run"] = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        ctx["last_run"] = f"read error: {e}"

    # LLM health — which providers have keys set, gated by DEAD/COOLDOWN flags
    try:
        from src.agent.llm_provider import (
            PROVIDER_REGISTRY,
            DEAD_PROVIDERS,
            COOLDOWN_PROVIDERS,
            _effective_env_value,
        )
        live: list[str] = []
        missing_keys: list[str] = []
        enable_flags = {
            "Cloudflare": os.getenv("CLOUDFLARE_ENABLE", "false").lower() in ("1", "true", "yes"),
            "HuggingFace": os.getenv("HF_ENABLE", "false").lower() in ("1", "true", "yes"),
            "Cerebras": os.getenv("CEREBRAS_ENABLE", "false").lower() in ("1", "true", "yes"),
            "Moonshot": os.getenv("MOONSHOT_ENABLE", "false").lower() in ("1", "true", "yes"),
            "Google": os.getenv("GOOGLE_ENABLE", "false").lower() in ("1", "true", "yes"),
            "Qwen": os.getenv("QWEN_ENABLE", "false").lower() in ("1", "true", "yes"),
        }
        for name, env_key, _, _ in PROVIDER_REGISTRY:
            if not _effective_env_value(env_key):
                missing_keys.append(name)
                continue
            if name in DEAD_PROVIDERS and not enable_flags.get(name, False):
                continue
            if name in COOLDOWN_PROVIDERS and not enable_flags.get(name, False):
                continue
            live.append(name)
        ctx["llms"] = {
            "live": live,
            "dead": list(DEAD_PROVIDERS.keys()),
            "cooldown": list(COOLDOWN_PROVIDERS.keys()),
            "missing_keys": missing_keys,
        }
    except Exception as e:
        ctx["llms"] = f"probe error: {e}"

    # Buffer channels (live query — uses in-process cache, cheap)
    try:
        from src.agent.agents import buffer_agent
        if buffer_agent._token():
            channels = buffer_agent.list_channels()
            ctx["buffer_channels"] = [
                {"service": c.get("service"), "name": c.get("name"), "id": (c.get("id") or "")[:10] + "…"}
                for c in channels
            ]
        else:
            ctx["buffer_channels"] = "BUFFER_API_KEY not set"
    except Exception as e:
        ctx["buffer_channels"] = f"probe error: {e}"

    # Composio auth surface — which toolkits' entity_id is configured
    comp: Dict[str, Any] = {}
    for key in (
        "COMPOSIO_ENTITY_ID", "COMPOSIO_USER_ID", "COMPOSIO_GOOGLE_DOCS_ACCOUNT_ID",
        "GA_PROPERTY_ID", "GOOGLEDOCS_WEEKLY_DOC_ID",
    ):
        comp[key] = "set" if os.getenv(key) else "missing"
    ctx["composio_env"] = comp

    # Direct API keys — just presence flags, never values
    keys: Dict[str, Any] = {}
    for key in (
        "BUFFER_API_KEY", "NVIDIA_API_KEY", "MISTRAL_API_KEY", "MISTRAL_IMAGE_API_KEY",
        "MEM0_API_KEY", "OPENROUTER_API_KEY", "NEBIUS_API_KEY",
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_AI_OWNER_CHAT_ID",
    ):
        keys[key] = "set" if os.getenv(key) else "missing"
    ctx["api_keys"] = keys

    # GA prior snapshot (written by ga_snapshot_node each cycle)
    try:
        from src.agent.agents import strategy_agent
        prev = strategy_agent._load_prev_ga()
        ctx["ga_prev_prose"] = strategy_agent._ga_to_prose(prev) or "(no prior snapshot)"
    except Exception as e:
        ctx["ga_prev_prose"] = f"probe error: {e}"

    # Engagement cache (6h TTL)
    try:
        cache_path = Path(os.getenv("ENGAGEMENT_CACHE_PATH", ".engagement_cache.json"))
        if cache_path.exists():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            ctx["engagement_summary"] = (payload.get("summary") or "")[:500]
        else:
            ctx["engagement_summary"] = "(not yet pulled this TTL window)"
    except Exception as e:
        ctx["engagement_summary"] = f"read error: {e}"

    # Mem0 recall relevant to the question
    try:
        from src.agent import mem0_adapter
        hits = mem0_adapter.recall_relevant(question or "recent activity", top_k=5) or []
        ctx["memory"] = [
            (h.get("memory") or h.get("text") or "")[:180]
            for h in hits if isinstance(h, dict)
        ]
    except Exception as e:
        ctx["memory"] = f"probe error: {e}"

    # Graph capabilities — what nodes exist
    try:
        from src.agent.graph import workflow
        ctx["graph_nodes"] = sorted(list(workflow.nodes.keys()))
    except Exception as e:
        ctx["graph_nodes"] = f"probe error: {e}"

    return ctx


def _format_self_dump(ctx: Dict[str, Any]) -> str:
    """Render the context dict as a compact text block for Telegram."""
    lines = ["🔎 FDWA self-introspection", ""]

    llms = ctx.get("llms") or {}
    if isinstance(llms, dict):
        lines.append(f"LLMs live: {', '.join(llms.get('live', [])[:8]) or '(none)'}")
        if llms.get("dead"):
            lines.append(f"LLMs dead: {', '.join(llms['dead'])}")
        if llms.get("cooldown"):
            lines.append(f"LLMs cooldown: {', '.join(llms['cooldown'])}")

    chans = ctx.get("buffer_channels")
    if isinstance(chans, list):
        if chans:
            lines.append(f"Buffer channels ({len(chans)}):")
            for c in chans[:12]:
                lines.append(f"  • {c.get('service')}: {c.get('name')}")
        else:
            lines.append("Buffer channels: (none connected)")
    else:
        lines.append(f"Buffer: {chans}")

    comp = ctx.get("composio_env") or {}
    missing = [k for k, v in comp.items() if v == "missing"]
    lines.append(f"Composio env: {len(comp) - len(missing)}/{len(comp)} set" + (f" — missing: {', '.join(missing)}" if missing else ""))

    keys = ctx.get("api_keys") or {}
    km = [k for k, v in keys.items() if v == "missing"]
    lines.append(f"API keys: {len(keys) - len(km)}/{len(keys)} set" + (f" — missing: {', '.join(km)}" if km else ""))

    lines.append(f"GA prior: {ctx.get('ga_prev_prose', '?')}")
    lines.append(f"Engagement: {str(ctx.get('engagement_summary', '?'))[:240]}")

    nodes = ctx.get("graph_nodes")
    if isinstance(nodes, list):
        lines.append(f"Graph nodes ({len(nodes)}): {', '.join(nodes[:20])}{'…' if len(nodes) > 20 else ''}")

    mem = ctx.get("memory") or []
    if isinstance(mem, list) and mem:
        lines.append("Memory recall:")
        for m in mem[:4]:
            lines.append(f"  • {m}")

    return "\n".join(lines)


async def _handle_self(chat_id: str) -> None:
    """Dump the raw introspection so the operator can see what the agent sees."""
    try:
        ctx = _collect_self_context(question="")
        _reply(chat_id, _format_self_dump(ctx))
    except Exception as e:
        logger.exception("self failed")
        _reply(chat_id, f"/self failed: {e}")


async def _handle_ask(chat_id: str, question: str) -> None:
    if not question.strip():
        _reply(chat_id, "Usage: /ask <question about connections, data, capabilities>")
        return
    try:
        from src.agent.llm_router import route

        ctx = _collect_self_context(question=question)

        system = (
            "You are the FDWA agent answering the operator on Telegram. You have "
            "real introspection data below — connections, LLM health, Buffer channels, "
            "GA traffic, engagement, memory. Answer from THAT DATA. Be concrete and "
            "short. If the data doesn't answer the question, say so — don't hallucinate."
        )
        data_block = json.dumps(ctx, default=str, indent=2)[:6000]
        user = (
            f"QUESTION: {question}\n\n"
            f"LIVE SYSTEM DATA:\n{data_block}"
        )

        from langchain_core.messages import SystemMessage, HumanMessage
        llm = route(task="explain_self", needs_long_context=True)
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        text = getattr(resp, "content", None) or str(resp)
        _reply(chat_id, text.strip()[:3800])
    except Exception as e:
        logger.exception("ask failed")
        _reply(chat_id, f"/ask failed: {e}")


def _badge(val: str) -> str:
    v = str(val or "").lower()
    if not v or v in ("n/a", "missing"):
        return "⚠️"
    if "skipped" in v or "skip" in v:
        return "⏭️"
    if "fail" in v or "error" in v or "expired" in v:
        return "❌"
    return "✅"


def _build_run_summary(result: dict, topic: str = "") -> str:
    """Same structured per-platform summary used by the scheduler."""
    fb = result.get("facebook_status") or (f"Posted: {result.get('facebook_post_id')}" if result.get("facebook_post_id") else "missing")
    tw = "skipped_by_config" if result.get("twitter_post_id") == "skipped_by_config" else (f"Posted: {result.get('twitter_url')}" if result.get("twitter_url") else "missing")
    li = result.get("linkedin_status") or "missing"
    ig = result.get("instagram_status") or "missing"
    tg = result.get("telegram_status") or "missing"
    blog = result.get("blog_status") or "missing"
    buf = result.get("buffer_status") or "missing"
    gdoc_url = result.get("gdocs_url") or ""
    gdoc_status = result.get("gdocs_status") or "missing"

    header = f"🤖 FDWA Agent run — {datetime.utcnow().isoformat()}Z"
    if topic:
        header += f"\n📌 Topic: {topic[:100]}"
    lines = [
        header,
        f"{_badge(fb)} facebook: {str(fb)[:120]}",
        f"{_badge(tw)} twitter: {str(tw)[:120]}",
        f"{_badge(li)} linkedin: {str(li)[:120]}",
        f"{_badge(ig)} instagram: {str(ig)[:120]}",
        f"{_badge(tg)} telegram: {str(tg)[:120]}",
        f"{_badge(blog)} blog: {str(blog)[:120]}",
        f"{_badge(buf)} buffer: {str(buf)[:120]}",
    ]
    if gdoc_url:
        lines.append(f"📄 gdoc: {gdoc_url}")
    else:
        lines.append(f"📄 gdoc: {str(gdoc_status)[:120]}")
    if result.get("error"):
        lines.append(f"⚠️ graph_error: {str(result.get('error'))[:200]}")
    return "\n".join(lines)


async def _handle_post(chat_id: str, topic: str) -> None:
    if not topic.strip():
        _reply(chat_id, "Usage: /post <topic>")
        return
    _reply(chat_id, f"🚀 Launching graph run with topic override: {topic[:120]}")
    try:
        from src.agent.graph import graph
        loop = asyncio.get_event_loop()
        state = {"topic_override": topic, "trend_data": topic}
        result = await loop.run_in_executor(None, lambda: graph.invoke(state))
        _reply(chat_id, _build_run_summary(result, topic=topic))
    except Exception as e:
        logger.exception("forced post failed")
        _reply(chat_id, f"/post failed: {e}")


async def _handle_brief(chat_id: str) -> None:
    try:
        from src.agent.agents import final_report_agent, gdocs_agent
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: final_report_agent.run({}))
        md = result.get("final_briefing_markdown", "(empty briefing)")
        _reply(chat_id, md[:3500])
        try:
            doc_result = await loop.run_in_executor(
                None, lambda: gdocs_agent.run({"final_briefing_markdown": md})
            )
            doc_url = doc_result.get("gdocs_url")
            if doc_url:
                _reply(chat_id, f"📄 Google Doc: {doc_url}")
            else:
                _reply(chat_id, f"📄 {doc_result.get('gdocs_status', 'gdoc not written')}")
        except Exception as doc_e:
            logger.exception("brief gdoc failed")
            _reply(chat_id, f"📄 gdoc failed: {doc_e}")
    except Exception as e:
        logger.exception("brief failed")
        _reply(chat_id, f"/brief failed: {e}")


async def _handle_jobs(chat_id: str) -> None:
    try:
        from src.agent import scheduler as sched
        jobs = sched.list_jobs() or []
        if not jobs:
            _reply(chat_id, "No custom scheduler jobs (default 6h tick still active).")
            return
        lines = ["📅 Scheduler jobs:"]
        for j in jobs:
            badge = "✓" if j.get("enabled", True) else "⏸"
            when = j.get("cron") or f"every {j.get('minutes')}m"
            lines.append(f"{badge} `{j.get('id')}` — {when} topic={j.get('topic', '-')}")
        _reply(chat_id, "\n".join(lines))
    except Exception as e:
        _reply(chat_id, f"/jobs failed: {e}")


async def _handle_schedule(chat_id: str, text: str) -> None:
    if not text.strip():
        _reply(chat_id, "Usage: /schedule <natural language> [topic]\nExample: /schedule every day at 9am crypto")
        return
    try:
        from src.agent.agents.schedule_nlp_agent import parse_nl
        from src.agent import scheduler as sched
        spec = parse_nl(text)
        if spec.get("error"):
            _reply(chat_id, f"⚠️ Could not parse: {spec['error']}")
            return
        stored = sched.add_job_from_spec(spec)
        readable = stored.get("cron") or f"every {stored.get('minutes')}m"
        _reply(chat_id, f"✅ Scheduled `{stored['id']}` — {readable} topic={stored.get('topic', '-')}")
    except Exception as e:
        logger.exception("/schedule failed")
        _reply(chat_id, f"/schedule failed: {e}")


async def _handle_unschedule(chat_id: str, job_id: str) -> None:
    if not job_id.strip():
        _reply(chat_id, "Usage: /unschedule <job_id>")
        return
    try:
        from src.agent import scheduler as sched
        ok = sched.remove_job(job_id.strip())
        _reply(chat_id, "🗑️ Job removed." if ok else "⚠️ Job not found or scheduler not running.")
    except Exception as e:
        _reply(chat_id, f"/unschedule failed: {e}")


# Single-platform post: /post_<platform> <caption>. If no caption, reuses the
# last refined `tweet_text` from agent_status.json.
_PLATFORM_AGENTS = {
    "twitter": "twitter_agent_v2",
    "facebook": "facebook_agent",
    "linkedin": "linkedin_agent_v2",
    "instagram": "instagram_agent_v2",
    "telegram": "telegram_agent_v2",
    "blog": "blog_agent",
}


async def _handle_platform_post(chat_id: str, platform: str, caption: str) -> None:
    platform = platform.lower().strip()
    mod_name = _PLATFORM_AGENTS.get(platform)
    if not mod_name:
        _reply(chat_id, f"Unknown platform '{platform}'. Valid: {', '.join(_PLATFORM_AGENTS)}")
        return
    _reply(chat_id, f"🚀 Posting to {platform}" + (f" with your caption…" if caption.strip() else "…"))
    try:
        import importlib
        mod = importlib.import_module(f"src.agent.agents.{mod_name}")
        runner = getattr(mod, "run", None)
        if not callable(runner):
            _reply(chat_id, f"{platform} agent has no .run(state)")
            return

        state: Dict[str, Any] = {}
        try:
            if STATUS_FILE.exists():
                snap = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
                state = dict((snap.get("results") or {}))
        except Exception:
            pass
        if caption.strip():
            state["tweet_text"] = caption.strip()
            state["base_insights"] = caption.strip()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: runner(state))
        text = result.get(f"{platform}_status") or result.get(f"{platform}_url") or str(result)[:300]
        _reply(chat_id, f"✅ {platform}: {text}")
    except Exception as e:
        logger.exception("%s post failed", platform)
        _reply(chat_id, f"/post_{platform} failed: {e}")


async def _handle_exec(chat_id: str, spec: str) -> None:
    """`/exec TOOL_SLUG {"arg": "value"}` — run any Composio tool."""
    spec = spec.strip()
    if not spec:
        _reply(chat_id, 'Usage: /exec <TOOL_SLUG> {"arg":"value"}\nExample: /exec GMAIL_SEND_EMAIL {"to":"x@y.com","subject":"hi","body":"hey"}')
        return
    slug, _, rest = spec.partition(" ")
    slug = slug.upper().strip()
    args: Dict[str, Any] = {}
    if rest.strip():
        try:
            args = json.loads(rest)
            if not isinstance(args, dict):
                _reply(chat_id, "arguments must be a JSON object")
                return
        except Exception as e:
            _reply(chat_id, f"Bad JSON: {e}")
            return
    try:
        from src.agent.tools.composio_tools import get_composio_client, _execute_with_fallback
        c = get_composio_client()
        user_id = os.environ.get("COMPOSIO_ENTITY_ID")
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, lambda: _execute_with_fallback(slug, args, user_id))
        blurb = json.dumps(resp, default=str)[:3500] if isinstance(resp, dict) else str(resp)[:3500]
        _reply(chat_id, f"🛠️ {slug}\n```\n{blurb}\n```")
    except Exception as e:
        logger.exception("/exec failed")
        _reply(chat_id, f"/exec {slug} failed: {e}")


async def _handle_tools(chat_id: str, toolkit: str) -> None:
    """`/tools [toolkit]` — list toolkits, or tool slugs for a given toolkit."""
    try:
        from src.agent.tools.composio_tools import get_composio_client
        c = get_composio_client()
        if not toolkit.strip():
            rows = c.toolkits.list()
            items = getattr(rows, "items", None) or rows
            names = sorted({getattr(r, "slug", None) or getattr(r, "name", str(r)) for r in (items or [])})
            _reply(chat_id, "🧰 Toolkits:\n" + "\n".join(f"- {n}" for n in names[:50]))
            return
        rows = c.tools.get_raw_composio_tools(toolkits=[toolkit.strip().lower()])
        slugs = sorted({getattr(r, "slug", None) or getattr(r, "name", str(r)) for r in (rows or [])})
        if not slugs:
            _reply(chat_id, f"No tools for toolkit '{toolkit}'.")
            return
        _reply(chat_id, f"🧰 {toolkit} — {len(slugs)} tools:\n" + "\n".join(f"- {s}" for s in slugs[:60]))
    except Exception as e:
        _reply(chat_id, f"/tools failed: {e}")


async def _handle_buffer_now(chat_id: str, text: str) -> None:
    """Post immediately to every Buffer channel (routes by service type)."""
    if not text.strip():
        _reply(chat_id, "Usage: /buffer_now <text>")
        return
    try:
        from src.agent.agents import buffer_agent
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: buffer_agent.post_now(text=text))
        by_service = result.get("by_service") or {}
        parts = [f"🎯 Buffer immediate post"]
        if result.get("success"):
            parts.append(f"✅ Queued {len(result.get('post_ids') or [])} post(s)")
        else:
            parts.append(f"❌ {result.get('error', 'unknown')[:200]}")
        if by_service:
            parts.append("Services: " + ", ".join(f"{k}={v}" for k, v in by_service.items()))
        _reply(chat_id, "\n".join(parts))
    except Exception as e:
        logger.exception("buffer_now failed")
        _reply(chat_id, f"/buffer_now failed: {e}")


async def _handle_buffer_schedule(chat_id: str, text: str) -> None:
    """Schedule a Buffer post. Usage: /buffer_schedule <ISO-8601> | <text>"""
    if "|" not in text:
        _reply(chat_id, "Usage: /buffer_schedule <ISO-8601 UTC> | <text>\nExample: /buffer_schedule 2026-04-16T15:00:00.000Z | Hello from the future")
        return
    when, _, body = text.partition("|")
    when, body = when.strip(), body.strip()
    if not when or not body:
        _reply(chat_id, "Usage: /buffer_schedule <ISO-8601 UTC> | <text>")
        return
    try:
        from src.agent.agents import buffer_agent
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: buffer_agent.schedule_post(text=body, when=when))
        if result.get("success"):
            by_service = result.get("by_service") or {}
            svc = ", ".join(f"{k}={v}" for k, v in by_service.items())
            _reply(chat_id, f"⏰ Scheduled for {when}\nServices: {svc}\nPost IDs: {len(result.get('post_ids') or [])}")
        else:
            _reply(chat_id, f"❌ Schedule failed: {result.get('error', 'unknown')[:200]}")
    except Exception as e:
        logger.exception("buffer_schedule failed")
        _reply(chat_id, f"/buffer_schedule failed: {e}")


_COMMANDS = {
    "/start": _handle_start,
    "/stop": _handle_stop,
    "/status": _handle_status,
    "/brief": _handle_brief,
    "/jobs": _handle_jobs,
    "/self": _handle_self,
}
_ARG_COMMANDS = {
    "/ask": _handle_ask,
    "/post": _handle_post,
    "/schedule": _handle_schedule,
    "/unschedule": _handle_unschedule,
    "/exec": _handle_exec,
    "/tools": _handle_tools,
    "/buffer_now": _handle_buffer_now,
    "/buffer_schedule": _handle_buffer_schedule,
}


async def _dispatch(text: str, chat_id: str) -> None:
    text = text.strip()
    if not text.startswith("/"):
        return
    head, _, tail = text.partition(" ")
    head = head.split("@", 1)[0].lower()

    # /post_<platform> <caption> — single-platform posting
    if head.startswith("/post_"):
        platform = head[len("/post_"):]
        await _handle_platform_post(chat_id, platform, tail)
        return

    if head in _COMMANDS:
        await _COMMANDS[head](chat_id)
    elif head in _ARG_COMMANDS:
        await _ARG_COMMANDS[head](chat_id, tail)
    else:
        _reply(
            chat_id,
            "Commands:\n"
            "/start /stop /status /brief /jobs /self\n"
            "/ask <q>              — chat with the agent about connections, data, capabilities\n"
            "/self                 — raw dump: LLMs, Buffer channels, Composio env, GA, memory\n"
            "/post <topic>         — run full graph with a topic\n"
            "/post_<platform> [caption]  — single-platform post (twitter/facebook/linkedin/instagram/telegram/blog)\n"
            "/schedule <nl>        — add a cron job from natural language\n"
            "/unschedule <id>      — remove a job\n"
            "/tools [toolkit]      — list Composio toolkits / tool slugs\n"
            "/exec <SLUG> {json}   — call any Composio tool\n"
            "/buffer_now <text>    — immediate Buffer post to every channel (routes images/video per service)\n"
            "/buffer_schedule <ISO> | <text> — schedule a Buffer post (e.g. 2026-04-16T15:00:00.000Z | hello)"
        )


def _extract_message(update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for key in ("message", "channel_post", "edited_message"):
        msg = update.get(key)
        if isinstance(msg, dict):
            return msg
    return None


async def poll_loop() -> None:
    """Main long-poll loop. Start as an asyncio task."""
    owner = _owner_chat_id()
    if not owner:
        logger.warning("TELEGRAM_AI_OWNER_CHAT_ID not set — control bot disabled")
        return
    logger.info("Telegram control bot started (owner=%s)", owner)

    offset = _load_offset()
    logger.debug("Telegram poll loop initial offset=%s", offset)
    print(f"TELEGRAM_POLL bootstrap: initial offset={offset}")
    while True:
        try:
            logger.debug("Calling telegram_agent.get_updates offset=%s limit=%s timeout=%s", offset, 50, LONG_POLL_TIMEOUT)
            print(f"TELEGRAM_POLL calling get_updates offset={offset} timeout={LONG_POLL_TIMEOUT}")
            resp = await asyncio.to_thread(
                telegram_agent.get_updates,
                offset=offset,
                limit=50,
                timeout=LONG_POLL_TIMEOUT,
            )
            # Make debugging easier: log raw response shape (trim long text)
            try:
                if isinstance(resp, dict):
                    logger.debug("get_updates response keys=%s", list(resp.keys()))
                    print(f"TELEGRAM_POLL get_updates keys={list(resp.keys())}")
                else:
                    logger.debug("get_updates returned non-dict: %s", type(resp))
                    print(f"TELEGRAM_POLL get_updates returned non-dict: {type(resp)}")
            except Exception:
                logger.debug("get_updates response logging failed")
                print("TELEGRAM_POLL get_updates response logging failed")
            if not resp.get("success"):
                logger.warning("get_updates failed or returned no success: %s", resp)
                print(f"TELEGRAM_POLL get_updates failed: {resp}")
                await asyncio.sleep(POLL_INTERVAL_SEC * 3)
                continue
            updates = (resp.get("data") or {}).get("result") or []
            logger.debug("get_updates fetched %d updates", len(updates))
            print(f"TELEGRAM_POLL fetched {len(updates)} updates")
            for upd in updates:
                logger.debug("processing update id=%s", upd.get("update_id"))
                print(f"TELEGRAM_POLL processing update id={upd.get('update_id')}")
                offset = max(offset or 0, int(upd.get("update_id", 0)) + 1)
                msg = _extract_message(upd)
                if not msg:
                    continue
                chat = msg.get("chat") or {}
                incoming = str(chat.get("id") or chat.get("username") or "")
                if incoming and owner and incoming not in {owner, owner.lstrip("@")}:
                    logger.debug("ignored telegram msg from non-owner chat %s", incoming)
                    continue
                text = (msg.get("text") or "").strip()
                if not text:
                    continue
                reply_chat = str(chat.get("id") or owner)
                try:
                    await _dispatch(text, reply_chat)
                except Exception as e:
                    logger.exception("command dispatch failed")
                    _reply(reply_chat, f"command failed: {e}")
            if updates:
                _save_offset(offset or 0)
        except asyncio.CancelledError:
            logger.info("Telegram control bot cancelled")
            raise
        except Exception as e:
            logger.warning("poll iteration error: %s", e)
            await asyncio.sleep(POLL_INTERVAL_SEC * 2)
        await asyncio.sleep(POLL_INTERVAL_SEC)


_task: Optional[asyncio.Task] = None


def start_background_task(loop: Optional[asyncio.AbstractEventLoop] = None) -> Optional[asyncio.Task]:
    """Spawn the poll loop on the given (or running) loop. Idempotent."""
    global _task
    if _task and not _task.done():
        return _task
    if not _owner_chat_id():
        logger.info("telegram control bot skipped — no TELEGRAM_AI_OWNER_CHAT_ID")
        return None
    loop = loop or asyncio.get_event_loop()
    _task = loop.create_task(poll_loop(), name="telegram_control_poll")
    return _task


async def stop_background_task() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except (asyncio.CancelledError, Exception):
            pass
    _task = None
