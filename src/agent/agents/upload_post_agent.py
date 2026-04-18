"""Upload-Post.com subagent — multi-platform photo/video uploads.

This agent wraps Upload-Post.com's HTTP API (endpoints: `/api/upload` and
`/api/upload_photos`) to publish media and text across multiple platforms in a
single request. It is used for platforms without a dedicated Composio
connector (Pinterest, Threads, Google Business Profile, X image flows, etc.).

See the companion skill docs for full API reference and platform-specific
behaviour:

- skills/UPLOAD_PHOTOS.skill.md
- skills/UPLOAD_TEXT.skill.md

Free-tier policy for this agent: **2 uploads per ISO calendar week**. Supervisor
reserves these for `promote_product=True` runs so routine content never drains them.

Env:
    UPLOADPOST_API_KEY (preferred) or UPLOAD_POST_API_KEY — bearer key
    UPLOAD_POST_WEEKLY_CAP (optional) — default 2. Falls back to legacy
        UPLOAD_POST_MONTHLY_CAP for one release only.

Counter file: .upload_post_usage.json (gitignored). Week schema: `{"2026-W15": 2}`.
Old month keys like `"2026-04"` from previous versions are ignored (count as 0).
"""


from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
USAGE_FILE = REPO_ROOT / ".upload_post_usage.json"

API_BASE = "https://api.upload-post.com/api"
API_URL_VIDEO = f"{API_BASE}/upload"
API_URL_PHOTOS = f"{API_BASE}/upload_photos"
API_URL_TEXT = f"{API_BASE}/upload_text"
# Back-compat alias (external imports)
API_URL = API_URL_VIDEO
API_KEY = os.getenv("UPLOADPOST_API_KEY") or os.getenv("UPLOAD_POST_API_KEY")
UPLOAD_POST_PROFILE = (
    os.getenv("UPLOAD_POST_PROFILE")
    or os.getenv("UPLOADPOST_PROFILE")
    or os.getenv("UPLOAD_POST_USERNAME")
    or os.getenv("UPLOADPOST_USERNAME")
    or "Blogger"
)
WEEKLY_CAP = int(
    os.getenv("UPLOAD_POST_WEEKLY_CAP")
    or os.getenv("UPLOAD_POST_MONTHLY_CAP")  # legacy fallback, one release only
    or "2"
)


# -----------------------------------------------------------------------------
# Upload-Post discovery, capabilities and quota helpers
# -----------------------------------------------------------------------------
PLATFORM_CAPABILITIES = {
    "linkedin": {"accepts_images": True, "accepts_videos": False, "accepts_text": True},
    "x": {"accepts_images": True, "accepts_videos": True, "accepts_text": True},
    "facebook": {"accepts_images": True, "accepts_videos": True, "accepts_text": True},
    "pinterest": {"accepts_images": True, "accepts_videos": True, "accepts_text": False},
    "google_business": {"accepts_images": True, "accepts_videos": False, "accepts_text": True},
    "youtube": {"accepts_images": False, "accepts_videos": True, "accepts_text": False},
    "instagram": {"accepts_images": True, "accepts_videos": True, "accepts_text": False},
    "tiktok": {"accepts_images": True, "accepts_videos": True, "accepts_text": False},
    "threads": {"accepts_images": True, "accepts_videos": True, "accepts_text": True},
    "bluesky": {"accepts_images": True, "accepts_videos": True, "accepts_text": True},
    "reddit": {"accepts_images": True, "accepts_videos": False, "accepts_text": True},
}


def _call_uploadpost_get(path: str) -> dict:
    """Generic GET helper for Upload-Post API with multiple path fallbacks."""
    if not API_KEY:
        return {"success": False, "error": "UPLOADPOST_API_KEY not set"}
    headers = {"Authorization": f"Apikey {API_KEY}"}
    last_exc = None
    # Try a few common path forms
    candidates = [f"{API_BASE}{path}", f"{API_BASE}/{path.lstrip('/')}", f"{API_BASE}/v1{path}", f"{API_BASE}/v1/{path.lstrip('/')}" ]
    for url in candidates:
        try:
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                try:
                    return {"success": True, "data": r.json()}
                except Exception:
                    return {"success": True, "data": {"raw": r.text}}
            if r.status_code == 404:
                continue
            return {"success": False, "error": f"HTTP {r.status_code}: {r.text[:500]}"}
        except Exception as e:
            last_exc = e
            continue
    return {"success": False, "error": f"All attempts failed: {last_exc}"}


