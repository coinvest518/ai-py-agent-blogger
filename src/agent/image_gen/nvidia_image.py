"""NVIDIA NIM image generation (FLUX.1-schnell).

Uses NVIDIA Build's NIM hosted endpoints. Requires NVIDIA_API_KEY.
"""

import base64
import logging
import os
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)



def generate_image_nvidia(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 4,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Generate image via NVIDIA NIM image model."""
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        return {"success": False, "error": "NVIDIA_API_KEY not set"}

    base_url = os.getenv("NVIDIA_API_BASE", "https://ai.api.nvidia.com/v1/genai")
    image_model = os.getenv("NVIDIA_IMAGE_MODEL", "black-forest-labs/flux.1-schnell")
    url = f"{base_url.rstrip('/')}/{image_model}"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    payload = {
        "width": width,
        "height": height,
        "seed": 0,
        "steps": steps,
        "prompt": prompt,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code != 200:
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:300]}"}
        data = resp.json()
        artifacts = data.get("artifacts") or []
        if not artifacts:
            return {"success": False, "error": "No artifacts in NVIDIA response"}
        b64 = artifacts[0].get("base64") or artifacts[0].get("b64_json")
        if not b64:
            return {"success": False, "error": "No base64 image in NVIDIA artifact"}
        img_bytes = base64.b64decode(b64)
        logger.info("✅ NVIDIA image gen success (%d bytes)", len(img_bytes))
        return {
            "success": True,
            "image_bytes": img_bytes,
            "provider": "NVIDIA NIM",
            "model": image_model,
        }
    except Exception as e:
        logger.warning("NVIDIA image gen failed: %s", e)
        return {"success": False, "error": str(e)}
