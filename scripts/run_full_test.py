"""Full verbose test of the FDWA AI Agent pipeline.

Shows every step, what the agent is thinking, and results.
Run with:  python -u scripts/run_full_test.py

The -u flag ensures unbuffered output so you see logs in real-time.
"""
import json
import os
import sys
import time

# Ensure project root is on path
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())

import logging

# ── Verbose logging — show everything ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-35s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
# Quiet down noisy libraries but keep our agents loud
for noisy in ["httpx", "httpcore", "urllib3", "requests", "openai", "composio",
               "astrapy", "huggingface_hub", "langsmith", "PIL"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger("test_runner")

# ═══════════════════════════════════════════════════════════════════════
# Banner
# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("  FDWA AI Agent — Full Pipeline Test (Verbose)")
print("=" * 70)
print()
print("  This test runs the COMPLETE graph end-to-end:")
print()
print("  1. Research Trends    — search web for trending topics")
print("  2. Generate Content   — AI Decision Engine + per-platform LLM")
print("  3. Generate Image     — Pollinations → Freepik → HuggingFace")
print("  4. Post Twitter       — tweet via Composio")
print("  5. Post Facebook      — post via Composio")
print("  6. Post LinkedIn      — post via Composio")
print("  7. Post Telegram      — crypto analysis + send to group")
print("  8. Post Instagram     — photo + caption (needs public image URL)")
print("  9. Monitor IG         — check for comments, auto-reply")
print(" 10. Reply Twitter      — engage with mentions")
print(" 11. Comment Facebook   — engage with comments")
print(" 12. Generate Blog      — 1000-1500 word blog email via Gmail")
print(" 13. Record Memory      — save performance to long-term memory")
print()
print("  Watch the logs below to see each step execute in real-time.")
print("=" * 70)
print()

# ═══════════════════════════════════════════════════════════════════════
# Import graph (this also validates all imports + account IDs)
# ═══════════════════════════════════════════════════════════════════════
logger.info("Importing graph and validating configuration...")
start_import = time.time()

try:
    from src.agent.graph import graph
    logger.info("Graph imported OK in %.1fs — %d nodes", time.time() - start_import,
                len(graph.nodes) if hasattr(graph, "nodes") else -1)
except Exception as e:
    logger.error("IMPORT FAILED: %s", e)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════
# Show env config (redacted)
# ═══════════════════════════════════════════════════════════════════════
print()
print("── Environment Check ──")
env_keys = [
    "MISTRAL_API_KEY", "OPENROUTER_API_KEY", "HF_TOKEN",
    "COMPOSIO_API_KEY", "TWITTER_ACCOUNT_ID", "FACEBOOK_ACCOUNT_ID",
    "LINKEDIN_ACCOUNT_ID", "TELEGRAM_ACCOUNT_ID", "INSTAGRAM_ACCOUNT_ID",
    "POLLINATIONS_API_KEY", "FREEPIK_API_KEY", "IMGBB_API_KEY",
    "COINMARKETCAP_API_KEY", "SERPAPI_API_KEY", "TAVILY_API_KEY",
    "GOOGLESHEETS_POSTS_SPREADSHEET_ID", "ASTRA_DB_APPLICATION_TOKEN",
]
for key in env_keys:
    val = os.getenv(key, "")
    if val:
        # Show first 4 and last 4 chars only
        redacted = val[:4] + "..." + val[-4:] if len(val) > 12 else "***"
        print(f"  ✅ {key}: {redacted}")
    else:
        print(f"  ❌ {key}: NOT SET")
print()

# ═══════════════════════════════════════════════════════════════════════
# Run the graph
# ═══════════════════════════════════════════════════════════════════════
logger.info("Starting graph.invoke({}) — full pipeline...")
start_run = time.time()

try:
    final = graph.invoke({})
    elapsed = time.time() - start_run
    logger.info("Graph completed in %.1fs", elapsed)
except KeyboardInterrupt:
    print("\n\n⚠️  Test interrupted by user (Ctrl+C)")
    sys.exit(1)
except Exception as e:
    elapsed = time.time() - start_run
    logger.error("Graph FAILED after %.1fs: %s", elapsed, e)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════
# Results summary
# ═══════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("  RESULTS SUMMARY")
print("=" * 70)
print()

# Content generated
print("── Content Generated ──")
for key, label in [
    ("tweet_text", "Twitter"),
    ("facebook_text", "Facebook"),
    ("linkedin_text", "LinkedIn"),
    ("instagram_caption", "Instagram"),
    ("telegram_message", "Telegram"),
]:
    val = final.get(key, "")
    chars = len(val) if val else 0
    preview = val[:100].replace("\n", " ") + "..." if val and len(val) > 100 else (val or "(empty)")
    print(f"  {label:12s} ({chars:4d} chars): {preview}")

print()

# Image
print("── Image ──")
print(f"  image_url:  {final.get('image_url', 'None')}")
print(f"  image_path: {final.get('image_path', 'None')}")
print()

# Posting results
print("── Posting Results ──")
for key, label in [
    ("twitter_url", "Twitter URL"),
    ("facebook_status", "Facebook"),
    ("linkedin_status", "LinkedIn"),
    ("telegram_status", "Telegram"),
    ("instagram_status", "Instagram"),
]:
    val = final.get(key, "N/A")
    status = "✅" if val and "Posted" in str(val) else ("⚠️" if val and "Skip" in str(val) else "❌")
    print(f"  {status} {label:18s}: {str(val)[:100]}")

print()

# Engagement
print("── Engagement ──")
for key, label in [
    ("instagram_comment_status", "IG Comments"),
    ("twitter_reply_status", "Twitter Replies"),
    ("comment_status", "FB Comments"),
]:
    print(f"  {label:18s}: {str(final.get(key, 'N/A'))[:100]}")

print()

# Blog
print("── Blog ──")
print(f"  Status: {final.get('blog_status', 'N/A')}")
print(f"  Title:  {final.get('blog_title', 'N/A')}")
print()

# Memory
print("── Memory ──")
print(f"  Status: {final.get('memory_status', 'N/A')}")
print()

# AI Strategy
strategy = final.get("ai_strategy")
if strategy and isinstance(strategy, dict):
    print("── AI Strategy ──")
    print(f"  Topic:    {strategy.get('topic', 'N/A')}")
    print(f"  Products: {[p.get('name', '?') for p in strategy.get('products', [])]}")
    print(f"  CTA:      {strategy.get('cta', 'N/A')}")
    print()

# Crypto
crypto = final.get("crypto_analysis")
if crypto and isinstance(crypto, dict):
    print("── Crypto Analysis ──")
    gainers = crypto.get("best_gainers", [])
    losers = crypto.get("best_losers", [])
    print(f"  Top gainers: {len(gainers)}")
    for g in gainers[:3]:
        sym = g.get("symbol", "?") if isinstance(g, dict) else "?"
        print(f"    - {sym}")
    print(f"  Top losers:  {len(losers)}")
    print()

# Errors
if final.get("error"):
    print("── ERRORS ──")
    print(f"  ❌ {final['error']}")
    print()

print("=" * 70)
print(f"  Total time: {elapsed:.1f}s")
print("=" * 70)
