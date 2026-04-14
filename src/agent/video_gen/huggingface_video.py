"""HuggingFace CogVideoX text-to-video via the Inference API.

Model: `THUDM/CogVideoX-5b`. Requires `HF_TOKEN` env var.
Returns raw MP4 bytes (or None on failure).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

HF_VIDEO_MODEL = os.getenv("HF_VIDEO_MODEL", "THUDM/CogVideoX-5b")
HF_VIDEO_URL = f"https://router.huggingface.co/hf-inference/models/{HF_VIDEO_MODEL}"


def generate_video(prompt: str, timeout: int = 300) -> Optional[bytes]:
    """Generate an MP4 from a text prompt. Returns bytes or None."""
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
    if not token:
        logger.info("HF_TOKEN not set — skipping CogVideoX")
        return None

    headers = {"Authorization": f"Bearer {token}", "Accept": "video/mp4"}
    try:
        resp = requests.post(
            HF_VIDEO_URL,
            headers=headers,
            json={"inputs": prompt},
            timeout=timeout,
        )
    except Exception as e:
        logger.warning("HF CogVideoX request exception: %s", e)
        return None

    if resp.status_code != 200:
        logger.warning("HF CogVideoX HTTP %d: %s", resp.status_code, resp.text[:200])
        return None

    ct = resp.headers.get("Content-Type", "")
    if "video" not in ct and not resp.content.startswith(b"\x00\x00\x00"):
        # Might be JSON error or queue-status body
        logger.warning("HF CogVideoX non-video response (%s): %s", ct, resp.text[:200])
        return None
    return resp.content


def save_video_locally(data: bytes, filename: str | None = None) -> str:
    """Persist bytes to temp_images/ and return the absolute path."""
    tmp = Path("temp_images")
    tmp.mkdir(exist_ok=True)
    from datetime import datetime
    name = filename or f"cogvideox_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.mp4"
    path = tmp / name
    path.write_bytes(data)
    return str(path.resolve())
