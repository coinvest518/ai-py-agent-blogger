"""Google Sheets smoke test via Composio — create sheet, append data, read back.

Exercises the full read/write loop the agent would use for learning:
 1. Create a new spreadsheet
 2. Append a header row + data rows (simulate learning metrics)
 3. Read it back to confirm round-trip
"""
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
TITLE = f"FDWA Agent Learning Log {STAMP}"


def test_create():
    print("\n=== 1. Create spreadsheet ===")
    result = _execute_with_fallback(
        "GOOGLESHEETS_CREATE_GOOGLE_SHEET1",
        {"title": TITLE},
        ENTITY,
    )
    print(f"  successful: {result.get('successful')}")
    data = result.get("data") or {}
    # Composio returns a `response_data` nested dict on CREATE
    rd = data.get("response_data") or data
    sid = rd.get("spreadsheetId") or rd.get("spreadsheet_id") or data.get("spreadsheetId")
    print(f"  spreadsheet_id: {sid}")
    if not result.get("successful"):
        print(f"  error: {str(result.get('error',''))[:300]}")
    return sid


def test_append(sid: str):
    print("\n=== 2. Append header + data rows ===")
    if not sid:
        print("  skipped: no spreadsheet_id")
        return False
    rows = [
        ["timestamp", "platform", "topic", "success", "notes"],
        [STAMP, "linkedin", "AI automation", "true", "posted normally"],
        [STAMP, "telegram", "AI automation", "true", "posted normally"],
        [STAMP, "facebook", "AI automation", "true", "posted normally"],
        [STAMP, "instagram", "AI automation", "false", "media URL rejected by Meta"],
    ]
    result = _execute_with_fallback(
        "GOOGLESHEETS_VALUES_UPDATE",
        {
            "spreadsheet_id": sid,
            "values": rows,
            "range": "Sheet1!A1",
            "valueInputOption": "RAW",
        },
        ENTITY,
    )
    if not result.get("successful"):
        # Fallback to deprecated but known-working BATCH_UPDATE
        result = _execute_with_fallback(
            "GOOGLESHEETS_BATCH_UPDATE",
            {
                "spreadsheet_id": sid,
                "values": rows,
                "first_cell_location": "A1",
                "sheet_name": "Sheet1",
                "valueInputOption": "RAW",
                "includeValuesInResponse": False,
            },
            ENTITY,
        )
    print(f"  successful: {result.get('successful')}")
    if not result.get("successful"):
        print(f"  error: {str(result.get('error',''))[:300]}")
    return result.get("successful")


def test_read(sid: str):
    print("\n=== 3. Read values back ===")
    if not sid:
        print("  skipped")
        return False
    result = _execute_with_fallback(
        "GOOGLESHEETS_BATCH_GET",
        {"spreadsheet_id": sid, "ranges": ["Sheet1!A1:E10"]},
        ENTITY,
    )
    print(f"  successful: {result.get('successful')}")
    data = result.get("data") or {}
    value_ranges = data.get("valueRanges") or data.get("value_ranges") or []
    if value_ranges:
        values = value_ranges[0].get("values") or []
        for row in values[:6]:
            print(f"  {row}")
    else:
        print(f"  raw data: {str(data)[:300]}")
    return result.get("successful")


def main() -> int:
    sid = test_create()
    test_append(sid)
    test_read(sid)
    if sid:
        print(f"\nOpen: https://docs.google.com/spreadsheets/d/{sid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
