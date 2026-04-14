"""Upload-Post.com subagent — Pinterest, X, Google Business, Threads bundled posting.

Upload-Post.com aggregates OAuth connections for platforms that don't have a
Composio connector in this project: Pinterest, Google Business Profile, Threads,
and X (image-only). One API call → all four platforms → counts as one quota unit.

Free-tier policy for this agent: **2 uploads per ISO calendar week**. Supervisor
reserves these for `promote_product=True` runs so routine content never drains them.

Env:
  UPLOADPOST_API_KEY (preferred) or UPLOAD_POST_API_KEY — bearer key
  UPLOAD_POST_WEEKLY_CAP (optional) — default 2. Falls back to legacy
    UPLOAD_POST_MONTHLY_CAP for one release for backwards compat.

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
    platforms: List[str],
    title: str = "",
    caption: str = "",
    video_url: Optional[str] = None,
    image_url: Optional[str] = None,
    video_path: Optional[str] = None,
    image_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Send a single multi-platform upload via upload-post.com.

    Args:
        platforms: list of platform slugs — e.g. ["pinterest", "x", "google_business"]
        title: short headline (Pinterest title, GBP headline)
        caption: body text / tweet text
        video_url / image_url: public URL to media (preferred over path)
        video_path / image_path: local file path (fallback)

    Respects monthly cap. Returns dict with success + response or error.
    """
    if not API_KEY:
        return {"success": False, "error": "UPLOADPOST_API_KEY not set"}
    if not platforms:
        return {"success": False, "error": "platforms list required"}

    logger.debug("Upload-Post payload: username=%s platforms=%s", UPLOAD_POST_PROFILE, platforms)
    remaining = remaining_quota()
    if remaining <= 0:
        return {
            "success": False,
            "error": f"Weekly cap {WEEKLY_CAP} reached for {_week_key()} — resets Monday 00:00 UTC",
            "remaining": 0,
        }

    # Route to the correct endpoint — upload-post.com has two:
    #   /api/upload         → video path (requires video file or video_url)
    #   /api/upload_photos  → image path (photos[] array, supports X, LinkedIn, etc.)
    is_photo_only = bool(image_url or image_path) and not (video_url or video_path)

    headers = {"Authorization": f"Apikey {API_KEY}"}
    files = {}

    if is_photo_only:
        endpoint = API_URL_PHOTOS
        data = {
            "title": title or caption[:90],
            "caption": caption,
            "description": caption,
            "platform[]": platforms,
        }
        if UPLOAD_POST_PROFILE:
            data["user"] = UPLOAD_POST_PROFILE.lstrip("@")
        if image_url:
            # API accepts either `photos[]` array (URLs) or multipart `photos[]` file(s)
            data["photos[]"] = image_url
        if image_path and os.path.exists(image_path):
            files["photos[]"] = open(image_path, "rb")
    else:
        endpoint = API_URL_VIDEO
        data = {
            "title": title,
            "caption": caption,
            "platform[]": platforms,
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
                    platforms, WEEKLY_CAP - (remaining - 1), WEEKLY_CAP, _week_key())
        return {
            "success": True,
            "response": body,
            "platforms": platforms,
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
    if not image_url and not video_url:
        return None
    strat = state.get("ai_strategy") or {}
    topic = (strat.get("topic") or "").strip() if isinstance(strat, dict) else ""
    title = (topic[:58] if topic else "FDWA Update")
    caption = state.get("tweet_text") or state.get("linkedin_text") or state.get("facebook_text") or ""
    if not caption:
        return None
    # Use /api/upload_photos for image-only (supports X, pinterest, GBP, threads).
    # Only /api/upload is video-only. Routing is handled inside upload().
    return {
        "platforms": ["pinterest", "x", "google_business", "threads"],
        "title": title,
        "caption": caption[:1500],
        "image_url": image_url,
        "video_url": video_url,
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
