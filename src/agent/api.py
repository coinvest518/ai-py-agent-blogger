"""FastAPI application for running the FDWA agent."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from agent.graph import graph
from agent.scheduler import start_scheduler, get_status, run_agent_task

app = FastAPI(title="FDWA Social Media Agent")

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


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    scheduler.shutdown()

