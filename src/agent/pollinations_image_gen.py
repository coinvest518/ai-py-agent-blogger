"""Pollinations.ai Image Generation Module.

Generate high-quality AI images using Pollinations.ai API.
Primary image generator with HuggingFace as fallback.

Pricing: ~0.0002 pollen per image for Flux Schnell (very affordable!)
Free tier: 1 pollen/day (5000 images/day) - more than enough!
"""

import base64
import io
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import time

import requests
from PIL import Image

logger = logging.getLogger(__name__)

# Pollinations.ai Models - https://pollinations.ai/models
POLLINATIONS_MODELS = {
    # Fast & Free
    "flux": "flux",  # FLUX Schnell - 0.0002 pollen/img (5K images per pollen) - DEFAULT
    "zimage": "zimage",  # Z-Image Turbo - 0.0002 pollen/img (5K images per pollen)
    
    # Premium Quality (requires paid pollen)
    "flux-klein": "klein",  # FLUX.2 Klein 4B - 0.008 pollen/img (150 images per pollen)
    "flux-klein-large": "klein-large",  # FLUX.2 Klein 9B - 0.012 pollen/img (85 images per pollen)
    "gptimage": "gptimage",  # GPT Image 1 Mini - 0.0125 pollen/img (75 images per pollen)
    
    # Best Quality (paid only)
    "seedream": "seedream",  # Seedream 4.0 - 0.03 pollen/img (35 images per pollen)
    "kontext": "kontext",  # FLUX.1 Kontext - 0.04 pollen/img (25 images per pollen)
    "seedream-pro": "seedream-pro",  # Seedream 4.5 Pro - 0.04 pollen/img (25 images per pollen)
}

# API Base URL
POLLINATIONS_API_BASE = "https://api.pollinations.ai"


def generate_image_pollinations(
    prompt: str,
    model: str = "flux",
    width: int = 1024,
    height: int = 1024,
    seed: Optional[int] = None,
    nologo: bool = True,
    enhance: bool = False,
    timeout: int = 90
) -> Dict[str, Any]:
    """Generate image using Pollinations.ai API.
    
    Args:
        prompt: Text description of image to generate
        model: Model key from POLLINATIONS_MODELS dict (default: "flux" = FLUX Schnell)
        width: Image width (512, 768, 1024, 1280, 1536, 2048)
        height: Image height (512, 768, 1024, 1280, 1536, 2048)
        seed: Random seed for reproducibility (None = random)
        nologo: Remove Pollinations watermark (default: True)
        enhance: Use prompt enhancement (default: False)
        timeout: Request timeout in seconds
        
    Returns:
        Dict with success status, image_bytes, model, seed, or error
    """
    api_key = os.getenv("POLLINATIONS_API_KEY")
    
    if not api_key:
        logger.warning("⚠️ POLLINATIONS_API_KEY not set - trying free tier")
        # Pollinations allows some usage without API key (limited)
        api_key = None
    
    # Get model ID
    model_id = POLLINATIONS_MODELS.get(model, POLLINATIONS_MODELS["flux"])
    
    logger.info(f"🎨 Generating image with Pollinations.ai: {model_id}")
    logger.info(f"   Prompt: {prompt[:100]}...")
    logger.info(f"   Size: {width}x{height}, Nologo: {nologo}, Enhance: {enhance}")
    
    try:
        # Build request URL (Pollinations uses GET with query params)
        url = f"{POLLINATIONS_API_BASE}/v1/image"
        
        # Build request parameters
        params = {
            "model": model_id,
            "prompt": prompt,
            "width": width,
            "height": height,
            "nologo": str(nologo).lower(),
            "enhance": str(enhance).lower()
        }
        
        # Add seed if provided
        if seed is not None:
            params["seed"] = seed
        
        # Build headers
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        # Make request
        logger.info(f"📡 Requesting image from Pollinations.ai...")
        start_time = time.time()
        
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout
        )
        
        response.raise_for_status()
        
        # Check if response is JSON error
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' in content_type:
            error_data = response.json()
            error_msg = error_data.get('error', 'Unknown API error')
            logger.error(f"❌ Pollinations API error: {error_msg}")
            return {
                "success": False,
                "error": f"Pollinations API error: {error_msg}"
            }
        
        # Get image bytes
        image_bytes = response.content
        
        # Get seed from response headers if available
        response_seed = response.headers.get('X-Seed')
        
        elapsed = time.time() - start_time
        
        logger.info(f"✅ Image generated successfully in {elapsed:.1f}s")
        logger.info(f"   Size: {len(image_bytes):,} bytes")
        if response_seed:
            logger.info(f"   Seed: {response_seed} (use this to reproduce)")
        
        return {
            "success": True,
            "image_bytes": image_bytes,
            "model": model_id,
            "seed": response_seed or seed,
            "generation_time": elapsed
        }
        
    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Pollinations API timeout after {timeout}s")
        return {
            "success": False,
            "error": f"Request timeout after {timeout}s - try again or use a different model"
        }
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        error_msg = f"HTTP {status_code}"
        
        # Parse error details
        try:
            error_data = e.response.json()
            error_msg = error_data.get('error', error_msg)
        except:
            pass
        
        logger.error(f"❌ Pollinations API HTTP error: {error_msg}")
        
        # Specific error handling
        if status_code == 401:
            return {
                "success": False,
                "error": "Invalid API key - check POLLINATIONS_API_KEY in .env"
            }
        elif status_code == 402:
            return {
                "success": False,
                "error": "Insufficient pollen balance - buy more at https://pollinations.ai"
            }
        elif status_code == 429:
            return {
                "success": False,
                "error": "Rate limit exceeded - wait or upgrade tier at https://pollinations.ai"
            }
        else:
            return {
                "success": False,
                "error": f"Pollinations API error: {error_msg}"
            }
    except Exception as e:
        logger.exception(f"❌ Pollinations image generation error: {e}")
        return {"success": False, "error": str(e)}


