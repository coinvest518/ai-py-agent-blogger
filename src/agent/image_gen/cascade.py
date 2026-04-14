"""Image generation cascade — primary providers first, Pollinations as last fallback.

Order:
  1. Cloudflare Workers AI (free tier, fast)
  2. HuggingFace (free tier, FLUX-schnell)
  3. Google Gemini Image
  4. NVIDIA NIM FLUX
  5. Freepik ($0.005/image)
  6. Pollinations.ai (last-resort fallback)

Each provider is skipped silently when its API key is missing.
"""

import logging
import os
from typing import Any, Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)


def _try_cloudflare(prompt, width, height, timeout):
    from src.agent.image_gen.cloudflare_image import generate_image_cloudflare
    return generate_image_cloudflare(prompt, width, height, timeout=timeout)


def _try_hf(prompt, width, height, timeout):
    if not os.getenv("HF_TOKEN"):
        return {"success": False, "error": "HF_TOKEN not set"}
    if os.getenv("HF_ENABLE", "true").lower() not in ("1", "true", "yes"):
        return {"success": False, "error": "HF_ENABLE=false"}
    from src.agent.hf_image_gen import generate_image_hf
    return generate_image_hf(prompt, model="flux-schnell", width=width, height=height, timeout=timeout)


def _try_google(prompt, width, height, timeout):
    from src.agent.image_gen.google_image import generate_image_google
    return generate_image_google(prompt, width, height, timeout)


def _try_nvidia(prompt, width, height, timeout):
    from src.agent.image_gen.nvidia_image import generate_image_nvidia
    return generate_image_nvidia(prompt, width, height, timeout=timeout)


def _try_freepik(prompt, width, height, timeout):
    if not os.getenv("FREEPIK_API_KEY"):
        return {"success": False, "error": "FREEPIK_API_KEY not set"}
    from src.agent.freepik_classic_fast import generate_image_freepik
    return generate_image_freepik(prompt=prompt, width=width, height=height, timeout=timeout)


def _try_pollinations(prompt, width, height, timeout):
    from src.agent.pollinations_image_gen import generate_image_pollinations
    res = generate_image_pollinations(prompt=prompt, model="flux", width=width, height=height, timeout=timeout)
    if res.get("success"):
        res["provider"] = "Pollinations.ai (fallback)"
    return res


_CASCADE: List[Tuple[str, Callable]] = [
    ("Cloudflare", _try_cloudflare),
    ("HuggingFace", _try_hf),
    ("Google", _try_google),
    ("NVIDIA", _try_nvidia),
    ("Freepik", _try_freepik),
    ("Pollinations", _try_pollinations),
]


def generate_with_cascade(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Try each provider in order; return first success."""
    errors = []
    for name, fn in _CASCADE:
        logger.info("🎨 Trying %s…", name)
        try:
            res = fn(prompt, width, height, timeout)
        except Exception as e:
            res = {"success": False, "error": f"{name} threw: {e}"}
        if res.get("success"):
            logger.info("✅ Image gen success via %s", res.get("provider", name))
            return res
        err = res.get("error", "unknown")
        logger.info("⏭️  %s skipped/failed: %s", name, err[:120])
        errors.append(f"{name}: {err[:80]}")

    return {"success": False, "error": "All providers failed — " + " | ".join(errors)}
