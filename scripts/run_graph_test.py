"""End-to-end test of the restructured FDWA graph."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import logging
logging.basicConfig(level=logging.WARNING)

from src.agent.graph import graph

print("Starting graph invocation (full end-to-end test)...")
print("Workflow: research -> content -> image -> post all -> blog -> memory")
print()

try:
    final = graph.invoke({})

    print("=== RESULTS ===")
    keys = [
        "tweet_text", "facebook_text", "linkedin_text", "instagram_caption",
        "telegram_message", "image_url", "twitter_url", "facebook_status",
        "linkedin_status", "instagram_status", "telegram_status",
        "instagram_comment_status", "twitter_reply_status", "comment_status",
        "blog_status", "blog_title", "memory_status", "crypto_analysis",
    ]
    for key in keys:
        val = final.get(key, "N/A")
        if isinstance(val, str):
            val = val[:120]
        elif isinstance(val, dict):
            val = "dict with keys: " + str(list(val.keys()))
        elif isinstance(val, list):
            val = "list with " + str(len(val)) + " items"
        print(f"  {key}: {val}")

    err = final.get("error")
    if err:
        print(f"  ERROR: {err}")

    print()
    print("GRAPH EXECUTION COMPLETE")
except Exception as e:
    print(f"GRAPH EXECUTION FAILED: {e}")
    import traceback
    traceback.print_exc()
