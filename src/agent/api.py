"""FastAPI application for running the FDWA agent."""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langserve import add_routes

# Load environment variables FIRST before importing graph
repo_root = Path(__file__).resolve().parents[3]
load_dotenv(repo_root / ".env")

from src.agent.blog_email_agent import (  # noqa: E402
    _load_business_profile,
    generate_and_send_blog,
    update_business_profile_from_shop,
)
from src.agent.graph import graph  # noqa: E402
from src.agent.realtime_status import broadcaster  # noqa: E402
from src.agent.scheduler import (  # noqa: E402
    get_status,
    run_agent_task,
    start_scheduler,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="FDWA Social Media Agent")

# Mount static files from templates directory for CSS/JS
templates_dir = Path(__file__).parent.parent.parent / "templates"
app.mount("/static", StaticFiles(directory=str(templates_dir)), name="static")

# Add LangServe route for LangSmith Studio
add_routes(app, graph, path="/agent")

scheduler = None


# ---------------------------------------------------------------------------
# Individual agent runner helper
# ---------------------------------------------------------------------------
_AGENT_RUNNERS = {}


def _lazy_load_agents():
    """Lazily import agent runners to avoid slow startup."""
    if _AGENT_RUNNERS:
        return
    try:
        from src.agent.agents import (  # noqa: F401
            research_agent, facebook_agent,
            blog_agent, memory_agent, content_agent, comment_agent,
            content_refiner_agent, sentiment_agent, analytics_agent,
            upload_post_agent, notion_agent, gdocs_agent, ganalytics_agent,
            onchain_agent, final_report_agent, engagement_reader_agent,
            supervisor_agent,
        )
        from src.agent.agents import linkedin_agent_v2 as linkedin_agent  # noqa
        from src.agent.agents import instagram_agent_v2 as instagram_agent  # noqa
        from src.agent.agents import telegram_agent_v2 as telegram_agent  # noqa

        _AGENT_RUNNERS.update({
            "supervisor_plan": ("Supervisor Plan", supervisor_agent.plan),
            "pull_engagement": ("Pull Engagement", engagement_reader_agent.run),
            "research": ("Research Trends", lambda st: {"trend_data": research_agent.research_trends().get("trend_data", ""), "source": "manual"}),
            "content": ("Generate Content", content_agent.run),
            "refine_content": ("Refine Content", content_refiner_agent.run),
            "sentiment": ("Sentiment", sentiment_agent.run),
            "twitter": ("Twitter (via upload-post)", upload_post_agent.run),
            "facebook": ("Facebook Post", facebook_agent.run),
            "linkedin": ("LinkedIn Post", linkedin_agent.run),
            "instagram": ("Instagram Post", instagram_agent.run),
            "telegram": ("Telegram Post", telegram_agent.run),
            "upload_post": ("Upload-Post", upload_post_agent.run),
            "ga_snapshot": ("Google Analytics", ganalytics_agent.run),
            "onchain": ("On-Chain", onchain_agent.run),
            "final_report": ("Final Report", final_report_agent.run),
            "notion": ("Notion", notion_agent.run),
            "gdocs": ("Google Docs", gdocs_agent.run),
            "comment": ("Comment/Reply", comment_agent.monitor_instagram),
            "blog": ("Blog/Email", blog_agent.run),
            "analytics": ("Analytics", analytics_agent.run),
            "memory": ("Memory Save", memory_agent.run),
            "supervisor_reflect": ("Supervisor Reflect", supervisor_agent.reflect),
        })
    except Exception as e:
        logger.warning("Failed to lazy-load agent runners: %s", e)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the UI homepage."""
    template_path = Path(__file__).parent.parent.parent / "templates" / "index.html"
    with open(template_path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Status & Stream
# ---------------------------------------------------------------------------

@app.get("/status")
async def status():
    """Get current agent status."""
    return get_status()


@app.get("/stream")
async def stream_status():
    """Stream real-time agent status updates via Server-Sent Events."""
    async def event_generator():
        queue = broadcaster.add_client()
        try:
            yield "data: {'type': 'connected', 'message': 'Connected to agent stream'}\n\n"
            for event in broadcaster.get_history():
                yield f"data: {event}\n\n"
            while True:
                event = await queue.get()
                yield f"data: {event}\n\n"
        except asyncio.CancelledError:
            broadcaster.remove_client(queue)
            raise
        except Exception as e:
            logger.error("Stream error: %s", e)
            broadcaster.remove_client(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Full Agent Run
# ---------------------------------------------------------------------------

@app.post("/run")
async def run_agent():
    """Manually trigger full agent pipeline."""
    result = await run_agent_task()
    return result


# ---------------------------------------------------------------------------
# Individual Agent Run
# ---------------------------------------------------------------------------

@app.get("/agent/list")
async def list_agents():
    """List every runnable subagent id for the dashboard."""
    _lazy_load_agents()
    return {"agents": [{"id": k, "label": v[0]} for k, v in sorted(_AGENT_RUNNERS.items())]}


@app.post("/memory/search")
async def memory_search(payload: dict):
    """Search Mem0 for relevant memories."""
    query = (payload or {}).get("query", "").strip()
    user_id = (payload or {}).get("user_id", "fdwa_agent")
    top_k = int((payload or {}).get("top_k", 5))
    if not query:
        return {"error": "query required"}
    try:
        from src.agent import mem0_adapter
        hits = mem0_adapter.recall_relevant(query=query, top_k=top_k, user_id=user_id) or []
        return {"hits": hits, "count": len(hits)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/engagement/fetch")
async def engagement_fetch(payload: dict | None = None):
    """Force-refresh engagement snapshot (bypasses 6h cache if force=true)."""
    force = bool((payload or {}).get("force", True))
    try:
        from src.agent.agents.engagement_reader_agent import read_yesterday
        return read_yesterday(force=force)
    except Exception as e:
        return {"error": str(e)}


@app.get("/reasoning/last")
async def reasoning_last():
    """Return the most recent supervisor plan + reflection from Mem0."""
    try:
        from src.agent import mem0_adapter
        plan_hits = mem0_adapter.recall_relevant("supervisor plan", top_k=3) or []
        reflect_hits = mem0_adapter.recall_relevant("supervisor_reflection", top_k=3) or []
        return {"plan": plan_hits, "reflection": reflect_hits}
    except Exception as e:
        return {"error": str(e)}


@app.post("/agent/run/{agent_id}")
async def run_single_agent(agent_id: str, request: Request):
    """Run a single agent by ID with optional state overrides.

    POST body (all optional):
      {
        "overrides": {
          "tweet_text": "Custom caption text…",
          "topic_override": "AI automation",
          "trend_data": "…",
          "image_url": "https://…",
          "video_url": "https://…",
          "base_insights": "…"
        }
      }

    Overrides are merged onto the snapshot from the last full run so per-platform
    posts can be made without re-running the whole graph.
    """
    _lazy_load_agents()
    if agent_id not in _AGENT_RUNNERS:
        return JSONResponse({"success": False, "error": f"Unknown agent: {agent_id}"}, status_code=404)

    try:
        body = await request.json()
    except Exception:
        body = {}
    overrides = (body or {}).get("overrides") or {}

    label, runner = _AGENT_RUNNERS[agent_id]
    try:
        current = get_status()
        state = dict(current.get("results", {}))
        state.setdefault("base_insights", state.get("tweet", "No insights available"))
        state.setdefault("trend_data", "")
        state.setdefault("ai_strategy", {})
        state.setdefault("image_url", state.get("image", ""))

        if isinstance(overrides, dict):
            for key, value in overrides.items():
                if value is not None and value != "":
                    state[key] = value
            if overrides.get("tweet_text") and not state.get("base_insights"):
                state["base_insights"] = overrides["tweet_text"]

        await broadcaster.update(f"Running {label} agent…")
        result = runner(state)
        await broadcaster.update(f"{label} agent completed")
        return {"success": True, "agent": agent_id, "overrides_applied": list(overrides.keys()) if overrides else [], "result": result}
    except Exception as e:
        logger.exception("Single agent %s failed", agent_id)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Direct Composio tool execution + discovery
# ---------------------------------------------------------------------------

@app.get("/composio/toolkits")
async def composio_toolkits():
    """List every Composio toolkit available to the agent's API key."""
    try:
        from src.agent.tools.composio_tools import get_composio_client
        c = get_composio_client()
        rows = c.toolkits.list()
        items = getattr(rows, "items", None) or rows
        return {"toolkits": [
            {
                "slug": getattr(r, "slug", None) or getattr(r, "name", str(r)),
                "name": getattr(r, "name", None),
            } for r in (items or [])
        ]}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/composio/tools")
