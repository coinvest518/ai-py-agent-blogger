"""Pipedream MCP client — fallback transport for when Composio fails.

Pipedream exposes 3,000+ apps via one MCP endpoint
(https://remote.mcp.pipedream.net/v3); the target app is selected per-request
via the `x-pd-app-slug` header. Users connect their accounts via a returned
Connect Link URL (no frontend needed).

Env:
  PIPEDREAM_CLIENT_ID / PIPEDREAM_CLIENT_SECRET — developer OAuth creds
  PIPEDREAM_PROJECT_ID        — proj_xxxxxxx
  PIPEDREAM_ENVIRONMENT       — development | production
  PIPEDREAM_EXTERNAL_USER_ID  — per-end-user id (we use a single "fdwa-owner")

Returns a ConnectLinkRequired marker dict when the user hasn't authorized yet;
callers should surface the URL (Telegram/Notion) and retry after auth.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

MCP_URL = os.getenv("PIPEDREAM_MCP_URL", "https://remote.mcp.pipedream.net/v3")
TOKEN_URL = "https://api.pipedream.com/v1/oauth/token"

_token_cache: Dict[str, Any] = {"value": None, "exp": 0}
_tools_cache: Dict[str, Dict[str, Any]] = {}


def _client_creds() -> Optional[Dict[str, str]]:
    cid = os.getenv("PIPEDREAM_CLIENT_ID")
    sec = os.getenv("PIPEDREAM_CLIENT_SECRET")
    proj = os.getenv("PIPEDREAM_PROJECT_ID")
    env = os.getenv("PIPEDREAM_ENVIRONMENT", "development")
    ext = os.getenv("PIPEDREAM_EXTERNAL_USER_ID", "fdwa-owner")
    if not (cid and sec and proj):
        return None
    return {"client_id": cid, "client_secret": sec, "project_id": proj, "environment": env, "external_user_id": ext}


def _access_token() -> Optional[str]:
    now = time.time()
    if _token_cache["value"] and _token_cache["exp"] > now + 60:
        return _token_cache["value"]
    creds = _client_creds()
    if not creds:
        return None
    try:
        r = requests.post(
            TOKEN_URL,
            json={
                "grant_type": "client_credentials",
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        _token_cache["value"] = data["access_token"]
        _token_cache["exp"] = now + int(data.get("expires_in", 3300))
        return _token_cache["value"]
    except Exception as e:
        logger.warning("Pipedream token fetch failed: %s", e)
        return None


def _headers(app_slug: str) -> Optional[Dict[str, str]]:
    tok = _access_token()
    creds = _client_creds()
    if not (tok and creds):
        return None
    return {
        "Authorization": f"Bearer {tok}",
        "x-pd-project-id": creds["project_id"],
        "x-pd-environment": creds["environment"],
        "x-pd-external-user-id": creds["external_user_id"],
        "x-pd-app-slug": app_slug,
    }


async def _get_tools_async(app_slug: str) -> Dict[str, Any]:
    if app_slug in _tools_cache:
        return _tools_cache[app_slug]
    headers = _headers(app_slug)
    if not headers:
        return {}
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {"pd": {"url": MCP_URL, "headers": headers, "transport": "streamable_http"}}
    )
    tools = await client.get_tools()
    _tools_cache[app_slug] = {t.name: t for t in tools}
    return _tools_cache[app_slug]


def _run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


_CONNECT_RE = re.compile(r"https://pipedream\.com/_static/connect\.html\?token=ctok_[a-zA-Z0-9]+[^\s]*")


def _parse_response(raw: Any) -> Dict[str, Any]:
    """Normalize MCP tool return into {success, data, connect_url, error}."""
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

    m = _CONNECT_RE.search(text or "")
    if m:
        return {"success": False, "connect_url": m.group(0), "error": "connect required"}

    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("error"):
            return {"success": False, "error": str(data["error"])[:300], "data": data}
        return {"success": True, "data": data}
    except Exception:
        return {"success": True, "data": text}


async def _call_tool_async(app_slug: str, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    tools = await _get_tools_async(app_slug)
    if not tools:
        return {"success": False, "error": "Pipedream not configured"}
    tool = tools.get(tool_name)
    if not tool:
        return {"success": False, "error": f"tool {tool_name} not found for {app_slug}", "available": list(tools.keys())[:20]}
    try:
        raw = await tool.ainvoke(args)
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"[:300]}
    return _parse_response(raw)


def call_tool(app_slug: str, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Sync wrapper — call a Pipedream MCP tool."""
    return _run_sync(_call_tool_async(app_slug, tool_name, args))