def generate_image_with_fallback(
    prompt: str,
    model: str = "flux",
    width: int = 1024,
    height: int = 1024,
    timeout: int = 90
) -> Dict[str, Any]:
    """Generate image with automatic 3-tier fallback: Pollinations → Freepik → HuggingFace.
    
    This is the RECOMMENDED function to use:
    1. Tries Pollinations first (best quality, fastest, free tier)
    2. Falls back to Freepik if Pollinations fails (budget-friendly $0.005/image)
    3. Falls back to HuggingFace if both fail and HF_ENABLE=true
    
    Args:
        prompt: Text description of image to generate
        model: Model key (default: "flux" for Pollinations)
        width: Image width
        height: Image height
        timeout: Request timeout in seconds
        
    Returns:
        Dict with success status, image_bytes, provider, model, or error
    """
    logger.info("🎨 Attempting 3-tier image generation: POLLINATIONS → FREEPIK → HUGGINGFACE")
    
    # Step 1: Try Pollinations.ai (PRIMARY - Best quality, free tier)
    logger.info("🌸 Trying Pollinations.ai first...")
    result = generate_image_pollinations(
        prompt=prompt,
        model=model,
        width=width,
        height=height,
        timeout=timeout
    )
    
    if result["success"]:
        logger.info("✅ SUCCESS with Pollinations.ai!")
        result["provider"] = "Pollinations.ai"
        return result
    
    # Step 2: Fallback to Freepik (SECONDARY - Budget-friendly $0.005/image)
    logger.warning(f"⚠️ Pollinations failed: {result.get('error')}")
    logger.info("💵 Falling back to Freepik API (budget-friendly)...")
    
    freepik_key = os.getenv("FREEPIK_API_KEY")
    if freepik_key:
        try:
            from src.agent.freepik_classic_fast import generate_image_freepik
            
            freepik_result = generate_image_freepik(
                prompt=prompt,
                width=width,
                height=height,
                timeout=timeout
            )
            
            if freepik_result["success"]:
                logger.info("✅ SUCCESS with Freepik API! ($0.005 cost)")
                return freepik_result
            
            logger.warning(f"⚠️ Freepik also failed: {freepik_result.get('error')}")
        
        except Exception as e:
            logger.warning(f"⚠️ Freepik fallback error: {e}")
    else:
        logger.info("💡 FREEPIK_API_KEY not set - skipping Freepik fallback")
    
    # Step 3: Fallback to HuggingFace (TERTIARY - only if enabled)
    hf_enabled = os.getenv("HF_ENABLE", "false").lower() in ("1", "true", "yes")
    
    if not hf_enabled:
        logger.warning("⚠️ All providers failed and HuggingFace is DISABLED (HF_ENABLE=false)")
        logger.info("💡 Set HF_ENABLE=true in .env to enable HuggingFace fallback")
        return {
            "success": False,
            "error": f"Pollinations failed: {result.get('error')}. Freepik {'failed' if freepik_key else 'not configured'}. HuggingFace disabled."
        }
    
    logger.info("🤗 Last resort: Falling back to HuggingFace...")
    
    try:
        from src.agent.hf_image_gen import generate_image_hf
        
        # Map Pollinations model to HF model if needed
        hf_model = "flux-schnell"  # Default HF model (fast)
        if "klein" in model or "gptimage" in model or "seedream" in model:
            hf_model = "flux-dev"  # Use better HF model for premium requests
        
        hf_result = generate_image_hf(
            prompt=prompt,
            model=hf_model,
            width=width,
            height=height,
            timeout=timeout
        )
        
        if hf_result["success"]:
            logger.info("✅ SUCCESS with HuggingFace fallback!")
            hf_result["provider"] = "HuggingFace (fallback)"
            return hf_result
        else:
            logger.error(f"❌ HuggingFace also failed: {hf_result.get('error')}")
            return {
                "success": False,
                "error": f"Both providers failed. Pollinations: {result.get('error')}. HuggingFace: {hf_result.get('error')}"
            }
    except Exception as e:
        logger.exception(f"❌ Fallback to HuggingFace failed: {e}")
        return {
            "success": False,
            "error": f"Pollinations failed: {result.get('error')}. HuggingFace unavailable: {str(e)}"
        }