async def composio_tools_list(toolkit: str | None = None, limit: int = 100):
    """List tool slugs (optionally filtered to one toolkit like 'googlesheets')."""
    try:
        from src.agent.tools.composio_tools import get_composio_client
        c = get_composio_client()
        rows = c.tools.get_raw_composio_tools(toolkits=[toolkit] if toolkit else None)
        out = []
        for r in rows or []:
            tkit = getattr(r, "toolkit", None)
            tkit_slug = getattr(tkit, "slug", None) or (tkit if isinstance(tkit, str) else "")
            out.append({
                "slug": getattr(r, "slug", None) or getattr(r, "name", str(r)),
                "toolkit": tkit_slug,
                "description": (getattr(r, "description", "") or "")[:200],
            })
            if len(out) >= limit:
                break
        return {"tools": out, "count": len(out)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/composio/execute")
async def composio_execute(payload: dict):
    """Run any Composio tool by slug.

    POST body:
      {
        "slug": "GMAIL_SEND_EMAIL",
        "arguments": { ... tool-specific args ... },
        "user_id": "optional override, defaults to COMPOSIO_ENTITY_ID"
      }
    """
    slug = (payload or {}).get("slug")
    args = (payload or {}).get("arguments") or {}
    user_id = (payload or {}).get("user_id") or os.environ.get("COMPOSIO_ENTITY_ID")
    if not slug:
        return JSONResponse({"success": False, "error": "slug required"}, status_code=400)
    try:
        from src.agent.tools.composio_tools import get_composio_client, _execute_with_fallback
        c = get_composio_client()
        resp = _execute_with_fallback(slug, args, user_id)
        return {"success": True, "slug": slug, "result": resp}
    except Exception as e:
        logger.exception("Composio execute failed for %s", slug)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Diagnostic endpoint — confirms which background loops are actually running
# ---------------------------------------------------------------------------

@app.get("/diag")
async def diag():
    """Liveness check for scheduler, Telegram poll loop, and key credentials."""
    info = {
        "role": os.getenv("RENDER_ROLE") or "standalone",
        "scheduler_running": bool(scheduler and getattr(scheduler, "running", False)),
        "telegram": {
            "bot_token_set": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
            "owner_chat_id": os.getenv("TELEGRAM_AI_OWNER_CHAT_ID") or os.getenv("TELEGRAM_GROUP_CHAT_ID"),
            "poll_task_alive": False,
        },
        "composio": {
            "api_key_set": bool(os.getenv("COMPOSIO_API_KEY")),
            "entity_id": os.getenv("COMPOSIO_ENTITY_ID"),
        },
    }
    try:
        from src.agent.agents import telegram_control_agent
        t = telegram_control_agent._task
        info["telegram"]["poll_task_alive"] = bool(t and not t.done())
    except Exception:
        pass
    return info


# ---------------------------------------------------------------------------
# Blog
# ---------------------------------------------------------------------------

@app.post("/blog")
async def generate_blog():
    """Manually trigger blog email generation."""
    try:
        result = generate_and_send_blog()
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Chat  (full-featured — knowledge base, memory, tools, URL scraping)
# ---------------------------------------------------------------------------

# In-memory conversation history per session (keyed by session_id)
_chat_sessions: dict[str, list[dict]] = {}
_MAX_HISTORY = 20  # keep last N turns per session


# Use the shared knowledge module (same identity for graph + chat)
from src.agent.core.knowledge import load_knowledge_context, build_system_prompt


@app.post("/ask")
async def ask(request: Request):
    """Ask the agent about itself: what it researched, why it picked a product, what's next.

    Pulls from agent_status.json, agent_analytics_daily.json, and recent memory.
    Routes through llm_router with task='explain_self'.
    """
    try:
        body = await request.json()
        question = (body.get("question") or body.get("message") or "").strip()
        if not question:
            return JSONResponse({"error": "Missing 'question'"}, status_code=400)

        base = Path(__file__).resolve().parent.parent.parent

        # Load status snapshot
        status_snapshot = ""
        try:
            sp = base / "agent_status.json"
            if sp.exists():
                status_snapshot = sp.read_text(encoding="utf-8")[:3000]
        except Exception:
            pass

        # Load today's analytics
        analytics_snapshot = ""
        try:
            ap = base / "agent_analytics_daily.json"
            if ap.exists():
                data = json.loads(ap.read_text(encoding="utf-8"))
                today = datetime.utcnow().strftime("%Y-%m-%d")
                analytics_snapshot = json.dumps(data.get(today, data), indent=2)[:2000]
        except Exception:
            pass

        # Memory recall + Mem0
        memory_lines = []
        try:
            from src.agent.memory_store import get_memory_store
            store = get_memory_store()
            for m in store.search_memory(query=question, limit=5):
                val = m.get("value", "")
                if isinstance(val, dict):
                    val = json.dumps(val)[:200]
                memory_lines.append(f"- {m.get('key', '?')}: {str(val)[:200]}")
        except Exception:
            pass
        try:
            from src.agent import mem0_adapter
            for m in mem0_adapter.recall_relevant(question, top_k=3):
                memory_lines.append(f"- mem0: {str(m)[:200]}")
        except Exception:
            pass

        memory_block = "\n".join(memory_lines) if memory_lines else "(none)"

        prompt = f"""You are the FDWA agent answering a question about yourself.
Be concrete and reference what you actually did, not generic claims.

QUESTION: {question}

CURRENT STATUS:
{status_snapshot or "(no status snapshot)"}

TODAY'S ANALYTICS:
{analytics_snapshot or "(no analytics)"}

RELEVANT MEMORY:
{memory_block}

Answer in 2-4 short paragraphs. Reference specific topics, products, frameworks
when they appear in the data above. If the data does not support an answer,
say so plainly — do not invent facts."""

        from src.agent.llm_router import route
        from src.agent.agents.content_agent import strip_markdown
        from src.agent import mem0_adapter

        llm = route(task="explain_self", needs_long_context=True)
        resp = llm.invoke(prompt)
        reply = strip_markdown(resp.content if hasattr(resp, "content") else str(resp))

        # Persist Q/A to Mem0 for future self-reflection
        try:
            mem0_adapter.remember_conversation("fdwa_agent", question, reply)
        except Exception:
            pass

        return {"answer": reply, "memory_hits": len(memory_lines)}
    except Exception as e:
        logger.exception("/ask error")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/chat")
async def chat(request: Request):
    """Full-featured chat endpoint with knowledge base, memory, URL scraping, and history."""
    try:
        body = await request.json()
        user_msg = body.get("message", "").strip()
        session_id = body.get("session_id", "default")

        if not user_msg:
            return JSONResponse({"error": "Empty message"}, status_code=400)

        # --- URL detection & auto-scrape ---
        extra_context = ""
        from src.agent.tools.web_tools import extract_urls, scrape_url

        urls = extract_urls(user_msg)
        if urls:
            scraped_parts = []
            for url in urls[:3]:  # max 3 URLs per message
                result = scrape_url(url)
                if "error" not in result:
                    title = result.get("title", "")
                    md = result.get("markdown", "")
                    scraped_parts.append(
                        f"[Scraped from {url}]\nTitle: {title}\nContent:\n{md}"
                    )
                else:
                    scraped_parts.append(f"[Could not scrape {url}: {result['error']}]")
            extra_context = "\n\n".join(scraped_parts)

        # --- Check if user wants a web search ---
        search_triggers = ["search for", "look up", "find info", "google", "what is the latest"]
        if any(t in user_msg.lower() for t in search_triggers) and not urls:
            from src.agent.tools.web_tools import search_web
            results = search_web(user_msg, limit=5)
            if results:
                search_text = "\n".join(
                    f"- {r['title']}: {r['description']} ({r['url']})"
                    for r in results
                )
                extra_context += f"\n\nWeb search results:\n{search_text}"

        # --- Memory recall ---
        memory_context = ""
        try:
            from src.agent.memory_store import get_memory_store
            store = get_memory_store()
            memories = store.search_memory(query=user_msg, limit=3)
            if memories:
                memory_parts = []
                for m in memories:
                    val = m.get("value", "")
                    if isinstance(val, dict):
                        val = json.dumps(val)[:300]
                    elif isinstance(val, str):
                        val = val[:300]
                    memory_parts.append(f"- {m.get('key', '?')}: {val}")
                if memory_parts:
                    memory_context = "\nRelevant memories:\n" + "\n".join(memory_parts)
        except Exception as e:
            logger.debug("Memory recall skipped: %s", e)

        # --- Build conversation history ---
        if session_id not in _chat_sessions:
            _chat_sessions[session_id] = []
        history = _chat_sessions[session_id]

        # System prompt (shared module — same identity as main graph agent)
        system_prompt = build_system_prompt(
            purpose="chat", extra_context=extra_context + memory_context
        )

        # Build messages list for LLM
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

        messages = [SystemMessage(content=system_prompt)]

        # Add conversation history (last N turns)
        for turn in history[-_MAX_HISTORY:]:
            if turn["role"] == "user":
                messages.append(HumanMessage(content=turn["content"]))
            else:
                messages.append(AIMessage(content=turn["content"]))

        # Add current message
        messages.append(HumanMessage(content=user_msg))

        # --- Call LLM ---
        from src.agent.llm_provider import get_llm
        llm = get_llm(purpose="chat assistant")
        response = llm.invoke(messages)
        reply_text = response.content if hasattr(response, "content") else str(response)

        # --- Strip markdown from response ---
        from src.agent.agents.content_agent import strip_markdown
        reply_text = strip_markdown(reply_text)

        # --- Save to conversation history ---
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply_text})

        # Trim history
        if len(history) > _MAX_HISTORY * 2:
            _chat_sessions[session_id] = history[-_MAX_HISTORY * 2:]

        # --- Persist important interactions to memory ---
        try:
            if len(user_msg) > 20:  # non-trivial messages
                store = get_memory_store()
                store.save_memory(
                    f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    {"user": user_msg[:500], "assistant": reply_text[:500], "session": session_id},
                )
        except Exception:
            pass  # non-critical

        return {
            "reply": reply_text,
            "session_id": session_id,
            "urls_scraped": len(urls),
        }
    except Exception as e:
        logger.exception("Chat error")
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Scheduler Control
# ---------------------------------------------------------------------------

