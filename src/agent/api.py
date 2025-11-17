"""FastAPI application for running the FDWA agent."""

import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from langserve import add_routes

# Load environment variables FIRST before importing graph
load_dotenv()

from src.agent.graph import graph
from src.agent.scheduler import start_scheduler, get_status, run_agent_task
from src.agent.blog_email_agent import generate_and_send_blog

app = FastAPI(title="FDWA Social Media Agent")

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


@app.on_event("startup")
async def startup():
    """Start scheduler on app startup."""
    global scheduler
    scheduler = start_scheduler()


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


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    scheduler.shutdown()

