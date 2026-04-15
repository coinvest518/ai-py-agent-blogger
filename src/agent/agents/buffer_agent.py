"""Buffer scheduling sub-agent (GraphQL API).

Buffer migrated from `api.bufferapp.com/1/*` REST to `api.buffer.com` GraphQL.
This agent uses the new GraphQL surface with a Bearer API key.

Env:
  BUFFER_API_KEY     — Bearer token from Buffer developer dashboard
  BUFFER_CHANNEL_IDS (optional) — comma-separated channel IDs to post to;
    otherwise every channel under every organization is used.

State keys read:
  buffer_text           — post body (falls back to tweet_text / linkedin_text)
  image_url             — public image URL attached as `assets.images[]`
  buffer_scheduled_at   — ISO-8601; if present, uses `schedulingType: custom`
                          otherwise `mode: addToQueue` (appends to profile queue)

Returns state keys:
  buffer_status, buffer_post_ids
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

API_URL = "https://api.buffer.com"
_channels_cache: Optional[List[Dict[str, Any]]] = None

# Default posting mode when state["buffer_scheduled_at"] is NOT provided.
# Values:
#   "immediate"  (default) — customScheduled with dueAt ≈ now + IMMEDIATE_DELAY_SECS
#                             so Buffer publishes as soon as its scheduler picks it up
#   "queue"                 — addToQueue; Buffer uses the channel's posting schedule
BUFFER_DEFAULT_MODE = os.getenv("BUFFER_DEFAULT_MODE", "immediate").lower()
IMMEDIATE_DELAY_SECS = int(os.getenv("BUFFER_IMMEDIATE_DELAY_SECS", "90"))


def _now_plus_iso(seconds: int) -> str:
    """Return ISO-8601 UTC timestamp for `seconds` from now (Buffer-accepted)."""
    dt = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _token() -> Optional[str]:
    return os.getenv("BUFFER_API_KEY") or os.getenv("BUFFER_ACCESS_TOKEN")


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_token() or ''}",
        "Content-Type": "application/json",
    }


def _gql(query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not _token():
        return {"error": "BUFFER_API_KEY not set"}
    payload = {"query": query, "variables": variables or {}}
    try:
        r = requests.post(API_URL, headers=_headers(), json=payload, timeout=30)
    except Exception as e:
        return {"error": f"Request exception: {e}"}
    if r.status_code >= 400:
        return {"error": f"HTTP {r.status_code}: {r.text[:240]}"}
    body = r.json()
    if body.get("errors"):
        return {"error": str(body["errors"])[:240], "data": body.get("data")}
    return body


def _list_organizations() -> List[str]:
    res = _gql("query { account { organizations { id } } }")
    if "error" in res:
        logger.warning("Buffer organizations query failed: %s", res["error"])
        return []
    data = ((res.get("data") or {}).get("account") or {}).get("organizations") or []
    return [str(o.get("id")) for o in data if o.get("id")]


def list_channels(refresh: bool = False) -> List[Dict[str, Any]]:
    """Return all channels across every organization in the account (cached)."""
    global _channels_cache
    if _channels_cache is not None and not refresh:
        return _channels_cache
    channels: List[Dict[str, Any]] = []
    for org_id in _list_organizations():
        res = _gql(
            "query($orgId: OrganizationId!) { channels(input: {organizationId: $orgId}) { id name service } }",
            {"orgId": org_id},
        )
        if "error" in res:
            logger.warning("Buffer channels query failed for %s: %s", org_id, res["error"])
            continue
        for c in (res.get("data") or {}).get("channels") or []:
            if c.get("id"):
                channels.append({"id": c["id"], "name": c.get("name"), "service": c.get("service"), "organization_id": org_id})
    _channels_cache = channels
    return channels


def _target_channel_ids() -> List[str]:
    explicit = os.getenv("BUFFER_CHANNEL_IDS", "").strip()
    if explicit:
        return [c.strip() for c in explicit.split(",") if c.strip()]
    return [c["id"] for c in list_channels()]


# Services that REQUIRE a video — skip if no video_url available
VIDEO_REQUIRED_SERVICES = {"tiktok", "youtube"}

# Services that accept image+text (video also accepted where platform allows)
IMAGE_SERVICES = {
    "pinterest", "googlebusiness", "instagram", "facebook",
    "threads", "bluesky", "mastodon", "start_page", "linkedin",
}

# Services that are text-first (image optional)
TEXT_SERVICES = {"twitter", "threads", "bluesky", "mastodon"}


def _pick_assets(service: str, image_url: Optional[str], video_url: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return the assets dict Buffer expects for this channel's service.

    - Video-required services (TikTok, YouTube): return video asset or None (skip).
    - Image services: return image asset if we have one.
    - Text services: attach image if available, else no assets.
    """
    svc = (service or "").lower()
    if svc in VIDEO_REQUIRED_SERVICES:
        if video_url:
            return {"video": {"url": video_url}}
        return None  # signal: skip this channel
    # Non-video channels: prefer image if present
    if image_url:
        return {"images": [{"url": image_url}]}
    return {}  # empty = text-only