@app.get("/scheduler")
async def scheduler_status():
    """Get scheduler info."""
    global scheduler
    if scheduler is None:
        return {"running": False, "interval_minutes": 80, "jobs": []}
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        })
    return {"running": scheduler.running, "interval_minutes": 80, "jobs": jobs}


@app.get("/scheduler/jobs")
async def scheduler_list_jobs():
    """Return persisted custom scheduler jobs."""
    from src.agent import scheduler as sched
    return {"jobs": sched.list_jobs()}


@app.post("/scheduler/add")
async def scheduler_add_job(payload: dict):
    """Add a scheduler job from a spec or natural-language text.

    Body: {"text": "every day at 9am crypto"} OR
          {"spec": {"kind": "cron", "cron": "0 9 * * *", "topic": "crypto"}}
    """
    from src.agent import scheduler as sched
    spec = payload.get("spec")
    if not spec and payload.get("text"):
        from src.agent.agents.schedule_nlp_agent import parse_nl
        spec = parse_nl(payload["text"])
        if spec.get("error"):
            return {"error": spec["error"]}
    if not spec:
        return {"error": "provide 'text' or 'spec'"}
    try:
        return {"job": sched.add_job_from_spec(spec)}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/scheduler/jobs/{job_id}")
async def scheduler_delete_job(job_id: str):
    from src.agent import scheduler as sched
    ok = sched.remove_job(job_id)
    return {"removed": bool(ok), "job_id": job_id}


