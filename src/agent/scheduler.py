"""Background scheduler for autonomous agent execution."""

import json
import logging
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.agent.graph import graph
from src.agent.realtime_status import broadcaster

JOBS_FILE = Path("scheduler_jobs.json")

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

        # Always send a full per-platform summary to Telegram (success or failure)
        try:
            from src.agent.tools.composio_tools import send_telegram_alert as send_telegram_text

            def _badge(val: str) -> str:
                v = str(val or "").lower()
                if not v or v in ("n/a", "missing"):
                    return "⚠️"
                if "skipped" in v or "skip" in v:
                    return "⏭️"
                if "fail" in v or "error" in v or "expired" in v:
                    return "❌"
                return "✅"

            fb_status = result.get("facebook_status") or (f"Posted: {result.get('facebook_post_id')}" if result.get("facebook_post_id") else "missing")
            tw_status = "skipped_by_config" if result.get("twitter_post_id") == "skipped_by_config" else (f"Posted: {result.get('twitter_url')}" if result.get("twitter_url") else "missing")
            li_status = result.get("linkedin_status") or "missing"
            ig_status = result.get("instagram_status") or "missing"
            tg_status = result.get("telegram_status") or "missing"
            blog_status = result.get("blog_status") or "missing"
            buffer_status = result.get("buffer_status") or "missing"
            gdoc_url = result.get("gdocs_url") or ""
            gdoc_status = result.get("gdocs_status") or "missing"

            lines = [
                f"🤖 FDWA Agent run — {datetime.now().isoformat()}",
                f"{_badge(fb_status)} facebook: {str(fb_status)[:120]}",
                f"{_badge(tw_status)} twitter: {str(tw_status)[:120]}",
                f"{_badge(li_status)} linkedin: {str(li_status)[:120]}",
                f"{_badge(ig_status)} instagram: {str(ig_status)[:120]}",
                f"{_badge(tg_status)} telegram: {str(tg_status)[:120]}",
                f"{_badge(blog_status)} blog: {str(blog_status)[:120]}",
                f"{_badge(buffer_status)} buffer: {str(buffer_status)[:120]}",
            ]
            if gdoc_url:
                lines.append(f"📄 gdoc: {gdoc_url}")
            else:
                lines.append(f"📄 gdoc: {str(gdoc_status)[:120]}")
            if result.get("error"):
                lines.append(f"⚠️ graph_error: {str(result.get('error'))[:200]}")

            try:
                send_telegram_text("\n".join(lines))
            except Exception:
                pass
        except Exception:
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
                "video": result.get("video_url", ""),
                "video_path": result.get("video_path", ""),
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


_scheduler: AsyncIOScheduler | None = None


# ── Persisted custom jobs ─────────────────────────────────────────────────

def _load_jobs_file() -> list[dict]:
    if not JOBS_FILE.exists():
        return []
    try:
        return json.loads(JOBS_FILE.read_text(encoding="utf-8")) or []
    except Exception:
        return []


