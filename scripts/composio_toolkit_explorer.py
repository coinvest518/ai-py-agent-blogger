"""Composio Toolkit Explorer — list tool slugs & schemas for any toolkit.

Uses the same Composio client the agent uses so whatever slugs/versions we
discover here are what the agent will actually see at runtime. Useful when
you want to add a new Composio integration and need the exact tool name and
argument shape.

Examples:
    # list all toolkits available to our API key
    .venv/Scripts/python.exe scripts/composio_toolkit_explorer.py --list-toolkits

    # list tools in a toolkit (e.g. googlesheets, googledrive, linkedin)
    .venv/Scripts/python.exe scripts/composio_toolkit_explorer.py --toolkit googlesheets

    # show schema for one tool slug
    .venv/Scripts/python.exe scripts/composio_toolkit_explorer.py --tool GOOGLESHEETS_BATCH_UPDATE

    # dump every toolkit's tool slugs to scripts/composio_inventory.json
    .venv/Scripts/python.exe scripts/composio_toolkit_explorer.py --dump

The resulting JSON can be fed to agents (or future skill files) so they know
exactly which slugs exist without us hand-maintaining a list.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv

load_dotenv()

from src.agent.tools.composio_tools import get_composio_client


_USER_ID = (
    os.getenv("COMPOSIO_ENTITY_ID")
    or os.getenv("GOOGLESHEETS_USER_ID")
    or "default"
)


def _client():
    c = get_composio_client()
    if not c:
        print("ERROR: Composio client unavailable (COMPOSIO_API_KEY missing?)")
        sys.exit(2)
    return c


def list_toolkits() -> list[dict]:
    c = _client()
    try:
        rows = c.toolkits.list()
    except Exception as e:
        print(f"ERROR listing toolkits: {e}")
        return []
    out = []
    items = getattr(rows, "items", None) or rows
    for row in items or []:
        name = getattr(row, "slug", None) or getattr(row, "name", None) or str(row)
        out.append({
            "slug": name,
            "name": getattr(row, "name", name),
            "description": (getattr(row, "description", "") or "")[:200],
        })
    return out


def _raw_tools(toolkit: str | None = None) -> list[dict]:
    """Use tools.get_raw_composio_tools which returns the full schema objects."""
    c = _client()
    try:
        rows = c.tools.get_raw_composio_tools(toolkits=[toolkit] if toolkit else None)
    except Exception as e:
        print(f"ERROR get_raw_composio_tools: {e}")
        return []
    out = []
    for row in rows or []:
        slug = getattr(row, "slug", None) or getattr(row, "name", None) or str(row)
        tkit = getattr(row, "toolkit", None)
        tkit_slug = getattr(tkit, "slug", None) or getattr(tkit, "name", None) or (tkit if isinstance(tkit, str) else "")
        out.append({
            "slug": slug,
            "toolkit": tkit_slug,
            "description": (getattr(row, "description", "") or "")[:200],
        })
    return out


def list_tools(toolkit: str | None = None, limit: int = 500) -> list[dict]:
    out = _raw_tools(toolkit=toolkit)
    return out[:limit]


def show_tool(slug: str) -> dict | None:
    c = _client()
    try:
        row = c.tools.get_raw_composio_tool_by_slug(slug)
    except Exception as e:
        return {"slug": slug, "error": str(e)}
    if not row:
        return None
    schema = getattr(row, "input_parameters", None) or getattr(row, "schema", None)
    try:
        if schema is not None and hasattr(schema, "model_dump"):
            schema = schema.model_dump()
    except Exception:
        pass
    return {
        "slug": getattr(row, "slug", slug),
        "toolkit": getattr(getattr(row, "toolkit", None), "slug", None),
        "description": getattr(row, "description", ""),
        "input_parameters": schema,
    }


def dump_all(outfile: Path) -> None:
    toolkits = list_toolkits()
    inventory: dict[str, list[dict]] = {}
    names = [t["name"] for t in toolkits] or [
        "googlesheets", "googledrive", "gmail", "linkedin", "twitter",
        "facebook", "instagram", "telegram", "notion",
    ]
    for name in names:
        try:
            tools = list_tools(name)
            inventory[name] = tools
            print(f"  {name}: {len(tools)} tools")
        except Exception as e:
            print(f"  {name}: failed — {e}")
    outfile.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    total = sum(len(v) for v in inventory.values())
    print(f"\n✅ Wrote {total} tools across {len(inventory)} toolkits → {outfile}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--list-toolkits", action="store_true")
    p.add_argument("--toolkit", help="Show tools for one toolkit (e.g. googlesheets)")
    p.add_argument("--tool", help="Show schema for one tool slug (e.g. GOOGLESHEETS_BATCH_UPDATE)")
    p.add_argument("--dump", action="store_true", help="Dump full inventory JSON")
    p.add_argument("--out", default="scripts/composio_inventory.json")
    args = p.parse_args()

    if not (args.list_toolkits or args.toolkit or args.tool or args.dump):
        p.print_help()
        return 0

    if args.list_toolkits:
        for tk in list_toolkits():
            print(f"- {tk['name']}")
        return 0

    if args.toolkit:
        tools = list_tools(args.toolkit)
        if not tools:
            print(f"(no tools returned for '{args.toolkit}')")
            return 0
        print(f"{args.toolkit} — {len(tools)} tools:")
        for t in tools:
            print(f"  {t['slug']}")
            if t["description"]:
                print(f"     {t['description']}")
        return 0

    if args.tool:
        info = show_tool(args.tool)
        print(json.dumps(info or {"slug": args.tool, "error": "not found"}, indent=2, default=str))
        return 0

    if args.dump:
        dump_all(Path(args.out))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
