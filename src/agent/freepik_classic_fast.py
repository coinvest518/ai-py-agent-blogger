"""Freepik Classic Fast API Image Generator.

Budget-friendly fallback when Pollinations fails/rate-limits.

API: Classic Fast Text-to-Image ($0.005/image)
Free: $5 credits on signup = 1000 free images!
Docs: https://docs.freepik.com/api/#tag/text-to-image/operation/create_image_from_text_classic
"""

import base64
import logging
import os
from typing import Dict

import requests

logger = logging.getLogger(__name__)

def generate_image_freepik(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    num_images: int = 1,
    timeout: int = 60
) -> Dict:
    """Generate image using Freepik Classic Fast API (budget-friendly fallback).
    
    Args:
        prompt: Text description of the image (min 3 chars)
        width: Image width (1-1792, default 1024)
        height: Image height (1-1792, default 1024) 
        num_images: Number of images to generate (1-4, default 1)
        timeout: Request timeout in seconds
        
    Returns:
        Dict with success, image_bytes, provider, or error
        
    Cost: $0.005 per image (Classic Fast model)
    Free tier: $5 credits = 1000 images on signup
    """
    api_key = os.getenv("FREEPIK_API_KEY")
    
    if not api_key:
        return {
            "success": False,
            "error": "FREEPIK_API_KEY not set in .env"
        }
    
    if len(prompt) < 3:
        return {
            "success": False, 
            "error": "Prompt must be at least 3 characters"
        }
    
    logger.info("🎨 Generating image with Freepik Classic Fast API")
    logger.info("   Prompt: %s...", prompt[:100])
    logger.info("   Size: %dx%d", width, height)
    logger.info("   Cost: $0.005 per image")
    
    # API endpoint - Classic Fast Text-to-Image
    url = "https://api.freepik.com/v1/ai/text-to-image"
    
    headers = {
        "x-freepik-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    # Map dimensions to Freepik aspect ratios
    aspect_ratio = _get_aspect_ratio(width, height)
    
    payload = {
        "prompt": prompt,
        "image": {
            "size": aspect_ratio
        },
        "num_images": min(num_images, 4),  # Max 4 images
        "guidance_scale": 1.0,  # Balanced creativity vs adherence  
        "filter_nsfw": True,  # Always safe content
        "seed": 42  # Fixed seed for consistent results in testing
    }
    
    logger.info("📡 Requesting image from Freepik Classic Fast API...")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract first image from response
            images = data.get("data", [])
            if not images:
                return {
                    "success": False,
                    "error": "No images in Freepik response"
                }
            
            # Decode base64 image
            first_image = images[0]
            base64_data = first_image.get("base64")
            has_nsfw = first_image.get("has_nsfw", False)
            
            if not base64_data:
                return {
                    "success": False,
                    "error": "No base64 image data in Freepik response"
                }
            
            if has_nsfw:
                logger.warning("⚠️ Freepik flagged image as NSFW")
            
            # Convert base64 to bytes
            image_bytes = base64.b64decode(base64_data)
            
            logger.info("✅ Freepik generation successful (%d bytes)", len(image_bytes))
            return {
                "success": True,
                "image_bytes": image_bytes,
                "provider": "Freepik Classic Fast",
                "model": "classic-fast",
                "cost": 0.005,  # USD per image
                "has_nsfw": has_nsfw,
                "meta": data.get("meta", {})
            }
        
        elif response.status_code == 400:
            error_data = response.json()
            return {
                "success": False,
                "error": f"Freepik bad request: {error_data.get('message', 'Invalid parameters')}"
            }
        
        elif response.status_code == 401:
            return {
                "success": False,
                "error": "Invalid Freepik API key (401 Unauthorized)"
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
    
    # Map common ratios to Freepik's supported aspect ratios
    if 0.95 <= ratio <= 1.05:
        return "square_1_1"
    elif 1.3 <= ratio <= 1.35:
        return "classic_4_3"
    elif 0.74 <= ratio <= 0.76:
        return "traditional_3_4"
    elif 1.7 <= ratio <= 1.85:
        return "widescreen_16_9"
    elif 0.5 <= ratio <= 0.6:
        return "social_story_9_16"
    elif 0.65 <= ratio <= 0.68:
        return "portrait_2_3"
    elif 1.45 <= ratio <= 1.55:
        return "standard_3_2"
    elif 1.9 <= ratio <= 2.1:
        return "horizontal_2_1"
    elif 0.45 <= ratio <= 0.55:
        return "vertical_1_2"
    else:
        # Default to square for unusual ratios
        return "square_1_1"