def list_tools(app_slug: str) -> List[str]:
    return list(_run_sync(_get_tools_async(app_slug)).keys())


def is_configured() -> bool:
    return _client_creds() is not None


# ── Option resolver (for apps whose create-post requires a page/account id) ──

_option_cache: Dict[str, str] = {}


async def _first_option_value(app_slug: str, key: str, prop_name: str) -> Optional[str]:
    """Call retrieve_options and return the first option's value. Cached."""
    cache_key = f"{app_slug}:{key}:{prop_name}"
    if cache_key in _option_cache:
        return _option_cache[cache_key]
    tools = await _get_tools_async(app_slug)
    tool = tools.get("retrieve_options")
    if not tool:
        return None
    try:
        raw = await tool.ainvoke({"key": key, "propName": prop_name})
    except Exception as e:
        logger.warning("retrieve_options failed for %s.%s: %s", app_slug, key, e)
        return None
    parsed = _parse_response(raw)
    data = parsed.get("data")
    options: List[Any] = []
    if isinstance(data, dict):
        options = data.get("options") or data.get("items") or data.get("results") or []
    elif isinstance(data, list):
        options = data
    if not options:
        return None
    first = options[0]
    val = (
        first.get("value")
        if isinstance(first, dict)
        else first
    )
    if val:
        _option_cache[cache_key] = str(val)
    return str(val) if val else None


# ── Convenience wrappers ──────────────────────────────────────────────────

def post_linkedin_text(text: str, visibility: str = "PUBLIC", article_url: Optional[str] = None) -> Dict[str, Any]:
    """Fallback LinkedIn text post via Pipedream."""
    args: Dict[str, Any] = {"visibility": visibility, "text": text[:2900]}
    if article_url:
        args["article"] = article_url
    return call_tool("linkedin", "linkedin-create-text-post-user", args)


def post_linkedin_image(text: str, image_url: str, visibility: str = "PUBLIC") -> Dict[str, Any]:
    """Fallback LinkedIn image post via Pipedream. `file` accepts a URL."""
    return call_tool(
        "linkedin",
        "linkedin-create-image-post-user",
        {"visibility": visibility, "text": text[:2900], "file": image_url},
    )


async def _post_facebook_async(message: str, link: Optional[str] = None) -> Dict[str, Any]:
    page = os.getenv("PIPEDREAM_FACEBOOK_PAGE")
    if not page:
        page = await _first_option_value("facebook_pages", "facebook_pages-create-post", "page")
    if not page:
        return {"success": False, "error": "no facebook page available"}
    args: Dict[str, Any] = {"page": page}
    if message:
        args["message"] = message[:5000]
    if link:
        args["link"] = link
    res = await _call_tool_async("facebook_pages", "facebook_pages-create-post", args)
    return res


def post_facebook_page(message: str, link: Optional[str] = None) -> Dict[str, Any]:
    return _run_sync(_post_facebook_async(message, link))


async def _post_instagram_async(caption: str, image_url: str, media_type: str = "IMAGE") -> Dict[str, Any]:
    page = os.getenv("PIPEDREAM_INSTAGRAM_PAGE")
    if not page:
        page = await _first_option_value("instagram_business", "instagram_business-create-post", "page")
    if not page:
        return {"success": False, "error": "no instagram business account available"}
    args = {"page": page, "mediaType": media_type, "url": image_url}
    if caption:
        args["caption"] = caption[:2200]
    return await _call_tool_async("instagram_business", "instagram_business-create-post", args)


def post_instagram(caption: str, image_url: str, media_type: str = "IMAGE") -> Dict[str, Any]:
    return _run_sync(_post_instagram_async(caption, image_url, media_type))


def send_gmail(to: List[str], subject: str, body: str, body_type: str = "html") -> Dict[str, Any]:
    return call_tool(
        "gmail",
        "gmail-send-email",
        {"to": to, "subject": subject[:200], "body": body, "bodyType": body_type},
    )
