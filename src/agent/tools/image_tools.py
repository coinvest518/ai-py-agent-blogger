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


def generate_image(prompt: str, width: int = 1024, height: int = 1024, timeout: int = 90, platform: str | None = None, overlay_text: str | None = None) -> dict:
    """Generate image with provider preference and graceful fallback.

    Preferred order:
      1. Hugging Face Inference Providers (if `HF_TOKEN` present)
      2. Pollinations cascade (existing fallback)

    Returns dict with 'success', 'image_bytes', 'provider', or 'error'.
    """
    # Build an enhanced prompt tailored to platform + optional overlay text
    try:
        prompt_text = enhance_prompt(prompt, topic=(platform or "business"))
        if overlay_text:
            # Give explicit overlay guidance for designers
            prompt_text += f"\n\nInclude the following overlay text in the image: '{overlay_text}'. Use a clean sans-serif font, high contrast against the background, sized for readability on mobile."

        # 1) Try Hugging Face Inference (preferred when token available)
        hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
        hf_model = os.getenv("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-dev")
        if hf_token:
            try:
                from huggingface_hub import InferenceClient

                client = InferenceClient(hf_token)
                # Use the textToImage helper — client implementations may vary by version.
                try:
                    image_blob = client.text_to_image(model=hf_model, inputs=prompt_text)
                except Exception:
                    # older clients use text_to_image -> .content or streaming; try chat-style call
                    image_blob = client.text_to_image(model=hf_model, inputs=prompt_text)

                # Convert returned blob-like objects to bytes where possible
                image_bytes = None
                if isinstance(image_blob, (bytes, bytearray)):
                    image_bytes = bytes(image_blob)
                else:
                    # Some clients return a requests.Response-like object
                    try:
                        image_bytes = getattr(image_blob, 'content', None) or getattr(image_blob, 'read', lambda: None)()
                    except Exception:
                        image_bytes = None

                if image_bytes:
                    return {"success": True, "image_bytes": image_bytes, "provider": "huggingface_inference", "model": hf_model}
            except Exception as e:
                logger.warning("Hugging Face image generation failed: %s", e)

        # 2) Fallback to Pollinations cascade (existing multi-provider fallback)
        try:
            from src.agent.pollinations_image_gen import generate_image_with_fallback
            return generate_image_with_fallback(prompt=prompt_text, model="flux", width=width, height=height, timeout=timeout)
        except Exception as e:
            logger.warning("Pollinations fallback failed: %s", e)
            return {"success": False, "error": str(e)}

    except Exception as e:
        logger.warning("Image generation orchestration failed: %s", e)
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


def enhance_prompt(text: str, topic: str = "business", platform: str | None = None, overlay_text: str | None = None) -> str:
    """Convert social-media text to a visual prompt for image generation.

    Enhances prompt depending on `platform` (e.g., 'etsy', 'instagram', 'linkedin')
    and includes guidelines for optional `overlay_text` that should appear in the image.

    Returns a clean prompt ≤ 400 chars optimised for FLUX-style models.
    """
    clean = re.sub(r"#\w+", "", text)
    clean = re.sub(r"@\w+", "", clean)
    clean = re.sub(r"https?://\S+", "", clean)
    clean = re.sub(r"[*#@\[\]{}()\'\"\\]", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip()[:200]

    # Platform-specific style guidance
    platform_styles = {
        "crypto": "cryptocurrency trading dashboard, Bitcoin and Ethereum symbols, candlestick charts, neon blue/gold accents on dark background",
        "credit_repair": "professional financial growth concept, credit score dashboard rising, banking documents organized, green upward graphs, clean modern office",
        "ai_automation": "futuristic AI workspace, holographic interfaces, neural network visuals, robotic assistants, glowing blue/purple tech, modern office",
        "etsy": "clean product mockup, flat-lay or white background, soft shadows, high-detail product texture, studio lighting, no watermarks",
        "instagram": "visual-first, cinematic crop, vibrant colors, portrait orientation, strong negative space for caption overlay",
        "linkedin": "professional, editorial style, office or case-study imagery, clean typography space",
        "product_mockup": "device mockup (phone/tablet) with screen showing the product, realistic shadows and reflections",
    }

    style = platform_styles.get(topic, platform_styles.get(platform, (
        "modern successful entrepreneur workspace, professional business growth, laptop with analytics dashboard, clean minimalist office, urban skyline"
    )))

    # Base prompt
    prompt = (
        f"High-quality professional image: {clean}. {style}. "
        "Cinematic lighting, ultra realistic, high detail, sharp focus."
    )

    # Overlay guidance (if requested)
    if overlay_text:
        prompt += (
            f" Include overlay text: '{overlay_text}' in a clean sans-serif font, "
            "high contrast, positioned for mobile readability (top or bottom), no decorative effects."
        )

    # Keep prompt concise for providers with token limits
    return prompt[:400]
