"""Hugging Face Image Generation Module.

Generate images using Hugging Face Inference API - FREE alternative to Google Gemini.
Uses huggingface_hub InferenceClient for text-to-image generation.
"""

import logging
import os
import io
import base64
import requests
from typing import Dict, Any
from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

# Available FREE models on Hugging Face Inference Providers API:
HF_MODELS = {
    "flux-dev": "black-forest-labs/FLUX.1-dev",  # High quality FLUX model
    "flux-krea": "black-forest-labs/FLUX.1-Krea-dev",  # Most powerful for realistic outputs
    "flux-schnell": "black-forest-labs/FLUX.1-schnell",  # Fast generation
    "sdxl-lightning": "ByteDance/SDXL-Lightning",  # Fast and powerful
    "stable-diffusion-xl": "stabilityai/stable-diffusion-xl-base-1.0",
    "stable-diffusion": "runwayml/stable-diffusion-v1-5",
}

def generate_image_hf(
    prompt: str,
    model: str = "flux-schnell",
    negative_prompt: str = None,
    width: int = 512,
    height: int = 512,
    num_inference_steps: int = 4,
    guidance_scale: float = 0.0,
    timeout: int = 60
) -> Dict[str, Any]:
    """Generate image using Hugging Face Inference API (FREE).
    
    Args:
        prompt: Text description of image to generate
        model: Model key from HF_MODELS dict
        negative_prompt: What to avoid in the image (not supported by all models)
        width: Image width (512, 768, 1024)
        height: Image height (512, 768, 1024)
        num_inference_steps: Number of denoising steps (flux-schnell uses 4)
        guidance_scale: How closely to follow the prompt (flux-schnell uses 0.0)
        timeout: Request timeout in seconds
        
    Returns:
        Dict with success status, image_bytes, or error
    """
    hf_token = os.getenv("HF_TOKEN")
    
    if not hf_token:
        return {
            "success": False,
            "error": "HF_TOKEN not set in .env. Get free token at https://huggingface.co/settings/tokens"
        }
    
    # Get model ID
    model_id = HF_MODELS.get(model, HF_MODELS["flux-schnell"])
    
    logger.info(f"Generating image with Hugging Face: {model_id}")
    logger.info(f"Prompt: {prompt[:100]}...")
    
    try:
        # Initialize InferenceClient
        client = InferenceClient(
            provider="hf-inference",
            api_key=hf_token,
        )
        
        # Generate image (returns PIL.Image object)
        image = client.text_to_image(
            prompt=prompt,
            model=model_id,
        )
        
        # Convert PIL Image to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        image_bytes = img_byte_arr.getvalue()
        
        logger.info(f"✅ Image generated successfully: {len(image_bytes)} bytes")
        
        return {
            "success": True,
            "image_bytes": image_bytes,
            "model": model_id
        }
            
    except Exception as e:
        logger.exception(f"HF image generation error: {e}")
        return {"success": False, "error": str(e)}


def save_image_locally(image_bytes: bytes, filename: str = None) -> str:
    """Save image bytes to local file.
    
    Args:
        image_bytes: Raw image data
        filename: Optional filename (auto-generated if not provided)
        
    Returns:
        Local file path
    """
    import os
    from pathlib import Path
    from datetime import datetime
    
    # Create temp_images directory if it doesn't exist
    temp_dir = Path("temp_images")
    temp_dir.mkdir(exist_ok=True)
    
    # Generate filename if not provided
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"hf_image_{timestamp}.png"
    
    filepath = temp_dir / filename
    
    # Save image
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    
    logger.info(f"Image saved to: {filepath}")
    return str(filepath.absolute())


