"""Background scheduler for autonomous agent execution."""

import json
import logging
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.agent.graph import graph
from src.agent.realtime_status import broadcaster

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
            with open(STATUS_FILE) as f:
                last_run_status = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load status: {e}")
    return last_run_status


async def run_agent_task() -> dict:
    """Run the agent and return results."""
    logger.info("Scheduled agent run starting...")
    
    # Notify start
    await broadcaster.start_run(total_steps=11)
    
    try:
        # Run agent
        await broadcaster.update("Initializing agent graph...")
        result = graph.invoke({})

        # If any platform step was skipped/failed, send an immediate Telegram alert so operators see why the flow stopped
        try:
            from src.agent.tools.composio_tools import send_telegram_alert as send_telegram_text

            problems = []
            # platform-level checks (treat missing twitter/facebook IDs as failures)
            checks = {
                "telegram": str(result.get("telegram_status", "")).lower(),
                "linkedin": str(result.get("linkedin_status", "")).lower(),
                "instagram": str(result.get("instagram_status", "")).lower(),
                "twitter": "ok" if result.get("twitter_url") else "missing",
                "facebook": "ok" if result.get("facebook_post_id") else "missing",
                "blog": str(result.get("blog_status", "")).lower(),
            }
            for name, val in checks.items():
                if any(x in val for x in ("skipped", "failed", "error")) or val == "missing":
                    problems.append(f"{name}: {result.get(name + ('_status' if name in ('telegram','linkedin','instagram','blog') else '_post_id'), val)}")

            if result.get("error"):
                problems.append(f"graph_error: {result.get('error')}")

            if problems:
                summary = (
                    "⚠️ FDWA Agent run completed with issues — some steps were skipped or failed.\n"
                    f"Time: {datetime.now().isoformat()}\n"
                    "Problems:\n" + "\n".join(problems)
                )
                # Best-effort send (safe if Telegram not configured)
                try:
                    send_telegram_text(summary)
                except Exception:
                    pass
        except Exception:
            # Don't let alerting interfere with normal run
            pass

        # Update status
        status = {
            "last_run": datetime.now().isoformat(),
            "status": "Success",
            "results": {
                "tweet": result.get("tweet_text", "N/A"),
                "linkedin": result.get("linkedin_text", "N/A"),
                "instagram": result.get("instagram_caption", "N/A"),
                "image": result.get("image_url", ""),
                "twitter": "Posted" if "twitter_url" in result else "Failed",
                "facebook": "Posted" if "facebook_post_id" in result else "Failed",
                "telegram": result.get("telegram_status", "N/A"),
                "linkedin_status": result.get("linkedin_status", "N/A"),
                "instagram_status": result.get("instagram_status", "N/A"),
                "comment": result.get("comment_status", "N/A")
            }
        }

        logger.info("Agent run completed successfully")
        await broadcaster.complete_run(success=True, results=status["results"])
        
    except Exception as e:
        logger.exception("Agent run failed")
        await broadcaster.error(f"Agent run failed: {str(e)}", {"error": str(e)})

        # Send Telegram alert for run-level failure (best-effort)
        try:
            from src.agent.tools.composio_tools import send_telegram_alert
            send_telegram_alert(f"🔥 FDWA Agent run FAILED: {str(e)}\nTime: {datetime.now().isoformat()}")
        except Exception:
            pass

        status = {
            "last_run": datetime.now().isoformat(),
            "status": f"Failed: {str(e)}",
            "results": {}
        }
        await broadcaster.complete_run(success=False, results={"error": str(e)})
    
    # Save and return
    global last_run_status
    last_run_status = status
    save_status(status)
    return status


def start_scheduler() -> AsyncIOScheduler:
    """Start the background scheduler."""
    scheduler = AsyncIOScheduler()
    
    # Run every 1 hour 20 minutes (80 minutes)
    scheduler.add_job(
        run_agent_task,
        'interval',
        minutes=80,
        id='agent_task',
        name='Run FDWA Agent',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Scheduler started - agent will run every 1 hour 30 minutes")
    
    # Load existing status
    load_status()
    
    return scheduler


def get_status() -> dict:
    """Get current agent status."""
    return last_run_status
