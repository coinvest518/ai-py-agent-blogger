"""Background worker entry point — runs scheduler + Telegram control bot.

Used by the Render `fdwa-worker` service so the web FastAPI process doesn't
double-fire the scheduler. Blocks on the asyncio loop forever.

    python -m src.agent.worker
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from dotenv import load_dotenv

load_dotenv()

from src.agent.scheduler import start_scheduler  # noqa: E402
from src.agent.agents import telegram_control_agent  # noqa: E402

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("fdwa.worker")
print("FDWA worker bootstrap: LOG_LEVEL=", os.getenv("LOG_LEVEL"))


async def _heartbeat() -> None:
    while True:
        logger.info("worker heartbeat — supervisor loop alive")
        await asyncio.sleep(300)


async def main() -> None:
    print("FDWA worker main(): starting")
    logger.info("🚀 FDWA worker starting (scheduler + telegram control)…")
    scheduler = start_scheduler()
    telegram_task = telegram_control_agent.start_background_task()
    heartbeat_task = asyncio.create_task(_heartbeat(), name="heartbeat")

    stop_event = asyncio.Event()

    def _on_signal(*_):
        logger.info("signal received — shutting down worker")
        stop_event.set()

    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _on_signal)
            except NotImplementedError:
                pass
    except Exception:
        pass

    try:
        await stop_event.wait()
    finally:
        heartbeat_task.cancel()
        await telegram_control_agent.stop_background_task()
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass
        logger.info("worker stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