def upload_to_imgbb(image_bytes: bytes, api_key: str = None) -> Dict[str, Any]:
    """Upload image to imgbb for free public hosting (Instagram/Blog compatible).
    
    Args:
        image_bytes: Raw image data
        api_key: imgbb API key (get free at https://api.imgbb.com/)
        
    Returns:
        Dict with success status and public URL
    """
    import base64
    
    if not api_key:
        api_key = os.getenv("IMGBB_API_KEY")
    
    if not api_key:
        return {
            "success": False,
            "error": "IMGBB_API_KEY not set. Get free key at https://api.imgbb.com/"
        }
    
    # imgbb requires base64 encoded image
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    url = "https://api.imgbb.com/1/upload"
    payload = {
        "key": api_key,
        "image": base64_image,
    }
    
    try:
        response = requests.post(url, data=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                image_url = data["data"]["url"]
                logger.info(f"✅ Image uploaded to imgbb: {image_url}")
                return {
                    "success": True,
                    "url": image_url,
                    "delete_url": data["data"].get("delete_url"),
                    "thumb_url": data["data"].get("thumb", {}).get("url"),
                }
            else:
                error_msg = data.get("error", {}).get("message", "Upload failed")
                return {"success": False, "error": error_msg}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        logger.exception(f"imgbb upload error: {e}")
        return {"success": False, "error": str(e)}


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
        # Convert image bytes to base64
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        
        # Upload to imgbb
        upload_url = "https://api.imgbb.com/1/upload"
        payload = {
            "key": imgbb_key,
            "image": image_base64
        }
        
        logger.info("Uploading image to imgbb...")
        response = requests.post(upload_url, data=payload, timeout=timeout)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                image_url = result["data"]["url"]
                logger.info(f"✅ Image uploaded to imgbb: {image_url}")
                return {
                    "success": True,
                    "url": image_url,
                    "delete_url": result["data"].get("delete_url"),
                    "display_url": result["data"].get("display_url")
                }
            else:
                error_msg = result.get("error", {}).get("message", "Upload failed")
                return {"success": False, "error": error_msg}
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}"
            }
            
    except Exception as e:
        logger.exception(f"imgbb upload error: {e}")
        return {"success": False, "error": str(e)}


def upload_to_imgur(image_bytes: bytes, timeout: int = 30) -> Dict[str, Any]:
    """Upload image to imgur for free public HTTP hosting (NO API KEY NEEDED).
    
    Imgur allows anonymous uploads without authentication.
    
    Args:
        image_bytes: Raw image data
        timeout: Request timeout in seconds
        
    Returns:
        Dict with success status, url, or error
    """
    try:
        # Convert image bytes to base64
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        
        # Upload to imgur (anonymous)
        upload_url = "https://api.imgur.com/3/upload"
        headers = {
            "Authorization": "Client-ID 546c25a59c58ad7"  # Public anonymous client ID
        }
        payload = {
            "image": image_base64,
            "type": "base64"
        }
        
        logger.info("Uploading image to imgur (anonymous)...")
        response = requests.post(upload_url, headers=headers, data=payload, timeout=timeout)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                image_url = result["data"]["link"]
                logger.info(f"✅ Image uploaded to imgur: {image_url}")
                return {
                    "success": True,
                    "url": image_url,
                    "delete_hash": result["data"].get("deletehash")
                }
            else:
                return {"success": False, "error": "Upload failed"}
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}"
            }
            
    except Exception as e:
        logger.exception(f"imgur upload error: {e}")
        return {"success": False, "error": str(e)}


# Quick test function
def test_huggingface_image_gen():
    """Test Hugging Face image generation and upload."""
    print("Testing Hugging Face Image Generation + Upload...")
    print("=" * 60)
    
    test_prompt = "Modern professional business office with AI technology, futuristic clean design, professional lighting"
    
    result = generate_image_hf(
        prompt=test_prompt,
        model="flux-schnell",  # Fast FLUX model
        width=512,
        height=512,
    )
    
    if result["success"]:
        print(f"✅ Image generated successfully!")
        print(f"   Model: {result['model']}")
        print(f"   Size: {len(result['image_bytes'])} bytes")
        
        # Save locally
        filepath = save_image_locally(result["image_bytes"], "test_hf_gen.png")
        print(f"   Saved to: {filepath}")
        
        # Try uploading to imgur (no API key needed)
        print("\nUploading to imgur (anonymous)...")
        upload_result = upload_to_imgur(result["image_bytes"])
        
        if upload_result["success"]:
            print(f"✅ Uploaded to imgur: {upload_result['url']}")
            print(f"   This URL works for Instagram/Blog/Email!")
            return upload_result['url']
        else:
            print(f"⚠️ Upload failed: {upload_result['error']}")
            print(f"   Local file still available: {filepath}")
            return filepath
    else:
        print(f"❌ Generation failed: {result['error']}")
        return None


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    test_huggingface_image_gen()
