"""One-shot real graph run — no stubs, uses .env as-is.

Prints a compact per-channel status table so we can see what works after the
Composio version-check fix and the LLM cascade reorder.
"""
from __future__ import annotations

import logging
import sys
import io
from dotenv import load_dotenv

# Force UTF-8 stdout so emojis in status text don't crash Windows cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from src.agent.graph import graph

CHANNELS = [
    ("tweet", "tweet_text", "twitter_url"),
    ("buffer", None, "buffer_status"),
    ("linkedin", "linkedin_text", "linkedin_status"),
    ("facebook", "facebook_text", "facebook_status"),
    ("instagram", "instagram_caption", "instagram_status"),
    ("telegram", "telegram_text", "telegram_status"),
    ("blog", "blog_post", "blog_status"),
    ("upload_post", None, "upload_post_status"),
]

def main() -> int:
    print("=== Real graph run (no stubs) ===")
    final_state = graph.invoke({})
    print("\n=== Per-channel status ===")
    for label, text_key, status_key in CHANNELS:
        status = (final_state.get(status_key) or "(no status)") if status_key else "(n/a)"
        text = ""
        if text_key:
            text = (final_state.get(text_key) or "")[:80].replace("\n", " ")
        safe_status = str(status)[:80].encode("ascii", "replace").decode("ascii")
        safe_text = text.encode("ascii", "replace").decode("ascii")
        print(f"  {label:12} {safe_status:80} | {safe_text}")

    err = final_state.get("error")
    if err:
        print(f"\nGraph error: {err}")
        return 1
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
