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
load_dotenv()

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
        from src.agent.agents import research_agent, twitter_agent, facebook_agent  # noqa
        from src.agent.agents import linkedin_agent_v2 as linkedin_agent  # noqa
        from src.agent.agents import instagram_agent_v2 as instagram_agent  # noqa
        from src.agent.agents import telegram_agent_v2 as telegram_agent  # noqa
        from src.agent.agents import blog_agent, memory_agent, content_agent  # noqa
        from src.agent.agents import comment_agent  # noqa

        _AGENT_RUNNERS.update({
            "research": ("Research Trends", lambda st: {"trend_data": research_agent.research_trends().get("trend_data", ""), "source": "manual"}),
            "twitter": ("Twitter Post", twitter_agent.run),
            "facebook": ("Facebook Post", facebook_agent.run),
            "linkedin": ("LinkedIn Post", linkedin_agent.run),
            "instagram": ("Instagram Post", instagram_agent.run),
            "telegram": ("Telegram Post", telegram_agent.run),
            "blog": ("Blog/Email", blog_agent.run),
            "memory": ("Memory Save", memory_agent.run),
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

@app.post("/agent/run/{agent_id}")
async def run_single_agent(agent_id: str):
    """Run a single agent by ID (twitter, facebook, linkedin, etc.)."""
    _lazy_load_agents()
    if agent_id not in _AGENT_RUNNERS:
        return JSONResponse({"success": False, "error": f"Unknown agent: {agent_id}"}, status_code=404)

    label, runner = _AGENT_RUNNERS[agent_id]
    try:
        # Build a minimal state from latest status
        current = get_status()
        state = dict(current.get("results", {}))
        state.setdefault("base_insights", state.get("tweet", "No insights available"))
        state.setdefault("trend_data", "")
        state.setdefault("ai_strategy", {})
        state.setdefault("image_url", state.get("image", ""))

        await broadcaster.update(f"Running {label} agent…")
        result = runner(state)
        await broadcaster.update(f"{label} agent completed")
        return {"success": True, "agent": agent_id, "result": result}
    except Exception as e:
        logger.exception("Single agent %s failed", agent_id)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


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

_SETTING_KEYS = [
    "COMPOSIO_API_KEY", "MISTRAL_API_KEY", "OPENROUTER_API_KEY",
    "COINMARKETCAP_API_KEY", "SERPAPI_KEY", "IMGBB_API_KEY",
    "FIRECRAWL_API_KEY", "LANGSMITH_API_KEY",
    "ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_API_ENDPOINT",
    "ASTRA_COLLECTION_NAME",
    "BLOG_INTERVAL_HOURS", "SCHEDULER_INTERVAL_MINUTES",
    "GOOGLE_POSTS_SPREADSHEET_ID", "GOOGLE_TOKENS_SPREADSHEET_ID",
]


@app.get("/settings")
async def get_settings():
    """Return env var keys and whether they are set (values masked)."""
    settings = []
    for key in _SETTING_KEYS:
        val = os.environ.get(key)
        settings.append({
            "key": key,
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
    """Start scheduler on app startup."""
    global scheduler
    scheduler = start_scheduler()

    try:
        from src.agent.sheets_agent import initialize_google_sheets
        initialize_google_sheets()
    except Exception as e:
        logger.warning("Google Sheets initialization failed (non-critical): %s", e)


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    scheduler.shutdown()

