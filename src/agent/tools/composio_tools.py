"""Composio client setup and platform posting tools.

Centralizes all Composio tool.execute() calls so agents never import Composio directly.
Uses `user_id=COMPOSIO_ENTITY_ID` — Composio auto-resolves the connected account by entity,
so per-platform account IDs are no longer required.
"""

import logging
import os
import json
from typing import Dict, List, Optional

from composio import Composio
from dotenv import load_dotenv

from src.agent.core.config import (
    COMPOSIO_API_KEY,
    COMPOSIO_ENTITY_ID,
    FACEBOOK_PAGE_ID,
    INSTAGRAM_USER_ID,
    LINKEDIN_AUTHOR_URN,
)

load_dotenv()
logger = logging.getLogger(__name__)

# Shared cached client
_client: Optional[Composio] = None

# Alias fallbacks for common slug differences across accounts/toolkits
SLUG_ALIASES: Dict[str, List[str]] = {
    "INSTAGRAM_GET_MEDIA_COMMENTS": ["INSTAGRAM_GET_POST_COMMENTS", "INSTAGRAM_GET_COMMENTS"],
    "INSTAGRAM_GET_MEDIA_INSIGHTS": ["INSTAGRAM_GET_POST_INSIGHTS", "INSTAGRAM_GET_INSIGHTS"],
    "FACEBOOK_GET_POSTS": ["FACEBOOK_GET_PAGE_POSTS", "FACEBOOK_LIST_PAGE_POSTS"],
    "FACEBOOK_GET_PAGE_INSIGHTS": ["FACEBOOK_PAGE_INSIGHTS"],
}

# Cache discovered tools list per entity to reduce list calls
_tools_cache: Dict[str, List[Dict]] = {}


def _env_toolkit_versions() -> Dict[str, str]:
    """Parse COMPOSIO_TOOLKIT_VERSION_* env vars into a toolkit version mapping."""
    versions: Dict[str, str] = {}
    prefix = "COMPOSIO_TOOLKIT_VERSION_"
    for key, value in os.environ.items():
        if key.startswith(prefix) and value:
            toolkit_slug = key[len(prefix):].replace("__", "/").lower()
            versions[toolkit_slug] = value.strip()
    return versions


def get_composio_client() -> Composio:
    """Get or create the shared Composio client.

    The Composio client is initialized with any configured
    `COMPOSIO_TOOLKIT_VERSION_*` env vars. If explicit toolkit versions are
    provided, they are passed to the SDK so manual tool execution can succeed.
    """
    global _client
    if _client is None:
        dangerously = os.getenv("COMPOSIO_DANGEROUSLY_SKIP_VERSION_CHECK", "true").lower() in ("1", "true", "yes")
        toolkit_versions = _env_toolkit_versions() or None
        try:
            if dangerously:
                # When skipping version check, don't pass toolkit_versions — the SDK
                # otherwise still enforces a version on any toolkit NOT in the map.
                logger.debug("Initializing Composio with dangerously_skip_version_check=True")
                _client = Composio(
                    api_key=COMPOSIO_API_KEY,
                    dangerously_skip_version_check=True,
                )
            else:
                _client = Composio(api_key=COMPOSIO_API_KEY, toolkit_versions=toolkit_versions)
        except TypeError:
            _client = Composio(api_key=COMPOSIO_API_KEY)
    return _client


def _entity() -> str | None:
    return COMPOSIO_ENTITY_ID


