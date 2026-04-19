"""Buffer scheduling sub-agent (MCP transport).

Uses Buffer's official MCP server at https://mcp.buffer.com/mcp with a bearer
token. This replaces the hand-rolled GraphQL path so per-service metadata
(Pinterest boardServiceId/title/url, Instagram userTags, etc.) is validated
by Buffer's own schema and tool calls show up in LangSmith as child spans.

Env:
  BUFFER_API_KEY                  — Bearer token from Buffer dashboard
  BUFFER_MCP_URL                  — default https://mcp.buffer.com/mcp
  BUFFER_PINTEREST_SOURCE_URL     — default https://futuristicwealth.gumroad.com/
  BUFFER_PINTEREST_BOARD_SERVICE_ID — optional; else auto-pick "Cryptocurrency"
                                     or first board on the pinterest channel
  BUFFER_DEFAULT_MODE             — shareNow (default) | customScheduled
  BUFFER_CHANNEL_IDS              — optional csv to restrict targets

State keys read: buffer_text, tweet_text/linkedin_text/facebook_text, image_url,
video_url, buffer_scheduled_at.
State keys returned: buffer_status, buffer_post_ids.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MCP_URL = os.getenv("BUFFER_MCP_URL", "https://mcp.buffer.com/mcp")
DEFAULT_MODE = os.getenv("BUFFER_DEFAULT_MODE", "shareNow")
PINTEREST_SOURCE_URL = os.getenv(
    "BUFFER_PINTEREST_SOURCE_URL", "https://futuristicwealth.gumroad.com/"
)
FALLBACK_IMAGE_URL = os.getenv("BUFFER_FALLBACK_IMAGE_URL", "").strip() or None
IMMEDIATE_DELAY_SECS = int(os.getenv("BUFFER_IMMEDIATE_DELAY_SECS", "90"))

VIDEO_REQUIRED_SERVICES = {"tiktok", "youtube"}

_tools_cache: Optional[Dict[str, Any]] = None
_channels_cache: Optional[List[Dict[str, Any]]] = None
_boards_cache: Dict[str, List[Dict[str, Any]]] = {}
_org_id_cache: Optional[str] = None


def _token() -> Optional[str]:
    return os.getenv("BUFFER_API_KEY") or os.getenv("BUFFER_ACCESS_TOKEN")


def _now_plus_iso(seconds: int) -> str:
    dt = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _extract_text(raw: Any) -> str:
    """MCP tools return langchain ToolMessage content; pull the JSON text out."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict):
            return first.get("text") or ""
        return getattr(first, "text", "") or ""
    if isinstance(raw, dict):
        return raw.get("text") or json.dumps(raw)
    return str(raw)


def _parse(raw: Any) -> Any:
    txt = _extract_text(raw)
    try:
        return json.loads(txt)
    except Exception:
        return txt


async def _get_tools() -> Dict[str, Any]:
    global _tools_cache
    if _tools_cache is not None:
        return _tools_cache
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {
            "buffer": {
                "url": MCP_URL,
                "headers": {"Authorization": f"Bearer {_token() or ''}"},
                "transport": "streamable_http",
            }
        }
    )
    tools = await client.get_tools()
    _tools_cache = {t.name: t for t in tools}
    return _tools_cache