def _save_jobs_file(jobs: list[dict]) -> None:
    try:
        JOBS_FILE.write_text(json.dumps(jobs, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Jobs save failed: %s", e)


def _trigger_from_spec(spec: dict):
    """Build an APScheduler trigger from a persisted spec.

    spec shapes:
      {"kind": "cron", "cron": "0 9 * * *"}
      {"kind": "interval", "minutes": 360}
    """
    kind = (spec.get("kind") or "interval").lower()
    if kind == "cron":
        parts = (spec.get("cron") or "0 9 * * *").split()
        if len(parts) != 5:
            raise ValueError(f"cron must have 5 fields, got: {spec.get('cron')!r}")
        minute, hour, day, month, dow = parts
        return CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=dow)
    return IntervalTrigger(minutes=int(spec.get("minutes") or 360))


async def _run_with_topic(topic: str | None = None) -> dict:
    """Job entry that can bias a cycle toward a topic override."""
    init_state = {"topic_override": topic} if topic else {}
    await broadcaster.start_run(total_steps=11)
    try:
        result = graph.invoke(init_state)
        return result
    except Exception as e:
        logger.exception("Scheduled run with topic=%s failed: %s", topic, e)
        return {"error": str(e)}


def list_jobs() -> list[dict]:
    """Return the persisted + live job list."""
    return _load_jobs_file()


def add_job_from_spec(spec: dict) -> dict:
    """Add a new scheduled job. Spec shape:
        {"id": "<auto-if-missing>", "topic": "crypto", "kind": "cron|interval",
         "cron": "0 9 * * *", "minutes": 360, "enabled": true}
    Returns the stored spec.
    """
    if _scheduler is None:
        return {"error": "scheduler not started"}
    jobs = _load_jobs_file()
    job_id = spec.get("id") or f"job_{int(datetime.now().timestamp())}"
    spec = {"id": job_id, "enabled": True, **spec, "id": job_id}

    trigger = _trigger_from_spec(spec)
    topic = spec.get("topic")

    _scheduler.add_job(
        _run_with_topic,
        trigger=trigger,
        id=job_id,
        name=f"FDWA run ({topic or 'default'})",
        kwargs={"topic": topic},
        replace_existing=True,
    )

    jobs = [j for j in jobs if j.get("id") != job_id]
    jobs.append(spec)
    _save_jobs_file(jobs)
    logger.info("Added scheduler job %s", spec)
    return spec


def remove_job(job_id: str) -> bool:
    if _scheduler is None:
        return False
    try:
        _scheduler.remove_job(job_id)
    except Exception as e:
        logger.warning("remove_job %s failed: %s", job_id, e)
    jobs = [j for j in _load_jobs_file() if j.get("id") != job_id]
    _save_jobs_file(jobs)
    return True


def toggle_job(job_id: str, enabled: bool) -> bool:
    if _scheduler is None:
        return False
    jobs = _load_jobs_file()
    found = False
    for j in jobs:
        if j.get("id") == job_id:
            j["enabled"] = enabled
            found = True
            try:
                if enabled:
                    _scheduler.resume_job(job_id)
                else:
                    _scheduler.pause_job(job_id)
            except Exception as e:
                logger.warning("toggle_job %s failed: %s", job_id, e)
    if found:
        _save_jobs_file(jobs)
    return found


def start_scheduler() -> AsyncIOScheduler:
    """Start the background scheduler."""
    global _scheduler
    scheduler = AsyncIOScheduler()
    _scheduler = scheduler

    # Default 6h agent tick (preserved)
    scheduler.add_job(
        run_agent_task,
        'interval',
        minutes=360,
        id='agent_task',
        name='Run FDWA Agent',
        replace_existing=True
    )

    # Restore any persisted custom jobs
    for spec in _load_jobs_file():
        try:
            if spec.get("enabled") is False:
                continue
            add_job_from_spec(spec)
        except Exception as e:
            logger.warning("Could not restore job %s: %s", spec.get("id"), e)

    scheduler.start()
    logger.info("Scheduler started - default tick every 6h, %d custom jobs restored", len(_load_jobs_file()))

    load_status()
    return scheduler


def pause() -> bool:
    """Pause the scheduler (no new runs until resume()). Idempotent."""
    if _scheduler is None:
        return False
    try:
        _scheduler.pause()
        logger.info("Scheduler paused")
        return True
    except Exception as e:
        logger.warning("pause() failed: %s", e)
        return False


def resume() -> bool:
    """Resume a paused scheduler. Idempotent."""
    if _scheduler is None:
        return False
    try:
        _scheduler.resume()
        logger.info("Scheduler resumed")
        return True
    except Exception as e:
        logger.warning("resume() failed: %s", e)
        return False


def get_status() -> dict:
    """Get current agent status."""
    return last_run_status