def _execute_with_fallback(slug: str, arguments: dict, user_id: str) -> dict:
    """Execute a Composio tool slug with graceful fallbacks.

    Attempts the requested slug, then tries configured alias slugs, and as a
    last resort lists available tools and attempts a best-effort match.
    Returns the raw Composio response dict.
    """
    client = get_composio_client()
    env_toolkit_versions = _env_toolkit_versions()
    skip_version = os.getenv("COMPOSIO_DANGEROUSLY_SKIP_VERSION_CHECK", "true").lower() in ("1", "true", "yes")
    def _execute(slug_to_execute: str, args: dict, version_override: str | None = None) -> dict:
        kwargs = {"arguments": args, "user_id": user_id}
        if version_override:
            kwargs["version"] = version_override
        elif skip_version:
            kwargs["dangerously_skip_version_check"] = True
        return client.tools.execute(slug_to_execute, **kwargs)

    try:
        resp = _execute(slug, arguments)
    except Exception as e:
        resp = {"successful": False, "error": str(e)}

    if resp.get("successful"):
        return resp

    # Inspect error and determine whether to attempt fallbacks
    err = resp.get("error", "")
    msg = json.dumps(err) if isinstance(err, (dict, list)) else str(err)
    msg_l = msg.lower()
    should_fallback = (
        "not found" in msg_l
        or "toolnotfound" in msg_l
        or "tool_not_found" in msg_l
        or "tool not found" in msg_l
        or "toolkit version not specified" in msg_l
    )

    # Try canonical alias list first
    if should_fallback:
        aliases = SLUG_ALIASES.get(slug, [])
        for a in aliases:
            try:
                resp2 = _execute(a, arguments)
                if resp2.get("successful"):
                    logger.info("Composio: fallback %s -> %s", slug, a)
                    return resp2
            except Exception as e2:
                logger.debug("Composio alias %s failed: %s", a, e2)
        # Try to resolve a toolkit version for this slug and execute with explicit
        # `toolkit_versions` if available. This fixes errors like
        # "Toolkit version not specified" by passing the exact version discovered
        # from the tools listing.
        try:
            tools = _tools_cache.get(user_id)
            if tools is None:
                tools = client.tools.get_raw_composio_tools()
                _tools_cache[user_id] = tools

            slug_parts = [p for p in slug.upper().split("_") if p]

            # Try direct tool lookup first, when slug is exact.
            try:
                direct_tool = client.tools.get_raw_composio_tool_by_slug(slug)
                tkit = getattr(direct_tool, "toolkit", None)
                toolkit_slug = None
                toolkit_version = None
                if isinstance(tkit, dict):
                    toolkit_slug = tkit.get("slug") or tkit.get("name")
                else:
                    toolkit_slug = getattr(tkit, "slug", None) or (str(tkit) if tkit else None)
                toolkit_version = (
                    getattr(direct_tool, "version", None)
                    or getattr(direct_tool, "toolkit_version", None)
                    or (direct_tool.get("version") if isinstance(direct_tool, dict) else None)
                    or (direct_tool.get("toolkit_version") if isinstance(direct_tool, dict) else None)
                )
                if toolkit_slug and toolkit_version:
                    try:
                        resp_tool = _execute(slug, arguments, toolkit_version)
                        if resp_tool.get("successful"):
                            logger.info("Composio: execute with direct version %s -> success", toolkit_version)
                            return resp_tool
                    except Exception:
                        pass
            except Exception:
                pass

            # First, try to find the same tool and its toolkit/version
            for t in tools or []:
                # support dict-like and object-like tool records
                tslug = (t.get("slug") if isinstance(t, dict) else getattr(t, "slug", None)) or ""
                tslug_u = tslug.upper()
                if tslug_u == slug.upper() or all(part in tslug_u for part in slug_parts):
                    # try to extract toolkit slug & version
                    tkit = (t.get("toolkit") if isinstance(t, dict) else getattr(t, "toolkit", None))
                    toolkit_slug = None
                    toolkit_version = None
                    if isinstance(tkit, dict):
                        toolkit_slug = tkit.get("slug") or tkit.get("name")
                    else:
                        toolkit_slug = getattr(tkit, "slug", None) or (str(tkit) if tkit else None)
                    if isinstance(t, dict):
                        toolkit_version = t.get("version") or t.get("toolkit_version")
                    else:
                        toolkit_version = getattr(t, "version", None) or getattr(t, "toolkit_version", None)

                    if toolkit_slug and toolkit_version:
                        try:
                            resp_tool = _execute(slug, arguments, toolkit_version)
                            if resp_tool.get("successful"):
                                logger.info("Composio: execute with version %s -> success", toolkit_version)
                                return resp_tool
                        except Exception:
                            pass

            # Last resort: attempt best-effort match by slug text and try executing
            for t in tools or []:
                tslug = (t.get("slug") if isinstance(t, dict) else getattr(t, "slug", None)) or ""
                tslug_u = tslug.upper()
                if all(part in tslug_u for part in slug_parts):
                    try:
                        resp3 = _execute(tslug, arguments)
                        if resp3.get("successful"):
                            logger.info("Composio: autodiscovered fallback %s -> %s", slug, tslug)
                            return resp3
                    except Exception:
                        pass
        except Exception as e3:
            logger.debug("Composio tools listing/resolve failed: %s", e3)

    # Return original response if no fallback succeeded
    # Final attempt: try passing a full mapping of discovered toolkit versions
    try:
        kits = client.toolkits.list()
        items = getattr(kits, "items", None) or kits
        toolkit_versions = {}
        for kt in (items or []):
            kslug = (kt.get("slug") if isinstance(kt, dict) else getattr(kt, "slug", None)) or None
            # try multiple possible version keys
            kver = None
            if isinstance(kt, dict):
                kver = kt.get("version") or kt.get("latest") or kt.get("latest_version") or kt.get("current_version")
            else:
                kver = getattr(kt, "version", None) or getattr(kt, "latest_version", None) or getattr(kt, "current_version", None)
            if kslug and kver:
                toolkit_versions[kslug] = kver
        if toolkit_versions:
            try:
                resp_full = _execute(slug, arguments, toolkit_versions)
                if resp_full.get("successful"):
                    logger.info("Composio: execute with discovered toolkit_versions mapping succeeded")
                    return resp_full
            except Exception:
                pass
    except Exception as _e:
        logger.debug("Composio full toolkit_versions attempt failed: %s", _e)

    return resp