@app.post("/scheduler/toggle")
async def scheduler_toggle():
    """Pause or resume the scheduler."""
    global scheduler
    if scheduler is None:
        return {"error": "Scheduler not initialized"}
    if scheduler.running:
        scheduler.pause()
        return {"running": False, "message": "Scheduler paused"}
    else:
        scheduler.resume()
        return {"running": True, "message": "Scheduler resumed"}


# ---------------------------------------------------------------------------
# Settings (read-only view of key env vars — values masked)
# ---------------------------------------------------------------------------

# Each entry: either a single env key, or a tuple of aliases (first one that is set wins).
_SETTING_KEYS: list = [
    "COMPOSIO_API_KEY", "COMPOSIO_ENTITY_ID",
    "MISTRAL_API_KEY", "OPENROUTER_API_KEY",
    "COINMARKETCAP_API_KEY", "SERPAPI_KEY", "IMGBB_API_KEY",
    "FIRECRAWL_API_KEY", "LANGSMITH_API_KEY",
    ("ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_API_KEY"),
    ("ASTRA_DB_API_ENDPOINT", "ASTRA_DB_ENDPOINT"),
    "ASTRA_DB_KEYSPACE",
    "BLOG_INTERVAL_HOURS", "SCHEDULER_INTERVAL_MINUTES",
    "GOOGLESHEETS_POSTS_SPREADSHEET_ID", "GOOGLESHEETS_TOKENS_SPREADSHEET_ID",
    "COMPOSIO_GOOGLESHEETS_ACCOUNT_ID", "COMPOSIO_GOOGLEDRIVE_ACCOUNT_ID",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_AI_OWNER_CHAT_ID",
    "HF_TOKEN", "BLOG_RECIPIENT_EMAIL",
]


