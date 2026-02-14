"""FastAPI application for running the FDWA agent."""

import asyncio
import logging
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from langserve import add_routes

# Load environment variables FIRST before importing graph
load_dotenv()

from src.agent.graph import graph
from src.agent.scheduler import start_scheduler, get_status, run_agent_task
from src.agent.blog_email_agent import generate_and_send_blog, update_business_profile_from_shop, _load_business_profile
from src.agent.realtime_status import broadcaster

logger = logging.getLogger(__name__)

app = FastAPI(title="FDWA Social Media Agent")

# Mount static files from templates directory for CSS/JS
templates_dir = Path(__file__).parent.parent.parent / "templates"
app.mount("/static", StaticFiles(directory=str(templates_dir)), name="static")

# Add LangServe route for LangSmith Studio
add_routes(app, graph, path="/agent")

scheduler = None


@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the UI homepage."""
    template_path = Path(__file__).parent.parent.parent / "templates" / "index.html"
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


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
            # Send connection confirmation
            yield f"data: {{'type': 'connected', 'message': 'Connected to agent stream'}}\n\n"
            
            # Send history
            for event in broadcaster.get_history():
                yield f"data: {event}\n\n"
            
            # Stream new events
            while True:
                event = await queue.get()
                yield f"data: {event}\n\n"
        except asyncio.CancelledError:
            broadcaster.remove_client(queue)
            raise
        except Exception as e:
            logger.error(f"Stream error: {e}")
            broadcaster.remove_client(queue)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.on_event("startup")
async def startup():
    """Start scheduler on app startup."""
    global scheduler
    scheduler = start_scheduler()
    
    # Initialize Google Sheets if needed
    try:
        from src.agent.sheets_agent import initialize_google_sheets
        initialize_google_sheets()
    except Exception as e:
        logger.warning(f"Google Sheets initialization failed (non-critical): {e}")


@app.post("/run")
async def run_agent():
    """Manually trigger agent run."""
    result = await run_agent_task()
    return result


@app.post("/blog")
async def generate_blog():
    """Manually trigger blog email generation."""
    try:
        result = generate_and_send_blog()
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/admin/refresh-profile")
async def refresh_business_profile(urls: list | None = None):
    """Refresh business profile by scraping provided shop URLs or default profile URLs.

    POST body (optional): JSON array of URLs to scrape. If omitted, uses
    `buymeacoffee` and `shop_page` from `business_profile.json`.
    """
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


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    scheduler.shutdown()

