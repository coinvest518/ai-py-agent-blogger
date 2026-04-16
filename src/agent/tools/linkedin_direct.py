"""Direct LinkedIn API helpers for profile discovery and simple posts.

This module provides minimal, explicit helpers so the agent can fall back
to the LinkedIn REST API when Composio is rate-limited. It performs safe
operations (profile discovery) and implements text/image posting helpers
that should only be called with explicit user confirmation.

Note: Caller must provide a valid member access token with `w_member_social`.
"""
from __future__ import annotations

import json
import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def _headers(token: str, content_type: str = "application/json") -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": content_type,
    }


def get_linkedin_profile(access_token: str) -> Dict[str, Any]:
    """Fetch the calling member's profile via `GET /v2/me`.

    Returns a dict with `success` and either `data` (JSON) and
    `person_urn` when available, or `error`/`status_code` on failure.
    """
    url = "https://api.linkedin.com/v2/me"
    try:
        resp = requests.get(url, headers=_headers(access_token))
        if resp.status_code == 200:
            data = resp.json()
            pid = data.get("id")
            urn = f"urn:li:person:{pid}" if pid else None
            return {"success": True, "data": data, "person_urn": urn}
        return {"success": False, "status_code": resp.status_code, "error": resp.text}
    except Exception as e:
        logger.debug("LinkedIn profile fetch failed: %s", e)
        return {"success": False, "error": str(e)}


def post_ugc_text(author_urn: str, text: str, access_token: str, visibility: str = "PUBLIC") -> Dict[str, Any]:
    """Create a text-only UGC post on behalf of `author_urn`.

    WARNING: This performs a live post. Only call after explicit user consent.
    """
    url = "https://api.linkedin.com/v2/ugcPosts"
    payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
    }
    try:
        resp = requests.post(url, headers=_headers(access_token), json=payload)
        if resp.status_code in (200, 201):
            try:
                body = resp.json() if resp.content else {}
            except Exception:
                body = {"raw": resp.text}
            return {"success": True, "data": body}
        try:
            err = resp.json()
        except Exception:
            err = resp.text
        return {"success": False, "status_code": resp.status_code, "error": err}
    except Exception as e:
        logger.debug("LinkedIn UGC post failed: %s", e)
        return {"success": False, "error": str(e)}


def register_image_upload(owner_urn: str, access_token: str) -> Dict[str, Any]:
    """Register an image upload. Returns the register response (value includes uploadUrl and asset).

    See LinkedIn docs: POST /v2/assets?action=registerUpload
    """
    url = "https://api.linkedin.com/v2/assets?action=registerUpload"
    body = {
        "registerUploadRequest": {
            "owner": owner_urn,
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "serviceRelationships": [
                {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
            ],
        }
    }
    try:
        resp = requests.post(url, headers=_headers(access_token), json=body)
        if resp.status_code in (200, 201):
            return {"success": True, "data": resp.json()}
        return {"success": False, "status_code": resp.status_code, "error": resp.text}
    except Exception as e:
        logger.debug("LinkedIn register upload failed: %s", e)
        return {"success": False, "error": str(e)}


def upload_binary_to_url(upload_url: str, data: bytes, content_type: str = "image/jpeg") -> Dict[str, Any]:
    """Upload binary bytes to the provided upload URL (PUT).

    Returns success True/False and any response details.
    """
    try:
        headers = {"Content-Type": content_type}
        resp = requests.put(upload_url, data=data, headers=headers)
        if resp.status_code in (200, 201):
            return {"success": True}
        return {"success": False, "status_code": resp.status_code, "error": resp.text}
    except Exception as e:
        logger.debug("Upload to LinkedIn upload URL failed: %s", e)
        return {"success": False, "error": str(e)}


def post_ugc_with_image(author_urn: str, text: str, image_bytes: bytes, access_token: str, visibility: str = "PUBLIC") -> Dict[str, Any]:
    """Register, upload image, and create a UGC post referencing the uploaded asset.

    WARNING: Live posting. Use only with explicit user confirmation.
    """
    reg = register_image_upload(author_urn, access_token)
    if not reg.get("success"):
        return reg
    data = reg.get("data") or {}

    # Parse typical registerUpload response to find upload URL and asset URN.
    upload_url = None
    asset_urn = None
    try:
        # Common payload shapes vary; defensively search
        val = data.get("value") if isinstance(data, dict) else None
        if isinstance(val, dict):
            asset_urn = val.get("asset") or val.get("assetUrn")
            mech = val.get("uploadMechanism") or {}
            for v in mech.values():
                if isinstance(v, dict):
                    upload_url = v.get("uploadUrl") or v.get("upload_uri")
                    if upload_url:
                        break
        # fallback: top-level keys
        if not upload_url and isinstance(data, dict):
            try:
                upload_url = data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
            except Exception:
                pass
        if not asset_urn:
            asset_urn = data.get("asset") or data.get("assetUrn")
    except Exception as e:
        logger.debug("Failed parsing registerUpload response: %s", e)
        return {"success": False, "error": "registerUpload parse failed", "data": data}

    if not upload_url or not asset_urn:
        return {"success": False, "error": "uploadUrl or asset URN missing", "data": data}

    up = upload_binary_to_url(upload_url, image_bytes)
    if not up.get("success"):
        return up

    payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "IMAGE",
                "media": [
                    {"status": "READY", "description": {"text": ""}, "media": asset_urn, "title": {"text": ""}}
                ],
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
    }
    try:
        url = "https://api.linkedin.com/v2/ugcPosts"
        resp = requests.post(url, headers=_headers(access_token), json=payload)
        if resp.status_code in (200, 201):
            try:
                body = resp.json() if resp.content else {}
            except Exception:
                body = {"raw": resp.text}
            return {"success": True, "data": body}
        try:
            err = resp.json()
        except Exception:
            err = resp.text
        return {"success": False, "status_code": resp.status_code, "error": err}
    except Exception as e:
        logger.debug("LinkedIn UGC post with image failed: %s", e)
        return {"success": False, "error": str(e)}