def save_image_locally(image_bytes: bytes, filename: str = None, provider: str = "pollinations") -> str:
    """Save image bytes to local file.
    
    Args:
        image_bytes: Raw image data
        filename: Optional filename (auto-generated if not provided)
        provider: Provider name for filename prefix
        
    Returns:
        Local file path
    """
    # Create temp_images directory if it doesn't exist
    temp_dir = Path("temp_images")
    temp_dir.mkdir(exist_ok=True)
    
    # Generate filename if not provided
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = provider.lower().replace(" ", "_").replace("(", "").replace(")", "")
        filename = f"{prefix}_image_{timestamp}.png"
    
    filepath = temp_dir / filename
    
    # Save image
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    
    logger.info(f"💾 Image saved to: {filepath}")
    return str(filepath.absolute())


def upload_to_imgbb(image_bytes: bytes, timeout: int = 30) -> Dict[str, Any]:
    """Upload image to imgbb for free public HTTP hosting.
    
    imgbb provides FREE image hosting with public URLs.
    Get your free API key at: https://api.imgbb.com/
    
    Args:
        image_bytes: Raw image data
        timeout: Request timeout in seconds
        
    Returns:
        Dict with success status, url, or error
    """
    imgbb_key = os.getenv("IMGBB_API_KEY")
    
    if not imgbb_key:
        return {
            "success": False,
            "error": "IMGBB_API_KEY not set. Get free key at https://api.imgbb.com/"
        }
    
    try:
        logger.info("📤 Uploading image to ImgBB...")
        
        # Encode image to base64
        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # Upload to imgbb
        response = requests.post(
            "https://api.imgbb.com/1/upload",
            data={
                "key": imgbb_key,
                "image": b64_image
            },
            timeout=timeout
        )
        
        response.raise_for_status()
        data = response.json()
        
        if data.get("success"):
            url = data["data"]["url"]
            logger.info(f"✅ Image uploaded to: {url}")
            return {
                "success": True,
                "url": url,
                "delete_url": data["data"].get("delete_url")
            }
        else:
            error = data.get("error", {}).get("message", "Unknown error")
            logger.error(f"❌ ImgBB upload failed: {error}")
            return {"success": False, "error": error}
            
    except Exception as e:
        logger.exception(f"❌ ImgBB upload error: {e}")
        return {"success": False, "error": str(e)}


# Test function
def test_pollinations_image_gen():
    """Test Pollinations.ai image generation."""
    print("🧪 Testing Pollinations.ai Image Generation\n")
    
    # Test prompt
    test_prompt = "A futuristic AI robot analyzing crypto trading charts, digital art style, vibrant colors, professional"
    
    print(f"Prompt: {test_prompt}\n")
    
    # Test with fallback
    result = generate_image_with_fallback(
        prompt=test_prompt,
        model="flux",  # Fast & free
        width=1024,
        height=1024,
        timeout=90
    )
    
    if result["success"]:
        print(f"✅ SUCCESS!")
        print(f"   Provider: {result.get('provider', 'Unknown')}")
        print(f"   Model: {result.get('model', 'Unknown')}")
        print(f"   Size: {len(result['image_bytes']):,} bytes")
        if result.get('seed'):
            print(f"   Seed: {result['seed']}")
        
        # Save locally
        filepath = save_image_locally(
            result["image_bytes"],
            provider=result.get('provider', 'pollinations')
        )
        print(f"   Saved to: {filepath}")
        
        # Upload to imgbb (if key available)
        upload_result = upload_to_imgbb(result["image_bytes"])
        if upload_result["success"]:
            print(f"   Public URL: {upload_result['url']}")
        else:
            print(f"   ImgBB upload skipped: {upload_result.get('error')}")
            
    else:
        print(f"❌ FAILURE: {result.get('error')}")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run test
    test_pollinations_image_gen()