def _safe_get(obj: object, *fields: str) -> Optional[str]:
    for field in fields:
        if isinstance(obj, dict):
            value = obj.get(field)
        else:
            value = getattr(obj, field, None)
        if value:
            return str(value)
    return None


def _looks_like_linkedin_account(item: object) -> bool:
    alias = _safe_get(item, "alias") or ""
    word_id = _safe_get(item, "word_id") or ""
    toolkit = _safe_get(item, "toolkit")
    toolkit_slug = _safe_get(toolkit, "slug") or ""
    toolkit_name = _safe_get(toolkit, "name") or ""
    return any("linkedin" in field.lower() for field in (alias, word_id, toolkit_slug, toolkit_name))


def _looks_like_linkedin_urn(value: str) -> bool:
    return isinstance(value, str) and value.startswith("urn:li:")


def _find_linkedin_author_urn_from_connected_accounts(user_id: str) -> Optional[str]:
    try:
        client = get_composio_client()
        resp = client.connected_accounts.list(user_ids=[user_id], statuses=["ACTIVE"])
        items = getattr(resp, "items", None) or []
        for item in items:
            if not _looks_like_linkedin_account(item):
                continue
            alias = _safe_get(item, "alias")
            if alias and _looks_like_linkedin_urn(alias):
                return alias
            word_id = _safe_get(item, "word_id")
            if word_id and _looks_like_linkedin_urn(word_id):
                return word_id
            state = _safe_get(item, "state")
            account_url = _safe_get(state, "account_url")
            if account_url and "linkedin" in account_url.lower() and _looks_like_linkedin_urn(account_url):
                return account_url
            account_id = _safe_get(state, "account_id")
            if account_id and _looks_like_linkedin_urn(account_id):
                return account_id
    except Exception as e:
        logger.debug("Failed to discover LinkedIn author URN from Composio connected accounts: %s", e)
    return None


def _find_linkedin_author_urn_from_linkedin_tool(user_id: str) -> Optional[str]:
    try:
        client = get_composio_client()
        resp = client.tools.execute(
            "LINKEDIN_GET_MY_INFO",
            arguments={},
            user_id=user_id,
            version="20260413_00",
        )
        if resp.get("successful"):
            data = resp.get("data") or {}
            for field in ("urn", "id", "personUrn", "memberUrn", "profileUrn"):  # heuristic
                value = data.get(field)
                if value and _looks_like_linkedin_urn(value):
                    return value
            # If the tool returns raw person id, build the URN
            person_id = data.get("id")
            if person_id and isinstance(person_id, str) and person_id.isalnum():
                return f"urn:li:person:{person_id}"
    except Exception as e:
        logger.debug("Failed to resolve LinkedIn author URN from LINKEDIN_GET_MY_INFO: %s", e)
    return None


