"""Google Docs smoke test via Composio — create a run-summary doc, read it back."""
from __future__ import annotations

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

load_dotenv(override=True)

from src.agent.tools.composio_tools import _execute_with_fallback

ENTITY = os.getenv("COMPOSIO_ENTITY_ID")
STAMP = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

SUMMARY = f"""FDWA Agent Run Summary — {STAMP}

## What ran this cycle
- LinkedIn: Posted
- Telegram: Posted
- Facebook: Posted
- Instagram: Posted
- Blog: Emailed to blogger
- Twitter: (pending X portal)

## Topics covered
- AI automation, agent tooling, OpenClaw skills

## Products promoted
- x402 Payment Skill
- Alpaca AI Trading Agent

## Next actions
- Tune supervisor prompts
- Monitor engagement rollup
"""


def test_create():
    print("\n=== 1. Create Google Doc ===")
    result = _execute_with_fallback(
        "GOOGLEDOCS_CREATE_DOCUMENT_MARKDOWN",
        {
            "title": f"FDWA Run Summary {STAMP}",
            "markdown_text": SUMMARY,
        },
        ENTITY,
    )
    print(f"  successful: {result.get('successful')}")
    data = result.get("data") or {}
    doc_id = data.get("documentId") or data.get("document_id") or data.get("id") or ""
    print(f"  doc_id: {doc_id}")
    if not result.get("successful"):
        print(f"  error: {result.get('error','')[:300]}")
    return doc_id


def test_read(doc_id: str):
    print("\n=== 2. Read Google Doc back ===")
    if not doc_id:
        print("  skipped: no doc_id")
        return False
    result = _execute_with_fallback(
        "GOOGLEDOCS_GET_DOCUMENT_PLAINTEXT",
        {"document_id": doc_id},
        ENTITY,
    )
    print(f"  successful: {result.get('successful')}")
    data = result.get("data") or {}
    text = (data.get("text") or data.get("plain_text") or "")[:400]
    print(f"  text (first 400 chars):\n{text}")
    return result.get("successful")


def main() -> int:
    doc_id = test_create()
    test_read(doc_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
