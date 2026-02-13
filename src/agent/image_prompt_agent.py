"""Image Prompt Enhancement Sub-Agent.

Converts social media text into clean, visual prompts for AI image generation.
"""

import logging
import os
import re

logger = logging.getLogger(__name__)


def enhance_prompt_for_image(text: str, product_name: str = None, product_price: str = None) -> str:
    """Convert social media text into a clean visual prompt for image generation with a selling focus.

    Args:
        text: Social media post text with hashtags and formatting.
        product_name: Optional name of the product to include in the prompt.
        product_price: Optional price of the product to include in the prompt.

    Returns:
        Clean, descriptive image prompt optimized for image generation.
    """
    logger.info("Enhancing image prompt...")

    # Clean the text - remove hashtags, links, special chars
    clean_text = re.sub(r'#\w+', '', text)  # Remove hashtags
    clean_text = re.sub(r'http[s]?://\S+', '', clean_text)  # Remove URLs
    clean_text = re.sub(r'[@*_\[\]{}()\'"\\]', '', clean_text)  # Remove special chars
    clean_text = ' '.join(clean_text.split())  # Clean whitespace
    
    # Build image prompt with business/professional themes
    prompt_parts = [
        "Modern professional business scene:",
        clean_text[:80],  # First 80 chars of cleaned text
        "futuristic AI technology",
        "clean minimalist design",
        "professional lighting"
    ]
    
    if product_name:
        prompt_parts.insert(1, f"featuring {product_name}")
    if product_price:
        prompt_parts.append(f"Buy Now {product_price}")
    
    image_prompt = " ".join(prompt_parts)
    
    # Limit to 200 characters
    if len(image_prompt) > 200:
        image_prompt = image_prompt[:197] + "..."
    
    logger.info("Enhanced prompt: %s", image_prompt)
    return image_prompt