CREATE_POST_MUTATION = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess {
      post { id text }
    }
    ... on MutationError {
      message
    }
  }
}
"""


def create_post_on_channel(
    channel_id: str,
    text: str,
    image_url: Optional[str] = None,
    scheduled_at: Optional[str] = None,
    video_url: Optional[str] = None,
    service: Optional[str] = None,
) -> Dict[str, Any]:
    """Create one post on a single channel. Returns {success, post_id, error, skipped}.

    If `service` is a video-only platform (TikTok/YouTube) and no `video_url`
    is provided, returns {success: False, skipped: True, reason: ...} so the
    caller can distinguish "we chose not to post" from "it failed".
    """
    assets = _pick_assets(service or "", image_url, video_url)
    if assets is None:
        return {"success": False, "skipped": True, "reason": f"{service} requires video"}

    input_obj: Dict[str, Any] = {
        "channelId": channel_id,
        "text": text,
        "schedulingType": "automatic",
    }

    # Mode resolution:
    #   1. Explicit scheduled_at (ISO-8601) → customScheduled at that time
    #   2. BUFFER_DEFAULT_MODE=immediate   → customScheduled at now+IMMEDIATE_DELAY_SECS
    #   3. BUFFER_DEFAULT_MODE=queue       → addToQueue (uses channel's posting schedule)
    if scheduled_at:
        input_obj["mode"] = "customScheduled"
        input_obj["dueAt"] = scheduled_at
    elif BUFFER_DEFAULT_MODE == "queue":
        input_obj["mode"] = "addToQueue"
    else:
        input_obj["mode"] = "customScheduled"
        input_obj["dueAt"] = _now_plus_iso(IMMEDIATE_DELAY_SECS)

    if assets:
        input_obj["assets"] = assets

    res = _gql(CREATE_POST_MUTATION, {"input": input_obj})
    if "error" in res:
        return {"success": False, "error": res["error"]}
    payload = ((res.get("data") or {}).get("createPost") or {})
    if payload.get("message"):
        return {"success": False, "error": payload["message"]}
    post = payload.get("post") or {}
    return {"success": True, "post_id": post.get("id"), "response": payload}


def create_update(
    text: str,
    image_url: Optional[str] = None,
    scheduled_at: Optional[str] = None,
    channel_ids: Optional[List[str]] = None,
    video_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Fan-out a post to every configured channel, routing by service type.

    Video-only services (TikTok, YouTube) are SKIPPED unless `video_url` is
    set. Image-capable services get the image. Services get their per-type
    asset payload via `_pick_assets()`.
    """
    if not _token():
        return {"success": False, "error": "BUFFER_API_KEY not set"}
    if not text:
        return {"success": False, "error": "empty text"}

    # Resolve channels with their service type so we can route correctly.
    explicit = os.getenv("BUFFER_CHANNEL_IDS", "").strip()
    if channel_ids:
        all_channels = list_channels()
        id_to_svc = {c["id"]: c.get("service") for c in all_channels}
        resolved = [{"id": cid, "service": id_to_svc.get(cid, "")} for cid in channel_ids]
    elif explicit:
        all_channels = list_channels()
        id_to_svc = {c["id"]: c.get("service") for c in all_channels}
        resolved = [
            {"id": cid.strip(), "service": id_to_svc.get(cid.strip(), "")}
            for cid in explicit.split(",") if cid.strip()
        ]
    else:
        resolved = [{"id": c["id"], "service": c.get("service", "")} for c in list_channels()]

    if not resolved:
        return {"success": False, "error": "no Buffer channels resolved"}

    post_ids: List[str] = []
    errors: List[str] = []
    skipped: List[str] = []
    by_service: Dict[str, str] = {}

    for ch in resolved:
        cid = ch["id"]
        svc = (ch.get("service") or "unknown").lower()
        res = create_post_on_channel(
            channel_id=cid,
            text=text,
            image_url=image_url,
            scheduled_at=scheduled_at,
            video_url=video_url,
            service=svc,
        )
        if res.get("skipped"):
            skipped.append(f"{svc}({res.get('reason', 'skipped')})")
            by_service[svc] = "skipped(no-video)"
            continue
        if res.get("success") and res.get("post_id"):
            post_ids.append(res["post_id"])
            by_service[svc] = "queued"
        else:
            err = str(res.get("error", "unknown"))[:80]
            errors.append(f"{svc}:{cid[:6]}: {err}")
            by_service[svc] = f"fail({err[:30]})"

    result: Dict[str, Any] = {"by_service": by_service, "post_ids": post_ids}
    if post_ids and not errors:
        result["success"] = True
        if skipped:
            result["skipped"] = skipped
        return result
    if post_ids and errors:
        result["success"] = True
        result["partial_errors"] = errors
        if skipped:
            result["skipped"] = skipped
        return result
    result["success"] = False
    result["error"] = "; ".join(errors) or (f"all channels skipped: {', '.join(skipped)}" if skipped else "no posts created")
    return result