@app.get("/settings")
async def get_settings():
    """Return env var keys and whether they are set (values masked).

    Entries may be aliased — if a tuple is given, the first non-empty alias wins
    so the dashboard does not report 'NOT SET' just because the user used a
    different but equivalent variable name.
    """
    settings = []
    for entry in _SETTING_KEYS:
        aliases = (entry,) if isinstance(entry, str) else tuple(entry)
        display_key = aliases[0]
        val = None
        matched_alias = None
        for alias in aliases:
            v = os.environ.get(alias)
            if v:
                val = v
                matched_alias = alias
                break
        settings.append({
            "key": display_key,
            "alias_used": matched_alias,
            "aliases": list(aliases) if len(aliases) > 1 else None,
            "set": val is not None and val != "",
            "preview": (val[:4] + "…") if val and len(val) > 4 else ("***" if val else ""),
        })
    return {"settings": settings}


# ---------------------------------------------------------------------------
# Memory / Astra status
# ---------------------------------------------------------------------------

@app.get("/memory/status")
async def memory_status():
    """Quick view of memory/Astra health."""
    try:
        from src.agent.memory_store import get_astra_status
        return get_astra_status()
    except ImportError:
        return {"astra": "not_configured"}
    except Exception as e:
        return {"astra": "error", "detail": str(e)}


