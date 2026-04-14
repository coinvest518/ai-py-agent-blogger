"""Video generation cascade — HF CogVideoX → graceful skip.

Currently only HuggingFace CogVideoX is wired. Future providers (Replicate,
Runway, etc.) can be appended to PROVIDERS without touching call sites.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List

from . import huggingface_video

logger = logging.getLogger(__name__)


def _hf_provider(prompt: str, **_: Any) -> Dict[str, Any]:
    data = huggingface_video.generate_video(prompt)
    if not data:
        return {"success": False, "error": "HF CogVideoX returned nothing"}
    path = huggingface_video.save_video_locally(data)
    return {"success": True, "provider": "huggingface_cogvideox", "video_bytes": data, "path": path}


PROVIDERS: List[Callable[..., Dict[str, Any]]] = [_hf_provider]


def generate_with_cascade(prompt: str, **kwargs: Any) -> Dict[str, Any]:
    """Try each provider in order. Returns the first success or {success: False}."""
    last_err = ""
    for provider in PROVIDERS:
        try:
            result = provider(prompt, **kwargs)
        except Exception as e:
            logger.warning("Video provider %s crashed: %s", provider.__name__, e)
            last_err = str(e)
            continue
        if result.get("success"):
            return result
        last_err = result.get("error", "unknown")
        logger.info("Video provider %s skipped: %s", provider.__name__, last_err)
    return {"success": False, "error": last_err or "no providers configured"}