def list_connected_uploadpost_accounts() -> dict:
    """Attempt to discover which platforms/accounts an Upload-Post API key has connected.

    Returns a mapping: {"success": True, "platforms": {platform: [account_info, ...]}}
    or {"success": False, "error": msg}.
    """
    # Try a few likely endpoints that Upload-Post implementations expose
    endpoints = ["/accounts", "/profiles", "/profile", "/me", "/connected_accounts", "/users/me/accounts"]
    for ep in endpoints:
        resp = _call_uploadpost_get(ep)
        if not resp.get("success"):
            continue
        data = resp.get("data") or {}
        # Normalize arrays found under common keys
        arr = None
        for k in ("accounts", "profiles", "connected_accounts", "items", "data"):
            if isinstance(data, dict) and k in data and isinstance(data[k], list):
                arr = data[k]
                break
        if arr is None and isinstance(data, list):
            arr = data
        if not arr:
            # If we couldn't find a list, return raw data for inspection
            return {"success": True, "raw": data}

        mapping: Dict[str, List[dict]] = {}
        for item in arr:
            platform = None
            if isinstance(item, dict):
                for fk in ("platform", "service", "type", "provider", "slug"):
                    v = item.get(fk)
                    if isinstance(v, str) and v:
                        platform = v.lower()
                        break
                # Inspect alias/display fields for hints
                if not platform:
                    alias = (item.get("alias") or item.get("name") or item.get("display_name") or "")
                    if isinstance(alias, str):
                        for p in ("linkedin", "instagram", "facebook", "x", "twitter", "tiktok", "pinterest", "youtube", "threads", "bluesky", "reddit", "google_business"):
                            if p in alias.lower():
                                platform = p
                                break
            if not platform:
                platform = "unknown"
            mapping.setdefault(platform, []).append(item if isinstance(item, dict) else {"value": item})

        return {"success": True, "platforms": mapping}

    return {"success": False, "error": "Could not discover connected accounts via Upload-Post API"}


def _week_key_to_date(week_key: str):
    try:
        y, wk = week_key.split("-W")
        y = int(y)
        wk = int(wk)
        from datetime import datetime

        return datetime.fromisocalendar(y, wk, 1)
    except Exception:
        return None


def get_quota_summary() -> dict:
    """Return remaining weekly and monthly quota summary.

    Uses existing `.upload_post_usage.json` weekly counters to approximate
    monthly usage by summing weeks that fall within the same month.
    """
    monthly_cap = int(os.getenv("UPLOAD_POST_MONTHLY_CAP") or "10")
    used_week = _load_usage().get(_week_key(), 0)
    remaining_week = max(0, WEEKLY_CAP - used_week)

    # Approximate monthly usage by summing weeks that start in the current month
    from datetime import datetime

    now = datetime.utcnow()
    usage = _load_usage()
    used_month = 0
    for k, v in (usage or {}).items():
        d = _week_key_to_date(k)
        if d and d.month == now.month and d.year == now.year:
            used_month += int(v)
    remaining_month = max(0, monthly_cap - used_month)
    return {
        "weekly_cap": WEEKLY_CAP,
        "remaining_weekly": remaining_week,
        "monthly_cap": monthly_cap,
        "remaining_monthly": remaining_month,
    }