# ---------------------------------------------------------------------------
# Admin — refresh business profile
# ---------------------------------------------------------------------------

@app.post("/admin/refresh-profile")
async def refresh_business_profile(urls: list | None = None):
    """Refresh business profile by scraping provided shop URLs."""
    try:
        profile = _load_business_profile()
        to_scrape = urls or [profile.get("shop_page"), profile.get("buymeacoffee")]
        to_scrape = [u for u in to_scrape if u]
        if not to_scrape:
            return {"success": False, "error": "No URLs provided and no defaults in profile."}
        updated = update_business_profile_from_shop(to_scrape)
        return {"success": True, "profile": updated}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    """Start scheduler + Telegram control bot on app startup.

    When RENDER_ROLE=web the worker service already owns the scheduler and
    the Telegram poll loop — skip here to avoid double-firing.
    """
    global scheduler
    role = os.getenv("RENDER_ROLE", "").lower()
    if role == "web":
        logger.info("RENDER_ROLE=web — scheduler + telegram owned by worker; skipping local start")
    else:
        scheduler = start_scheduler()
        logger.info("✅ Scheduler started (role=%s)", role or "standalone")
        try:
            from src.agent.agents import telegram_control_agent
            task = telegram_control_agent.start_background_task()
            owner = os.getenv("TELEGRAM_AI_OWNER_CHAT_ID") or os.getenv("TELEGRAM_GROUP_CHAT_ID")
            token = os.getenv("TELEGRAM_BOT_TOKEN")
            if task is not None:
                logger.info("✅ Telegram control bot polling (owner_chat=%s, token=%s)",
                            owner, "set" if token else "MISSING")
            else:
                logger.warning("⚠️ Telegram control bot NOT started — check TELEGRAM_AI_OWNER_CHAT_ID / TELEGRAM_BOT_TOKEN")
        except Exception as e:
            logger.warning("Telegram control bot failed to start (non-critical): %s", e)

    try:
        from src.agent.sheets_agent import initialize_google_sheets
        initialize_google_sheets()
    except Exception as e:
        logger.warning("Google Sheets initialization failed (non-critical): %s", e)


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    try:
        from src.agent.agents import telegram_control_agent
        await telegram_control_agent.stop_background_task()
    except Exception as e:
        logger.debug("Telegram control stop error: %s", e)
    if scheduler is not None:
        scheduler.shutdown()

