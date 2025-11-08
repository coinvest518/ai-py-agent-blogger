"""Image Prompt Enhancement Sub-Agent.

Converts social media text into clean, visual prompts for AI image generation.
"""

import logging
import os
import re

from langchain_google_genai import GoogleGenerativeAI
from langsmith import traceable

logger = logging.getLogger(__name__)


@traceable(name="enhance_image_prompt")
def enhance_prompt_for_image(text: str) -> str:
    """Convert social media text into a clean visual prompt for image generation.

    Args:
        text: Social media post text with hashtags and formatting.

    Returns:
        Clean, descriptive image prompt optimized for Pollinations AI.
    """
    logger.info("Enhancing image prompt...")

    llm = GoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        temperature=0.7,
        google_api_key=os.getenv("GOOGLE_AI_API_KEY"),
    )

    prompt = f"""
Convert this social media post into a visual art prompt for AI image generation.

SOCIAL MEDIA TEXT:
{text}

REQUIREMENTS:
- Remove ALL hashtags
- Remove ALL special characters (* # @ etc)
- Remove ALL markdown formatting
- Extract core visual theme
- Add professional business imagery keywords
- Style: modern, clean, professional, futuristic
- Maximum 200 characters

OUTPUT:
Return ONLY the clean image prompt. No explanations.
"""

    try:
        response = llm.invoke(prompt)
        visual_prompt = response.strip()

        # Additional cleanup
        visual_prompt = re.sub(r"[*#@\[\]{}()\'\"\\]", "", visual_prompt)
        visual_prompt = re.sub(r"\s+", " ", visual_prompt).strip()

        logger.info("Enhanced prompt: %s", visual_prompt)
        return visual_prompt

    except Exception as e:
        logger.exception("Error enhancing prompt: %s", e)
        # Fallback: basic cleanup
        fallback = re.sub(r"[*#@\[\]{}()\'\"\\]", "", text)
        fallback = re.sub(r"\s+", " ", fallback).strip()
        return f"Professional business image: {fallback[:150]}"