def get_linkedin_author_urn(author_urn: str | None = None) -> Optional[str]:
    urn = author_urn or LINKEDIN_AUTHOR_URN
    if urn:
        return urn
    entity = _entity()
    if entity:
        found = _find_linkedin_author_urn_from_connected_accounts(entity)
        if found:
            return found
        return _find_linkedin_author_urn_from_linkedin_tool(entity)
    return None


# =============================================================================
# Twitter — posting now routes through upload_post_agent (image-only, 10/mo cap)
# =============================================================================


# =============================================================================
# Facebook
# =============================================================================

def _normalize_facebook_page_id(page_id: str | None) -> str:
    """Normalize Facebook page ID or URL to the canonical page identifier."""
    if not page_id:
        return ""
    page_id = str(page_id).strip()
    if not page_id:
        return ""

    if page_id.lower().startswith("http"):
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(page_id)
        query = parse_qs(parsed.query)
        if "page_id" in query and query["page_id"]:
            return query["page_id"][0].strip()
        page_id = parsed.path.strip("/")

    if "facebook.com" in page_id.lower():
        page_id = page_id.lower().split("facebook.com")[-1].strip("/")

    if page_id.startswith("pg/"):
        page_id = page_id[len("pg/"):]
    if "/" in page_id:
        page_id = page_id.split("/")[-1]

    return page_id.strip()


def _extract_facebook_post_id(response: dict) -> str:
    """Robustly extract a Facebook post ID from Composio response data."""
    if not isinstance(response, dict):
        return ""
    data = response.get("data", {}) or {}
    response_data = data.get("response_data", {}) or {}
    post_id = (
        response_data.get("post_id")
        or response_data.get("id")
        or data.get("post_id")
        or data.get("id")
    )
    if isinstance(post_id, str):
        return post_id.strip()
    if post_id is not None:
        return str(post_id).strip()
    return ""


def post_facebook(page_id: str | None, text: str, photo_path: str | None = None) -> dict:
    """Post to Facebook page. Returns dict with success, post_id, or error."""
    page_id = _normalize_facebook_page_id(page_id or FACEBOOK_PAGE_ID)
    entity = _entity()
    if not page_id:
        return {"error": "FACEBOOK_PAGE_ID not set"}
    if not entity:
        return {"success": False, "error": "COMPOSIO_ENTITY_ID not set"}

    client = get_composio_client()
    params = {"page_id": page_id, "message": text, "published": True}

    tool_name = "FACEBOOK_CREATE_POST"
    if photo_path and os.path.exists(photo_path):
        params["photo"] = photo_path
        tool_name = "FACEBOOK_CREATE_PHOTO_POST"

    try:
        resp = _execute_with_fallback(tool_name, params, entity)
        if not resp.get("successful"):
            return {"success": False, "error": resp.get("error", "Unknown")}
        post_id = _extract_facebook_post_id(resp)
        return {"success": True, "post_id": post_id}
    except Exception as e:
        logger.exception("Facebook post failed: %s", e)
        return {"success": False, "error": str(e)}


def comment_facebook(post_id: str, message: str) -> dict:
    """Comment on a Facebook post."""
    if not post_id:
        return {"success": False, "error": "No post ID"}
    entity = _entity()
    if not entity:
        return {"success": False, "error": "COMPOSIO_ENTITY_ID not set"}
    client = get_composio_client()
    try:
        resp = _execute_with_fallback(
            "FACEBOOK_CREATE_COMMENT", {"message": message, "object_id": post_id}, entity
        )
        cid = resp.get("data", {}).get("id", "commented")
        return {"success": True, "comment_id": cid}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# LinkedIn
# =============================================================================

