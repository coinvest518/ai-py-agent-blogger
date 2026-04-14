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
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

API_URL = "https://api.buffer.com"
_channels_cache: Optional[List[Dict[str, Any]]] = None


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


CREATE_POST_MUTATION = """
mutation CreatePost($input: PostCreateInput!) {
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
) -> Dict[str, Any]:
    """Create one post on a single channel. Returns {success, post_id, error}."""
    input_obj: Dict[str, Any] = {
        "channelId": channel_id,
        "text": text,
    }
    if scheduled_at:
        input_obj["schedulingType"] = "custom"
        input_obj["scheduledAt"] = scheduled_at
    else:
        input_obj["schedulingType"] = "automatic"
        input_obj["mode"] = "addToQueue"
    if image_url:
        input_obj["assets"] = {"images": [{"url": image_url}]}

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
) -> Dict[str, Any]:
    """Fan-out a post to every configured channel."""
    if not _token():
        return {"success": False, "error": "BUFFER_API_KEY not set"}
    if not text:
        return {"success": False, "error": "empty text"}

    ids = channel_ids or _target_channel_ids()
    if not ids:
        return {"success": False, "error": "no Buffer channels resolved"}

    post_ids: List[str] = []
    errors: List[str] = []
    for cid in ids:
        res = create_post_on_channel(cid, text, image_url, scheduled_at)
        if res.get("success") and res.get("post_id"):
            post_ids.append(res["post_id"])
        else:
            errors.append(f"{cid}: {res.get('error', 'unknown')[:80]}")

    if post_ids and not errors:
        return {"success": True, "post_ids": post_ids}
    if post_ids and errors:
        return {"success": True, "post_ids": post_ids, "partial_errors": errors}
    return {"success": False, "error": "; ".join(errors) or "all channels failed"}


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
    scheduled_at = state.get("buffer_scheduled_at")

    result = create_update(
        text=text[:2000],
        image_url=image_url,
        scheduled_at=scheduled_at,
    )
    if result.get("success"):
        ids = result.get("post_ids") or []
        partial = result.get("partial_errors")
        status = f"Queued to {len(ids)} channel(s)"
        if partial:
            status += f" (partial: {len(partial)} failed)"
        logger.info("Buffer: %s", status)
        return {"buffer_status": status, "buffer_post_ids": ids}
    err = result.get("error", "Unknown")
    logger.error("Buffer failed: %s", err)
    return {"buffer_status": f"Failed: {err[:180]}", "buffer_post_ids": []}
