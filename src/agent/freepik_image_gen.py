"""
Freepik API Image Generator
Budget-friendly fallback when Pollinations fails/rate-limits.

Pricing: Classic Fast model = $0.005/image (1000 images for $5)
Free: $5 credits on signup = 1000 free images!

Documentation: https://developers.freepik.com/docs/ai-image-generator
"""

import os
import logging
import base64
import requests
import time
from typing import Dict

logger = logging.getLogger(__name__)

def generate_image_freepik(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    model: str = "classic_fast",  # Classic Fast = $0.005/image (cheapest!)
    timeout: int = 60
) -> Dict:
    """Generate image using Freepik Classic Fast API (budget-friendly fallback).
    
    Following Freepik API documentation EXACTLY as provided:
    - Endpoint: /v1/ai/text-to-image  
    - Auth: x-freepik-api-key header
    - Model: classic_fast ($0.005/img) or mystic models ($0.069+/img)
    
    Args:
        prompt: Text description of the image
        width: Image width (default 1024)
        height: Image height (default 1024)
        model: "classic_fast" (cheapest) or mystic models
        timeout: Request timeout in seconds
        
    Returns:
        Dict with success, image_bytes, provider, or error
    """
    api_key = os.getenv("FREEPIK_API_KEY")
    
    if not api_key:
        return {
            "success": False,
            "error": "FREEPIK_API_KEY not set in .env"
        }
    
    logger.info("🎨 Generating image with Freepik API")
    logger.info("   Model: Classic Fast ($0.005/image)")
    logger.info("   Prompt: %s...", prompt[:100])
    logger.info("   Size: %dx%d", width, height)
    
    # Map dimensions to Freepik aspect ratios (per documentation)
    aspect_ratio = _get_aspect_ratio(width, height)
    resolution = _get_resolution(width, height)
    
    # Freepik API endpoint (per documentation)
    url = "https://api.freepik.com/v1/ai/text-to-image"
    
    # Authentication per documentation: x-freepik-api-key header
    headers = {
        "x-freepik-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    # Payload EXACTLY per Freepik Mystic API documentation provided
    payload = {
        "prompt": prompt,
        "resolution": "1k",  # 1k = cheapest, good enough for social media
        "aspect_ratio": "square_1_1",  # Standard square
        # "model": "realism",  # Try default model (don't specify)
        "creative_detailing": 33,  # Default per documentation
        "engine": "automatic",  # Default per documentation
        "fixed_generation": False,  # Random variety
        "filter_nsfw": True  # Always safe
    }
    
    logger.info("📡 Requesting image from Freepik API...")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        
        if response.status_code == 200:
            data = response.json()
            task_id = data.get("data", {}).get("task_id")
            
            if not task_id:
                return {
                    "success": False,
                    "error": "No task_id in Freepik response"
                }
            
            # Poll for completion (Freepik generates async)
            logger.info("⏳ Waiting for Freepik to generate image (task: %s)...", task_id)
            image_url = _poll_task_status(task_id, api_key, timeout=120)
            
            if image_url:
                # Download the generated image
                image_response = requests.get(image_url, timeout=30)
                
                if image_response.status_code == 200:
                    logger.info("✅ Freepik generation successful (%d bytes)", len(image_response.content))
                    return {
                        "success": True,
                        "image_bytes": image_response.content,
                        "provider": "Freepik API",
                        "model": model,
                        "cost": 0.005  # USD per image
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to download Freepik image: HTTP {image_response.status_code}"
                    }
            else:
                return {
                    "success": False,
                    "error": "Freepik generation timed out or failed"
                }
        
        elif response.status_code == 401:
            return {
                "success": False,
                "error": "Invalid Freepik API key (401 Unauthorized)"
            }
        
        elif response.status_code == 402:
            return {
                "success": False,
                "error": "Freepik out of credits (402 Payment Required)"
            }
        
        elif response.status_code == 429:
            return {
                "success": False,
                "error": "Freepik rate limit exceeded (429 Too Many Requests)"
            }
        
        else:
            error_text = response.text[:500]
            return {
                "success": False,
                "error": f"Freepik API error: HTTP {response.status_code} - {error_text}"
            }
    
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Freepik request timed out"
        }
    
    except requests.exceptions.ConnectionError as e:
        return {
            "success": False,
            "error": f"Freepik connection error: {e}"
        }
    
    except Exception as e:
        logger.error("Freepik generation failed: %s", e)
        return {
            "success": False,
            "error": f"Freepik error: {str(e)}"
        }


def _get_aspect_ratio(width: int, height: int) -> str:
    """Convert dimensions to Freepik aspect ratio string."""
    ratio = width / height
    
    if 0.95 <= ratio <= 1.05:
        return "square_1_1"
    elif 1.3 <= ratio <= 1.35:
        return "classic_4_3"
    elif 1.7 <= ratio <= 1.85:
        return "widescreen_16_9"
    elif 0.5 <= ratio <= 0.6:
        return "social_story_9_16"
    elif 1.4 <= ratio <= 1.55:
        return "traditional_3_4"
    else:
        return "square_1_1"  # Default


def _get_resolution(width: int, height: int) -> str:
    """Convert dimensions to Freepik resolution string."""
    max_dim = max(width, height)
    
    if max_dim >= 2048:
        return "4k"
    elif max_dim >= 1024:
        return "2k"
    else:
        return "1k"


def _poll_task_status(task_id: str, api_key: str, timeout: int = 120) -> str:
    """Poll Freepik task status until complete or timeout.
    
    Returns:
        Image URL if successful, None otherwise
    """
    import time
    
    url = f"https://api.freepik.com/v1/ai/text-to-image/{task_id}"
    headers = {"x-freepik-api-key": api_key}
    
    start_time = time.time()
    poll_interval = 2  # seconds
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("data", {}).get("status")
                
                if status == "COMPLETED":
                    generated = data.get("data", {}).get("generated", [])
                    if generated:
                        logger.info("✅ Freepik task completed!")
                        return generated[0]  # Return first image URL
                
                elif status in ["FAILED", "CANCELLED"]:
                    logger.error("❌ Freepik task failed: %s", status)
                    return None
                
                # Still processing, wait and retry
                logger.info("⏳ Freepik status: %s (%.1fs elapsed)", status, time.time() - start_time)
                time.sleep(poll_interval)
            
            else:
                logger.error("Failed to poll Freepik task: HTTP %d", response.status_code)
                return None
        
        except Exception as e:
            logger.error("Error polling Freepik task: %s", e)
            return None
    
    logger.error("❌ Freepik polling timed out after %ds", timeout)
    return None