def post_linkedin(author_urn: str | None, text: str) -> dict:
    """Post to LinkedIn. Returns dict with success or error."""
    urn = get_linkedin_author_urn(author_urn)
    entity = _entity()
    if not urn:
        return {"success": False, "error": "LINKEDIN_AUTHOR_URN not set or discoverable from Composio"}
    if not entity:
        return {"success": False, "error": "COMPOSIO_ENTITY_ID not set"}
    client = get_composio_client()
    try:
        resp = _execute_with_fallback(
            "LINKEDIN_CREATE_LINKED_IN_POST",
            {
                "author": urn,
                "commentary": text,
                "lifecycleState": "PUBLISHED",
                "visibility": "PUBLIC",
            },
            entity,
        )
        if resp.get("successful"):
            return {"success": True}
        return {"success": False, "error": resp.get("error", "Unknown")}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Instagram
# =============================================================================

def _ensure_publishable_image_url(image_url: str) -> tuple[str, str]:
    """Re-host image on a fresh CDN URL so Meta doesn't reject stale/blocked URLs.

    Returns (new_url, source) where source is "reuploaded" if we downloaded
    and re-uploaded, or "as-is" if the original URL was kept.
    """
    if not image_url:
        return "", "missing"
    # Local-file URLs can never be passed to Meta — always re-upload
    is_local = image_url.startswith("file://") or image_url.startswith("file:///")
    if not is_local:
        # For remote URLs, still re-upload: Meta aggressively rejects repeat URLs.
        pass
    try:
        from src.agent.tools.image_tools import download_image, upload_image
        local = download_image(image_url)
        if not local:
            return image_url, "as-is"  # couldn't download — let Meta try anyway
        import pathlib
        data = pathlib.Path(local).read_bytes()
        up = upload_image(data)
        if up.get("success") and up.get("url"):
            return up["url"], "reuploaded"
    except Exception as e:
        logger.warning("IG image re-host failed: %s", e)
    return image_url, "as-is"


def post_instagram(caption: str, image_url: str) -> dict:
    """Post to Instagram (image required). Returns dict with instagram_status.

    Before handing the URL to Meta, we download the bytes and re-upload to a
    fresh CDN URL — Meta aggressively rejects stale/re-used third-party CDN
    links (error 9004 / 2207052). A fresh URL avoids those rejections.
    """
    entity = _entity()
    if not INSTAGRAM_USER_ID:
        return {"error": "INSTAGRAM_USER_ID not set"}
    if not entity:
        return {"error": "COMPOSIO_ENTITY_ID not set"}
    if not image_url:
        return {"error": "Image required for Instagram"}

    publishable_url, source = _ensure_publishable_image_url(image_url)
    if not publishable_url:
        return {"error": "Could not produce a publishable image URL"}
    logger.info("IG image URL (%s): %s", source, publishable_url)

    client = get_composio_client()
    try:
        container = _execute_with_fallback(
            "INSTAGRAM_CREATE_MEDIA_CONTAINER",
            {
                "ig_user_id": INSTAGRAM_USER_ID,
                "image_url": publishable_url,
                "caption": caption,
                "content_type": "photo",
            },
            entity,
        )
        if not container.get("successful"):
            return {"error": container.get("error", "Container failed")}
        container_id = container.get("data", {}).get("id", "")
        import time
        time.sleep(10)
        pub = _execute_with_fallback(
            "INSTAGRAM_CREATE_POST",
            {"ig_user_id": INSTAGRAM_USER_ID, "creation_id": container_id},
            entity,
        )
        if pub.get("successful"):
            post_id = pub.get("data", {}).get("id", "")
            return {"instagram_status": "Posted", "instagram_post_id": post_id}
        return {"error": pub.get("error", "Publish failed")}
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# Telegram (text only — NO images for Telegram)
# =============================================================================

def send_telegram_text(message: str) -> dict:
    """Send text-only message to Telegram group (no images)."""
    from src.agent import telegram_agent
    chat_id = telegram_agent.TELEGRAM_GROUP_USERNAME or telegram_agent.TELEGRAM_GROUP_CHAT_ID
    if not chat_id:
        return {"error": "No Telegram group configured"}
    try:
        result = telegram_agent.send_message(chat_id=chat_id, text=message)
        if result.get("success"):
            msg_id = result.get("data", {}).get("result", {}).get("message_id", "N/A")
            return {"telegram_status": f"Posted: message_id={msg_id}"}
        return {"error": result.get("error", "Unknown")}
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# READ layer — engagement / analytics pulls (Phase 16)
# =============================================================================

