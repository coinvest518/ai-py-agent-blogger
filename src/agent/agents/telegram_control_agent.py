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


async def _handle_ask(chat_id: str, question: str) -> None:
    if not question.strip():
        _reply(chat_id, "Usage: /ask <question>")
        return
    try:
        from src.agent.llm_router import route
        from src.agent import mem0_adapter

        memories = []
        try:
            hits = mem0_adapter.recall_relevant(question, top_k=3) or []
            for h in hits:
                if isinstance(h, dict):
                    memories.append((h.get("memory") or h.get("text") or "")[:200])
        except Exception:
            pass

        status_txt = ""
        try:
            if STATUS_FILE.exists():
                status_txt = STATUS_FILE.read_text(encoding="utf-8")[:1500]
        except Exception:
            pass

        prompt = (
            "You are the FDWA agent answering the operator on Telegram. "
            "Be concrete, short, reference real events when the data supports it.\n\n"
            f"QUESTION: {question}\n\n"
            f"AGENT STATUS:\n{status_txt or '(none)'}\n\n"
            f"MEMORY:\n" + ("\n".join(f"- {m}" for m in memories) if memories else "(none)")
        )
        llm = route(task="explain_self", needs_long_context=True)
        resp = llm.invoke(prompt)
        text = getattr(resp, "content", None) or str(resp)
        _reply(chat_id, text.strip())
    except Exception as e:
        logger.exception("ask failed")
        _reply(chat_id, f"/ask failed: {e}")


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
        summary = (
            f"Run done at {datetime.utcnow().isoformat()}Z.\n"
            f"twitter: {'✓' if result.get('twitter_url') else '×'}  "
            f"fb: {'✓' if result.get('facebook_post_id') else '×'}  "
            f"li: {str(result.get('linkedin_status',''))[:30]}  "
            f"ig: {str(result.get('instagram_status',''))[:30]}  "
            f"blog: {str(result.get('blog_status',''))[:30]}"
        )
        _reply(chat_id, summary)
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


_COMMANDS = {
    "/start": _handle_start,
    "/stop": _handle_stop,
    "/status": _handle_status,
    "/brief": _handle_brief,
    "/jobs": _handle_jobs,
}
_ARG_COMMANDS = {
    "/ask": _handle_ask,
    "/post": _handle_post,
    "/schedule": _handle_schedule,
    "/unschedule": _handle_unschedule,
    "/exec": _handle_exec,
    "/tools": _handle_tools,
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
            "/start /stop /status /brief /jobs\n"
            "/ask <q>              — ask the agent about itself\n"
            "/post <topic>         — run full graph with a topic\n"
            "/post_<platform> [caption]  — single-platform post (twitter/facebook/linkedin/instagram/telegram/blog)\n"
            "/schedule <nl>        — add a cron job from natural language\n"
            "/unschedule <id>      — remove a job\n"
            "/tools [toolkit]      — list Composio toolkits / tool slugs\n"
            "/exec <SLUG> {json}   — call any Composio tool"
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
