"""NVIDIA FLUX Image Generation Module.

Generates images via NVIDIA's public genai API using black-forest-labs FLUX.
Same NVIDIA_API_KEY as the text LLM. Free tier, fast (4-step schnell), high
quality (1024x1024 default).

Endpoint:
  https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-schnell
  https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev

Body:
  {"prompt": "...", "width": 1024, "height": 1024, "seed": 0, "steps": 4}

Response:
  {"artifacts": [{"base64": "..."}]}

Allowed dims: 768, 832, 896, 960, 1024, 1088, 1152, 1216, 1280, 1344.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

NVIDIA_IMAGE_MODELS = {
    "flux-schnell": "black-forest-labs/flux.1-schnell",
    "flux-dev": "black-forest-labs/flux.1-dev",
}

_ALLOWED_DIMS = (768, 832, 896, 960, 1024, 1088, 1152, 1216, 1280, 1344)


def _snap_dim(v: int) -> int:
    """Round to nearest FLUX-allowed dimension."""
    return min(_ALLOWED_DIMS, key=lambda d: abs(d - v))


def generate_image_nvidia(
    prompt: str,
    model: str = "flux-schnell",
    width: int = 1024,
    height: int = 1024,
    seed: int = 0,
    steps: Optional[int] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Generate an image via NVIDIA FLUX.

    Returns dict: {success, image_bytes, provider, model, error?}.
    """
    key = os.getenv("NVIDIA_API_KEY")
    if not key:
        return {"success": False, "error": "NVIDIA_API_KEY not set"}

    model_id = NVIDIA_IMAGE_MODELS.get(model, NVIDIA_IMAGE_MODELS["flux-schnell"])
    url = f"https://ai.api.nvidia.com/v1/genai/{model_id}"
    body: Dict[str, Any] = {
        "prompt": prompt[:1500],
        "width": _snap_dim(width),
        "height": _snap_dim(height),
        "seed": seed,
        "steps": steps if steps is not None else (4 if "schnell" in model_id else 28),
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    logger.info("🎨 NVIDIA FLUX generating: %s (%dx%d, %d steps)", model_id, body["width"], body["height"], body["steps"])
    try:
        r = requests.post(url, headers=headers, json=body, timeout=timeout)
    except Exception as e:
        return {"success": False, "error": f"request exception: {e}"}

    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}: {r.text[:240]}"}

    try:
        data = r.json()
    except Exception:
        return {"success": False, "error": f"non-JSON response: {r.text[:240]}"}

    artifacts = data.get("artifacts") or data.get("images") or []
    if not artifacts:
        return {"success": False, "error": f"no artifacts in response: {str(data)[:200]}"}

    first = artifacts[0]
    b64 = first.get("base64") if isinstance(first, dict) else first
    if not b64:
        return {"success": False, "error": "empty base64 in artifact"}
    try:
        image_bytes = base64.b64decode(b64)
    except Exception as e:
        return {"success": False, "error": f"base64 decode failed: {e}"}

    logger.info("✅ NVIDIA FLUX image generated: %d bytes", len(image_bytes))
    return {
        "success": True,
        "image_bytes": image_bytes,
        "provider": "NVIDIA FLUX",
        "model": model_id,
    }


def refine_prompt_with_mistral(raw_prompt: str, topic: str = "") -> Optional[str]:
    """Optional: use MISTRAL_IMAGE_API_KEY to sharpen the image prompt.

    Separate key from MISTRAL_API_KEY so image prompt rewriting doesn't eat into
    the text-LLM quota. Silently returns None if key missing or call fails.
    """
    key = os.getenv("MISTRAL_IMAGE_API_KEY") or os.getenv("MISTRAL_API_KEY")
    if not key or not raw_prompt:
        return None
    try:
        url = "https://api.mistral.ai/v1/chat/completions"
        system = (
            "Rewrite the user's idea as a single vivid text-to-image prompt for FLUX. "
            "Be concrete about subject, style, lighting, composition. No preamble, no quotes, "
            "under 80 words. No hashtags."
        )
        user = f"Topic: {topic}\nIdea: {raw_prompt}"
        body = {
            "model": os.getenv("LLM_MODEL_MISTRAL_IMAGE", "mistral-small-latest"),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.6,
            "max_tokens": 200,
        }
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        r = requests.post(url, headers=headers, json=body, timeout=30)
        if r.status_code != 200:
            logger.debug("Mistral image-prompt refine HTTP %d: %s", r.status_code, r.text[:160])
            return None
        data = r.json()
        text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
        return text or None
    except Exception as e:
        logger.debug("Mistral image-prompt refine failed: %s", e)
        return None
