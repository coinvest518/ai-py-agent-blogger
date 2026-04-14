"""Cloudflare Workers AI image generation (SDXL-Lightning).

Free tier: 10,000 neurons/day. SDXL-Lightning is fast (4 steps).
Endpoint: https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/bytedance/stable-diffusion-xl-lightning
"""

import logging
import os
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

CF_MODEL = "@cf/bytedance/stable-diffusion-xl-lightning"


def generate_image_cloudflare(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    num_steps: int = 8,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Generate image via Cloudflare Workers AI SDXL-Lightning."""
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")
    if not account_id or not api_token:
        return {"success": False, "error": "CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN not set"}

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{CF_MODEL}"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_steps": num_steps,
        "negative_prompt": "people, faces, humans, person, girl, boy, child, hands, body, portrait, selfie",
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code == 200:
            ctype = resp.headers.get("content-type", "")
            if "image" in ctype or len(resp.content) > 2000:
                logger.info("✅ Cloudflare image gen success (%d bytes)", len(resp.content))
                return {
                    "success": True,
                    "image_bytes": resp.content,
                    "provider": "Cloudflare Workers AI",
                    "model": CF_MODEL,
                }
            return {"success": False, "error": f"Unexpected response: {resp.text[:200]}"}
        return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        logger.warning("Cloudflare image gen failed: %s", e)
        return {"success": False, "error": str(e)}
