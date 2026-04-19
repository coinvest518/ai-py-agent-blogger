"""Zernio MCP client — hosted multi-platform publisher.

Zernio (https://zernio.com) is a social scheduling aggregator with its own
MCP server at https://mcp.zernio.com/mcp. One bearer token, 14 platforms
(Twitter/X, LinkedIn, Instagram, TikTok, Bluesky, Facebook, YouTube,
Pinterest, Threads, Telegram, etc.), no per-platform OAuth.

We use it primarily for **Twitter/X** (since our direct + Composio paths
for X were removed), and as an optional transport for others.

Env:
  ZERNIO_API_KEY        — bearer token from zernio.com/dashboard/api-keys
  ZERNIO_MCP_URL        — default https://mcp.zernio.com/mcp
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MCP_URL = os.getenv("ZERNIO_MCP_URL", "https://mcp.zernio.com/mcp")

_tools_cache: Optional[Dict[str, Any]] = None


def is_configured() -> bool:
    return bool(os.getenv("ZERNIO_API_KEY"))


def _headers() -> Optional[Dict[str, str]]:
    key = os.getenv("ZERNIO_API_KEY")
    if not key:
        return None
    return {"Authorization": f"Bearer {key}"}


async def _get_tools_async() -> Dict[str, Any]:
    global _tools_cache
    if _tools_cache is not None:
        return _tools_cache
    headers = _headers()
    if not headers:
        _tools_cache = {}
        return _tools_cache
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {"zernio": {"url": MCP_URL, "headers": headers, "transport": "streamable_http"}}
    )
    tools = await client.get_tools()
    _tools_cache = {t.name: t for t in tools}
    return _tools_cache


def _run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _parse(raw: Any) -> Dict[str, Any]:
    text = ""
    if isinstance(raw, list) and raw:
        first = raw[0]
        text = first.get("text") if isinstance(first, dict) else getattr(first, "text", "")
    elif isinstance(raw, str):
        text = raw
    elif isinstance(raw, dict):
        text = raw.get("text") or json.dumps(raw)
    else:
        text = str(raw)
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("error"):
            return {"success": False, "error": str(data["error"])[:300], "data": data}
        return {"success": True, "data": data, "raw": text}
    except Exception:
        low = (text or "").lower()
        failed = any(k in low for k in ("error", "failed", "invalid", "unauthorized"))
        return {"success": not failed and bool(text), "data": text, "raw": text}


async def _call_async(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    tools = await _get_tools_async()
    if not tools:
        return {"success": False, "error": "Zernio not configured"}
    tool = tools.get(tool_name)
    if not tool:
        return {"success": False, "error": f"tool {tool_name} not found", "available": list(tools.keys())[:30]}
    try:
        raw = await tool.ainvoke(args)
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"[:300]}
    return _parse(raw)


def call_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    return _run_sync(_call_async(tool_name, args))


def list_tools() -> List[str]:
    return list(_run_sync(_get_tools_async()).keys())


def list_accounts() -> Dict[str, Any]:
    return call_tool("accounts_list", {})


# ── Convenience wrappers ──────────────────────────────────────────────────

def publish_now(content: str, platform: str, media_urls: Optional[List[str]] = None, title: str = "") -> Dict[str, Any]:
    args: Dict[str, Any] = {"content": content, "platform": platform}
    if media_urls:
        args["media_urls"] = ",".join(media_urls)
    if title:
        args["title"] = title
    return call_tool("posts_publish_now", args)


def cross_post(content: str, platforms: List[str], media_urls: Optional[List[str]] = None, publish_immediately: bool = True) -> Dict[str, Any]:
    args: Dict[str, Any] = {
        "content": content,
        "platforms": ",".join(platforms),
        "publish_now": publish_immediately,
    }
    if media_urls:
        args["media_urls"] = ",".join(media_urls)
    return call_tool("posts_cross_post", args)


def post_twitter(text: str, image_url: Optional[str] = None) -> Dict[str, Any]:
    media = [image_url] if image_url else None
    return publish_now(text[:280], "twitter", media_urls=media)
