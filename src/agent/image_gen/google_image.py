"""Google AI image generation via Gemini API.

Uses gemini-2.5-flash-image (Imagen-style) via Google AI Studio.
Requires GOOGLE_AI_API_KEY.
"""

import base64
import logging
import os
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

GOOGLE_MODEL = "gemini-2.5-flash-image"


def generate_image_google(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Generate image via Google Gemini image model."""
    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        return {"success": False, "error": "GOOGLE_AI_API_KEY not set"}

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GOOGLE_MODEL}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }

    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        if resp.status_code != 200:
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:300]}"}
        data = resp.json()
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    img_bytes = base64.b64decode(inline["data"])
                    logger.info("✅ Google image gen success (%d bytes)", len(img_bytes))
                    return {
                        "success": True,
                        "image_bytes": img_bytes,
                        "provider": "Google Gemini Image",
                        "model": GOOGLE_MODEL,
                    }
        return {"success": False, "error": "No image data in response"}
    except Exception as e:
        logger.warning("Google image gen failed: %s", e)
        return {"success": False, "error": str(e)}
