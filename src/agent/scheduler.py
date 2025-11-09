"""Background scheduler for autonomous agent execution."""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.agent.graph import graph

logger = logging.getLogger(__name__)

# Status file to track last run
STATUS_FILE = Path("agent_status.json")

# Global status
last_run_status = {
    "last_run": None,
    "status": "Never run",
    "results": {}
}


def save_status(status: dict) -> None:
    """Save agent status to file."""
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save status: {e}")


def load_status() -> dict:
    """Load agent status from file."""
    global last_run_status
    try:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, "r") as f:
                last_run_status = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load status: {e}")
    return last_run_status


async def run_agent_task() -> dict:
    """Run the agent and return results."""
    logger.info("Scheduled agent run starting...")
    
    try:
        # Run agent
        result = graph.invoke({})
        
        # Update status
        status = {
            "last_run": datetime.now().isoformat(),
            "status": "Success",
            "results": {
                "tweet": result.get("tweet_text", "N/A")[:100],
                "twitter": "Posted" if "twitter_url" in result else "Failed",
                "facebook": "Posted" if "facebook_post_id" in result else "Failed",
                "comment": result.get("comment_status", "N/A")
            }
        }
        
        logger.info("Agent run completed successfully")
        
    except Exception as e:
        logger.exception("Agent run failed")
        status = {
            "last_run": datetime.now().isoformat(),
            "status": f"Failed: {str(e)}",
            "results": {}
        }
    
    # Save and return
    global last_run_status
    last_run_status = status
    save_status(status)
    return status


def start_scheduler() -> AsyncIOScheduler:
    """Start the background scheduler."""
    scheduler = AsyncIOScheduler()
    
    # Run every 30 minutes
    scheduler.add_job(
        run_agent_task,
        'interval',
        minutes=30,
        id='agent_task',
        name='Run FDWA Agent',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Scheduler started - agent will run every 30 minutes")
    
    # Load existing status
    load_status()
    
    return scheduler


def get_status() -> dict:
    """Get current agent status."""
    return last_run_status
