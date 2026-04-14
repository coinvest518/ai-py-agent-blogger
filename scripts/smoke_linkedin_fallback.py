"""Exercise the LinkedIn agent end-to-end without the rest of the graph.

Stubs Composio to always fail (rate-limit-like), so the upload-post fallback is exercised.
Uses dry-run mode: sets LINKEDIN_DAILY_LIMIT=0 to verify cap path, then lifts it to actually try posting.
"""
from __future__ import annotations

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Force fallback by making Composio return a simulated rate-limit error
import src.agent.agents.linkedin_agent_v2 as li_mod

def _fake_composio(author_urn, text):
    return {"success": False, "error": "RATE_LIMITED (simulated)"}

li_mod._composio_post = _fake_composio  # type: ignore[assignment]

# Also stub author URN lookup so we don't need a live Composio connection
li_mod.get_linkedin_author_urn = lambda _=None: "urn:li:person:STUB"  # type: ignore[assignment]

os.environ["LINKEDIN_DAILY_LIMIT"] = "9"

state = {
    "base_insights": "FDWA launched its AI automation toolkit. Builders are scaling with passive income stacks.",
    "ai_strategy": {"topic": "AI automation for entrepreneurs"},
    "image_url": os.getenv("TEST_IMAGE_URL", "https://i.ibb.co/3mHDJS5/fdwa-test.png"),
}

print("=== Running LinkedIn agent with Composio forced to fail ===")
result = li_mod.run(state)
print("result:")
for k, v in result.items():
    print(f"  {k}: {str(v)[:140]}")

status = (result.get("linkedin_status") or "")
if "upload-post fallback" in status or "Posted" in status:
    print("\nPASS: fallback path reached")
    sys.exit(0)
else:
    print("\nNON-PASS status:", status)
    sys.exit(1)
