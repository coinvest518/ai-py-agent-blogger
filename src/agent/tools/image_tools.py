"""Image generation tools — Pollinations (primary) → HuggingFace → Freepik fallback.

Provides image generation and upload. Used by the image generation node.
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path

import requests

from src.agent.core.config import TEMP_IMAGES_DIR

logger = logging.getLogger(__name__)


def generate_image(prompt: str, width: int = 1024, height: int = 1024, timeout: int = 90) -> dict:
    """Generate image with automatic provider fallback.

    Returns dict with 'success', 'image_bytes', 'provider', or 'error'.
    """
    try:
        from src.agent.pollinations_image_gen import generate_image_with_fallback
        return generate_image_with_fallback(prompt=prompt, model="flux", width=width, height=height, timeout=timeout)
    except Exception as e:
        logger.warning("Image generation failed: %s", e)
        return {"success": False, "error": str(e)}


def upload_image(image_bytes: bytes) -> dict:
    """Upload image bytes to imgbb for public HTTP URL.

    Returns dict with 'success', 'url', or 'error'.
    """
    try:
        from src.agent.pollinations_image_gen import upload_to_imgbb
        return upload_to_imgbb(image_bytes)
    except Exception as e:
        return {"success": False, "error": str(e)}


def save_image_locally(image_bytes: bytes, provider: str = "pollinations") -> str:
    """Save image bytes to local file. Returns local path."""
    TEMP_IMAGES_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{provider}_{timestamp}.png"
    path = TEMP_IMAGES_DIR / filename
    path.write_bytes(image_bytes)
    logger.info("Image saved: %s", path)
    return str(path)


def download_image(url: str) -> str | None:
    """Download image from URL and save locally. Returns local path or None."""
    try:
        if url.startswith("file:///"):
            local_path = url.replace("file:///", "").replace("/", chr(92))
            return local_path if os.path.exists(local_path) else None
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        TEMP_IMAGES_DIR.mkdir(exist_ok=True)
        fname = url.split("/")[-1] or "image.jpg"
        if not fname.endswith((".jpg", ".jpeg", ".png")):
            fname += ".jpg"
        path = TEMP_IMAGES_DIR / fname
        path.write_bytes(resp.content)
        return str(path)
    except Exception as e:
        logger.warning("Image download failed: %s", e)
        return None


def enhance_prompt(text: str, topic: str = "business") -> str:
    """Convert social-media text to a visual prompt for image generation.

    Returns a clean prompt ≤ 400 chars optimised for FLUX-style models.
    """
    clean = re.sub(r"#\w+", "", text)
    clean = re.sub(r"@\w+", "", clean)
    clean = re.sub(r"https?://\S+", "", clean)
    clean = re.sub(r"[*#@\[\]{}()\'\"\\]", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip()[:120]

    styles = {
        "crypto": (
            "cryptocurrency trading dashboard, Bitcoin and Ethereum symbols, "
            "candlestick charts rising, digital blockchain visualization, "
            "neon blue/gold accents on dark background"
        ),
        "credit_repair": (
            "professional financial growth concept, credit score dashboard rising, "
            "banking documents organized, green upward graphs, clean modern office"
        ),
        "ai_automation": (
            "futuristic AI workspace, holographic interfaces, neural network visuals, "
            "robotic assistants, glowing blue/purple tech, modern office"
        ),
    }
    style = styles.get(topic, (
        "modern successful entrepreneur workspace, professional business growth, "
        "laptop with analytics dashboard, clean minimalist office, urban skyline"
    ))

    prompt = (
        f"Professional high-quality photograph: {clean}. "
        f"{style}. "
        "Cinematic lighting, ultra realistic, 8K, sharp focus, "
        "no text or words in image, photorealistic style"
    )
    return prompt[:400]
