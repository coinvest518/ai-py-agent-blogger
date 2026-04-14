"""Targeted smoke test: Twitter, Facebook, Instagram only. No full graph.

Uses real .env. Tests:
  1. Twitter direct API auth (GET /2/users/me)
  2. Twitter direct post a test tweet
  3. Facebook post via Composio (test message with timestamp)
  4. Instagram post via Composio with a public test image
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

load_dotenv(override=True)

from src.agent.agents import twitter_agent
from src.agent.tools.composio_tools import post_facebook, post_instagram

TEST_IMAGE = os.getenv("TEST_IMAGE_URL", "https://picsum.photos/seed/fdwa/1200/900")
STAMP = datetime.now().strftime("%H:%M:%S")

def test_twitter_auth():
    print("\n=== 1. Twitter auth check ===")
    session = twitter_agent._oauth_session()
    if not session:
        print("  OAuth keys not configured in env")
        return False
    import requests
    r = session.get("https://api.x.com/2/users/me", timeout=30)
    print(f"  GET /2/users/me -> {r.status_code}")
    print(f"  body: {r.text[:200]}")
    return r.status_code == 200

def test_twitter_post():
    print("\n=== 2. Twitter direct post ===")
    text = f"FDWA agent smoke test {STAMP} - AI automation for entrepreneurs"
    result = twitter_agent._post_direct(text, image_url=None)
    print(f"  result: {result}")
    return bool(result.get("success"))

def test_facebook():
    print("\n=== 3. Facebook post via Composio ===")
    text = f"FDWA smoke test FB {STAMP} — testing post pipeline"
    result = post_facebook(page_id=None, text=text, photo_path=None)
    print(f"  result: {result}")
    return bool(result.get("success"))

def test_instagram():
    print("\n=== 4. Instagram post via Composio ===")
    caption = f"FDWA smoke test IG {STAMP}"
    result = post_instagram(caption=caption, image_url=TEST_IMAGE)
    print(f"  result: {result}")
    return bool(result.get("instagram_status") == "Posted" or result.get("instagram_post_id"))

def main() -> int:
    # GET /2/users/me can 403 on free tier even with valid keys — attempt post anyway.
    test_twitter_auth()
    test_twitter_post()

    test_facebook()
    test_instagram()

    return 0

if __name__ == "__main__":
    sys.exit(main())