def post_now(
    text: str,
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
    channel_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Fire-and-forget immediate post. Uses customScheduled at now+IMMEDIATE_DELAY_SECS.

    Convenience wrapper the AI / Telegram /buffer_now can call to bypass the
    graph state. Returns the same shape as create_update.
    """
    return create_update(
        text=text,
        image_url=image_url,
        video_url=video_url,
        scheduled_at=_now_plus_iso(IMMEDIATE_DELAY_SECS),
        channel_ids=channel_ids,
    )


def schedule_post(
    text: str,
    when: str | datetime,
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
    channel_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Schedule a post for a specific time.

    Args:
        when: ISO-8601 string (e.g. "2026-03-10T15:00:00.000Z") OR a datetime
              (naive treated as UTC). Must be in the future.
    """
    if isinstance(when, datetime):
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        iso = when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
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
    """Graph-compatible entry — push a post to every linked Buffer channel."""
    logger.info("--- BUFFER AGENT ---")
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
        image_url = None
    video_url = state.get("video_url") or None
    scheduled_at = state.get("buffer_scheduled_at")

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
        status = f"Queued {len(ids)}: {svc_summary}"
        if partial:
            status += f" | partial-fail: {len(partial)}"
        if skipped:
            status += f" | skipped: {len(skipped)}"
        logger.info("Buffer: %s", status)
        return {"buffer_status": status[:500], "buffer_post_ids": ids}
    err = result.get("error", "Unknown")
    logger.error("Buffer failed: %s | services=%s", err, svc_summary)
    return {"buffer_status": f"Failed: {svc_summary} | {err[:180]}", "buffer_post_ids": []}