def _run_sync(coro):
    """Run a coroutine from sync code even if an event loop is already running."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Running loop: hand to a worker thread to avoid nested-loop error.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _get_account_org() -> Optional[str]:
    global _org_id_cache
    if _org_id_cache:
        return _org_id_cache
    tools = await _get_tools()
    acct = _parse(await tools["get_account"].ainvoke({}))
    orgs = (acct or {}).get("organizations") if isinstance(acct, dict) else []
    if orgs:
        _org_id_cache = orgs[0].get("id")
    return _org_id_cache


async def _list_channels_async() -> List[Dict[str, Any]]:
    global _channels_cache
    if _channels_cache is not None:
        return _channels_cache
    tools = await _get_tools()
    org = await _get_account_org()
    if not org:
        _channels_cache = []
        return _channels_cache
    data = _parse(await tools["list_channels"].ainvoke({"organizationId": org}))
    _channels_cache = data if isinstance(data, list) else []
    return _channels_cache


def list_channels(refresh: bool = False) -> List[Dict[str, Any]]:
    global _channels_cache
    if refresh:
        _channels_cache = None
    return _run_sync(_list_channels_async())


async def _pinterest_board_service_id(channel_id: str) -> Optional[str]:
    override = os.getenv("BUFFER_PINTEREST_BOARD_SERVICE_ID")
    if override:
        return override
    if channel_id in _boards_cache:
        boards = _boards_cache[channel_id]
    else:
        tools = await _get_tools()
        ch = _parse(await tools["get_channel"].ainvoke({"channelId": channel_id}))
        boards = ((ch or {}).get("metadata") or {}).get("boards") or []
        _boards_cache[channel_id] = boards
    if not boards:
        return None
    for b in boards:
        if "crypto" in (b.get("name") or "").lower():
            return b.get("serviceId")
    return boards[0].get("serviceId")


_EMOJI_RE = __import__("re").compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F600-\U0001F64F\u2700-\u27BF\uFE0F]",
)


def _pin_title(text: str) -> str:
    """Pinterest pin titles: ≤100 chars, no emojis, no URLs, no leading '#'."""
    import re

    first = (text or "").strip().splitlines()[0] if text else ""
    s = first or text or "FDWA Update"
    s = re.sub(r"https?://\S+", "", s)
    s = _EMOJI_RE.sub("", s)
    s = re.sub(r"#\S+", "", s)
    s = re.sub(r"\s+", " ", s).strip(" .,:;-|")
    if not s:
        s = "FDWA Update"
    return s[:100]


async def _create_one(
    *,
    channel: Dict[str, Any],
    text: str,
    image_url: Optional[str],
    video_url: Optional[str],
    mode: str,
    due_at: Optional[str],
) -> Dict[str, Any]:
    tools = await _get_tools()
    svc = (channel.get("service") or "").lower()
    cid = channel.get("id")

    if svc in VIDEO_REQUIRED_SERVICES and not video_url:
        return {"service": svc, "skipped": True, "reason": "no video"}
    if svc == "pinterest" and not image_url:
        return {"service": svc, "skipped": True, "reason": "no image (pinterest requires image)"}

    args: Dict[str, Any] = {
        "channelId": cid,
        "schedulingType": "automatic",
        "mode": mode,
        "text": (text or "")[:2000],
    }
    if mode == "customScheduled":
        args["dueAt"] = due_at or _now_plus_iso(IMMEDIATE_DELAY_SECS)

    assets: Dict[str, Any] = {}
    if video_url:
        assets["videos"] = [{"url": video_url}]
    elif image_url:
        assets["images"] = [
            {"url": image_url, "metadata": {"altText": _pin_title(text)}}
        ]
    if assets:
        args["assets"] = assets

    if svc == "pinterest":
        board_id = await _pinterest_board_service_id(cid)
        if not board_id:
            return {"service": svc, "success": False, "error": "no pinterest board"}
        args["metadata"] = {
            "pinterest": {
                "title": _pin_title(text),
                "url": PINTEREST_SOURCE_URL,
                "boardServiceId": board_id,
            }
        }

    try:
        raw = await tools["create_post"].ainvoke(args)
        data = _parse(raw)
    except Exception as e:
        return {"service": svc, "success": False, "error": f"{type(e).__name__}: {e}"[:200]}

    if isinstance(data, dict) and data.get("id"):
        return {"service": svc, "success": True, "post_id": data.get("id"), "raw": data}
    if isinstance(data, dict) and (data.get("message") or data.get("error")):
        return {"service": svc, "success": False, "error": str(data.get("message") or data.get("error"))[:200]}
    return {"service": svc, "success": True, "post_id": None, "raw": data}


async def _create_update_async(
    text: str,
    image_url: Optional[str],
    video_url: Optional[str],
    scheduled_at: Optional[str],
    channel_ids: Optional[List[str]],
) -> Dict[str, Any]:
    if not _token():
        return {"success": False, "error": "BUFFER_API_KEY not set"}
    if not (text or "").strip():
        return {"success": False, "error": "empty text"}

    all_channels = await _list_channels_async()
    if channel_ids:
        wanted = set(channel_ids)
        channels = [c for c in all_channels if c.get("id") in wanted]
    else:
        explicit = os.getenv("BUFFER_CHANNEL_IDS", "").strip()
        if explicit:
            wanted = {c.strip() for c in explicit.split(",") if c.strip()}
            channels = [c for c in all_channels if c.get("id") in wanted]
        else:
            channels = all_channels

    if not channels:
        return {"success": False, "error": "no Buffer channels resolved"}

    mode = "customScheduled" if scheduled_at else DEFAULT_MODE

    results = await asyncio.gather(
        *[
            _create_one(
                channel=c,
                text=text,
                image_url=image_url,
                video_url=video_url,
                mode=mode,
                due_at=scheduled_at,
            )
            for c in channels
        ],
        return_exceptions=False,
    )

    post_ids: List[str] = []
    errors: List[str] = []
    skipped: List[str] = []
    by_service: Dict[str, str] = {}
    for r in results:
        svc = r.get("service", "unknown")
        if r.get("skipped"):
            reason = r.get("reason", "skipped")
            skipped.append(f"{svc}({reason})")
            short = "no-video" if "video" in reason else ("no-image" if "image" in reason else "skipped")
            by_service[svc] = f"skipped({short})"
            continue
        if r.get("success"):
            by_service[svc] = "posted"
            if r.get("post_id"):
                post_ids.append(r["post_id"])
        else:
            err = str(r.get("error", "unknown"))[:80]
            errors.append(f"{svc}: {err}")
            by_service[svc] = f"fail({err[:30]})"

    out: Dict[str, Any] = {"by_service": by_service, "post_ids": post_ids}
    if post_ids and not errors:
        out["success"] = True
        if skipped:
            out["skipped"] = skipped
        return out
    if post_ids and errors:
        out["success"] = True
        out["partial_errors"] = errors
        if skipped:
            out["skipped"] = skipped
        return out
    out["success"] = False
    out["error"] = "; ".join(errors) or (
        f"all channels skipped: {', '.join(skipped)}" if skipped else "no posts created"
    )
    return out


def create_update(
    text: str,
    image_url: Optional[str] = None,
    scheduled_at: Optional[str] = None,
    channel_ids: Optional[List[str]] = None,
    video_url: Optional[str] = None,
) -> Dict[str, Any]:
    return _run_sync(
        _create_update_async(text, image_url, video_url, scheduled_at, channel_ids)
    )


def post_now(
    text: str,
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
    channel_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return create_update(
        text=text,
        image_url=image_url,
        video_url=video_url,
        scheduled_at=None,
        channel_ids=channel_ids,
    )


def schedule_post(
    text: str,
    when: str | datetime,
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
    channel_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if isinstance(when, datetime):
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        iso = when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    else:
        iso = str(when).strip()
    return create_update(
        text=text,
        image_url=image_url,
        video_url=video_url,
        scheduled_at=iso,
        channel_ids=channel_ids,
    )


def run(state: dict) -> dict:
    logger.info("--- BUFFER AGENT (MCP) ---")
    if not _token():
        return {"buffer_status": "Skipped: BUFFER_API_KEY not set", "buffer_post_ids": []}

    text = (
        state.get("buffer_text")
        or state.get("tweet_text")
        or state.get("linkedin_text")
        or state.get("facebook_text")
        or ""
    )
    if not text:
        return {"buffer_status": "Skipped: no text to post", "buffer_post_ids": []}

    image_url = state.get("image_url")
    if image_url and str(image_url).startswith("file://"):
        logger.warning("Buffer: dropping local file:// image_url (need public HTTPS)")
        image_url = None
    if not image_url and FALLBACK_IMAGE_URL:
        logger.info("Buffer: using BUFFER_FALLBACK_IMAGE_URL so Pinterest can still post")
        image_url = FALLBACK_IMAGE_URL
    video_url = state.get("video_url") or None
    scheduled_at = state.get("buffer_scheduled_at")
    logger.info(
        "Buffer input: text_len=%d image=%s video=%s scheduled_at=%s",
        len(text), bool(image_url), bool(video_url), scheduled_at,
    )

    result = create_update(
        text=text[:2000],
        image_url=image_url,
        video_url=video_url,
        scheduled_at=scheduled_at,
    )
    by_service = result.get("by_service") or {}
    svc_summary = ", ".join(f"{k}={v}" for k, v in by_service.items()) or "no channels"

    if result.get("success"):
        ids = result.get("post_ids") or []
        partial = result.get("partial_errors")
        skipped = result.get("skipped") or []
        status = f"Posted {len(ids)}: {svc_summary}"
        if partial:
            status += f" | partial-fail: {len(partial)}"
        if skipped:
            status += f" | skipped: {len(skipped)}"
        logger.info("Buffer: %s", status)
        return {"buffer_status": status[:500], "buffer_post_ids": ids}
    err = result.get("error", "Unknown")
    logger.error("Buffer failed: %s | services=%s", err, svc_summary)
    return {"buffer_status": f"Failed: {svc_summary} | {err[:180]}", "buffer_post_ids": []}