def _exec_read(slug: str, args: dict) -> dict:
    """Internal helper: run a Composio READ tool, return `data` dict or {}."""
    entity = _entity()
    if not entity:
        return {"_error": "COMPOSIO_ENTITY_ID not set"}
    try:
        resp = _execute_with_fallback(slug, args, entity)
        if not resp.get("successful"):
            return {"_error": resp.get("error", "Unknown"), "_slug": slug}
        return resp.get("data", {}) or {}
    except Exception as e:
        logger.warning("READ %s failed: %s", slug, e)
        return {"_error": str(e), "_slug": slug}


def fetch_facebook_page_insights(page_id: str | None = None, metric: str = "page_impressions") -> dict:
    """Pull Facebook Page insights (impressions, reach, engaged users)."""
    page_id = page_id or FACEBOOK_PAGE_ID
    if not page_id:
        return {"_error": "FACEBOOK_PAGE_ID not set"}
    return _exec_read(
        "FACEBOOK_GET_PAGE_INSIGHTS",
        {"page_id": page_id, "metric": metric, "period": "day"},
    )


def fetch_facebook_recent_posts(page_id: str | None = None, limit: int = 5) -> dict:
    """Fetch recent posts on the page with engagement counts."""
    page_id = page_id or FACEBOOK_PAGE_ID
    if not page_id:
        return {"_error": "FACEBOOK_PAGE_ID not set"}
    return _exec_read(
        "FACEBOOK_GET_PAGE_POSTS",
        {"page_id": page_id, "limit": limit},
    )


def fetch_linkedin_post_stats(share_urn: str) -> dict:
    """Pull LinkedIn share analytics (impressions, clicks, engagement)."""
    if not share_urn:
        return {"_error": "No share_urn"}
    return _exec_read(
        "LINKEDIN_GET_ANALYTICS_FOR_SHARE",
        {"share_urn": share_urn},
    )


def fetch_instagram_media_insights(media_id: str) -> dict:
    """Pull Instagram media insights (reach, impressions, likes, comments, saves)."""
    if not media_id:
        return {"_error": "No media_id"}
    return _exec_read(
        "INSTAGRAM_GET_MEDIA_INSIGHTS",
        {"media_id": media_id, "metric": "reach,impressions,likes,comments,saved"},
    )


def fetch_instagram_media_comments(media_id: str) -> dict:
    """Pull recent comments on an Instagram media."""
    if not media_id:
        return {"_error": "No media_id"}
    return _exec_read(
        "INSTAGRAM_GET_MEDIA_COMMENTS",
        {"media_id": media_id},
    )


def fetch_telegram_recent_updates(limit: int = 20) -> dict:
    """Poll recent Telegram updates (channel/group activity)."""
    from src.agent import telegram_agent
    try:
        data = telegram_agent.get_updates(limit=limit) if hasattr(telegram_agent, "get_updates") else None
        if data is None:
            return {"_error": "telegram_agent.get_updates not available"}
        return {"updates": data}
    except Exception as e:
        return {"_error": str(e)}


def send_telegram_alert(message: str) -> dict:
    """Send alert text to a dedicated Telegram failure chat if configured.

    Falls back to the primary group when no failure-specific target is configured.
    """
    from src.agent import telegram_agent

    failure_chat = os.getenv("TELEGRAM_FAILURE_GROUP_USERNAME") or os.getenv("TELEGRAM_FAILURE_GROUP_CHAT_ID")
    target = failure_chat or (telegram_agent.TELEGRAM_GROUP_USERNAME or telegram_agent.TELEGRAM_GROUP_CHAT_ID)
    if not target:
        return {"error": "No Telegram group configured for alerts"}
    try:
        result = telegram_agent.send_message(chat_id=target, text=message)
        if result.get("success"):
            msg_id = result.get("data", {}).get("result", {}).get("message_id", "N/A")
            return {"telegram_status": f"Posted: message_id={msg_id}"}
        return {"error": result.get("error", "Unknown")}
    except Exception as e:
        return {"error": str(e)}