def _week_key() -> str:
    """ISO-week key like '2026-W15'. Rolls over Monday 00:00 UTC."""
    iso = datetime.now(timezone.utc).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _load_usage() -> Dict[str, int]:
    if not USAGE_FILE.exists():
        return {}
    try:
        return json.loads(USAGE_FILE.read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_usage(data: Dict[str, int]) -> None:
    try:
        USAGE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning("Could not persist upload-post usage: %s", e)


def remaining_quota() -> int:
    """Uploads left this ISO week."""
    used = _load_usage().get(_week_key(), 0)
    return max(0, WEEKLY_CAP - used)


def _bump_usage() -> None:
    data = _load_usage()
    key = _week_key()
    data[key] = int(data.get(key, 0)) + 1
    _save_usage(data)


def upload(
    platforms: Optional[List[str]] = None,
    title: str = "",
    caption: str = "",
    video_url: Optional[str] = None,
    image_url: Optional[str] = None,
    video_path: Optional[str] = None,
    image_path: Optional[str] = None,
    platform_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Send a single multi-platform upload via upload-post.com.

    If `platforms` is omitted, the function will attempt to discover connected
    accounts via the Upload-Post API and select compatible platforms based on
    media type and `PLATFORM_CAPABILITIES`.

    `platform_overrides` is a mapping like `{"linkedin": {"title": ..., "target_linkedin_page_id": ...}}`
    and will be flattened into form fields like `linkedin_title`.
    """
    if not API_KEY:
        return {"success": False, "error": "UPLOADPOST_API_KEY not set"}

    # Determine media type
    has_image = bool(image_url or image_path)
    has_video = bool(video_url or video_path)
    is_photo_only = has_image and not has_video
    is_video_only = has_video and not has_image
    is_text_only = not has_image and not has_video

    # Discover platforms when not explicitly provided
    if not platforms:
        disc = list_connected_uploadpost_accounts()
        if disc.get("success") and disc.get("platforms"):
            platforms = [p for p in disc.get("platforms", {}).keys() if p != "unknown"]
        else:
            platforms = []

    # Filter platforms by capability
    filtered: List[str] = []
    for p in (platforms or []):
        caps = PLATFORM_CAPABILITIES.get(p, {})
        if is_photo_only and not caps.get("accepts_images", False):
            continue
        if is_video_only and not caps.get("accepts_videos", False):
            continue
        # If text-only, prefer platforms that accept text
        if not is_photo_only and not is_video_only and caption:
            if not caps.get("accepts_text", False):
                continue
        filtered.append(p)

    if not filtered:
        return {"success": False, "error": "No compatible target platforms found", "available": platforms, "quota": get_quota_summary()}

    logger.debug("Upload-Post payload: username=%s platforms=%s", UPLOAD_POST_PROFILE, filtered)
    remaining = remaining_quota()
    if remaining <= 0:
        return {
            "success": False,
            "error": f"Weekly cap {WEEKLY_CAP} reached for {_week_key()} — resets Monday 00:00 UTC",
            "remaining": 0,
        }

    headers = {"Authorization": f"Apikey {API_KEY}"}
    files = {}

    # Build base data payload
    if is_text_only:
        endpoint = API_URL_TEXT
        data = {
            "title": title or caption[:90],
            "caption": caption,
            "platform[]": filtered,
        }
        if UPLOAD_POST_PROFILE:
            data["user"] = UPLOAD_POST_PROFILE.lstrip("@")
    elif is_photo_only:
        endpoint = API_URL_PHOTOS
        data = {
            "title": title or caption[:90],
            "caption": caption,
            "description": caption,
            "platform[]": filtered,
        }
        if UPLOAD_POST_PROFILE:
            data["user"] = UPLOAD_POST_PROFILE.lstrip("@")
        if image_url:
            data["photos[]"] = image_url
        if image_path and os.path.exists(image_path):
            files["photos[]"] = open(image_path, "rb")
    else:
        endpoint = API_URL_VIDEO
        data = {
            "title": title,
            "caption": caption,
            "platform[]": filtered,
        }
        if UPLOAD_POST_PROFILE:
            data["user"] = UPLOAD_POST_PROFILE.lstrip("@")
        if video_url:
            data["video_url"] = video_url
        if image_url:
            data["photo_url"] = image_url
        if video_path and os.path.exists(video_path):
            files["video"] = open(video_path, "rb")
        if image_path and os.path.exists(image_path):
            files["photo"] = open(image_path, "rb")

    # Apply platform-specific overrides (flatten into form fields)
    if platform_overrides and isinstance(platform_overrides, dict):
        for p, ov in platform_overrides.items():
            if not isinstance(ov, dict):
                continue
            for k, v in ov.items():
                try:
                    data[f"{p}_{k}"] = v
                except Exception:
                    pass

    try:
        resp = requests.post(endpoint, headers=headers, data=data, files=files or None, timeout=120)
    except Exception as e:
        return {"success": False, "error": f"Request exception: {e}"}
    finally:
        for f in files.values():
            try:
                f.close()
            except Exception:
                pass

    if resp.status_code in (200, 201):
        _bump_usage()
        body = {}
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:500]}
        logger.info("upload-post OK to %s — %d/%d used this week (%s)",
                    filtered, WEEKLY_CAP - (remaining - 1), WEEKLY_CAP, _week_key())
        return {
            "success": True,
            "response": body,
            "platforms": filtered,
            "remaining": remaining - 1,
        }

    return {
        "success": False,
        "error": f"HTTP {resp.status_code}: {resp.text[:300]}",
        "remaining": remaining,
    }


# =============================================================================
# Convenience wrappers per user's intended use
# =============================================================================

def pin_to_pinterest(title: str, caption: str, image_url: str) -> Dict[str, Any]:
    return upload(["pinterest"], title=title, caption=caption, image_url=image_url)


def tweet_video(caption: str, video_url: str) -> Dict[str, Any]:
    """Use upload-post for Twitter VIDEO only — text tweets go through composio/direct."""
    return upload(["x"], caption=caption, video_url=video_url)


def post_google_business(title: str, caption: str, image_url: Optional[str] = None) -> Dict[str, Any]:
    return upload(["google_business"], title=title, caption=caption, image_url=image_url)


# NOTE: promote_product gating removed — uploads are considered when media
# and caption are present. The weekly cap still applies.


def _derive_task(state: dict) -> Optional[Dict[str, Any]]:
    """Build an upload task from graph state when no explicit one is present.

    Bundles pinterest + x + google_business + threads into one API call — these
    are the platforms without a Composio connector, so upload-post is the only
    route. One bundled call = one weekly quota unit.
    """
    image_url = state.get("image_url")
    video_url = state.get("video_url")
    strat = state.get("ai_strategy") or {}
    topic = (strat.get("topic") or "").strip() if isinstance(strat, dict) else ""
    title = (topic[:58] if topic else "FDWA Update")
    caption = state.get("tweet_text") or state.get("linkedin_text") or state.get("facebook_text") or ""
    if not caption:
        return None

    if image_url:
        # Photo route — Upload-Post /api/upload_photos supported platforms.
        return {
            "platforms": ["linkedin", "facebook", "x", "instagram", "threads", "pinterest", "bluesky"],
            "title": title,
            "caption": caption[:1500],
            "image_url": image_url,
        }
    if video_url:
        return {
            "platforms": ["x", "pinterest", "threads", "instagram", "youtube"],
            "title": title,
            "caption": caption[:1500],
            "video_url": video_url,
        }
    # Text-only fallback via /api/upload_text
    return {
        "platforms": ["x", "threads", "linkedin", "bluesky"],
        "title": title,
        "caption": caption[:1500],
    }


def run(state: dict) -> dict:
    """Graph-compatible entry.

    Reads state['upload_post'] dict when caller supplies it; otherwise auto-derives
    a multi-platform task from available media + strategy. Gated on `promote_product`
    behavior removed — presence of media+caption determines posting. Weekly cap
    still enforced by `WEEKLY_CAP` and `remaining_quota()`.
    """
    # No promote_product gating; proceed when a task can be derived or provided.

    task = state.get("upload_post") or _derive_task(state)
    if not task:
        return {
            "upload_post_status": "Skipped: no media or caption",
            "upload_post_remaining": remaining_quota(),
        }

    result = upload(
        platforms=task.get("platforms", []),
        title=task.get("title", ""),
        caption=task.get("caption", ""),
        video_url=task.get("video_url"),
        image_url=task.get("image_url"),
        video_path=task.get("video_path"),
        image_path=task.get("image_path"),
    )
    if result.get("success"):
        return {
            "upload_post_status": f"Posted to {','.join(task.get('platforms', []))} "
                                  f"({result.get('remaining')} left this week)",
            "upload_post_remaining": result.get("remaining"),
        }
    return {
        "upload_post_status": f"Failed: {result.get('error', 'unknown')[:120]}",
        "upload_post_remaining": result.get("remaining", remaining_quota()),
    }
