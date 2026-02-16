"""Image Prompt Agent — LLM-powered visual prompt designer for FDWA brand.

Uses the cascading LLM to craft detailed, brand-consistent image prompts
based on the post content, topic, and FDWA's visual identity.

FDWA Brand Visual Identity (derived from generated content library):
- Cyberpunk/futuristic cityscape with neon-lit skyscrapers
- Black woman protagonist in tech/futuristic attire
- Holographic UI dashboards, charts, data visualizations
- Neon color palette: cyan, magenta, purple, gold accents on dark backgrounds
- Cinematic composition, dramatic lighting, atmospheric depth
- No readable text in images (text is added separately)
"""

import logging
import os
import re
from pathlib import Path

from src.agent.core.config import TEMP_IMAGES_DIR, detect_topic
from src.agent.llm_provider import get_llm

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FDWA Brand Visual DNA — the core aesthetic every image must follow
# ---------------------------------------------------------------------------

FDWA_VISUAL_DNA = """FDWA BRAND VISUAL IDENTITY:
- Setting: Cyberpunk/futuristic cityscape, neon-lit skyscrapers, rain-slicked streets
- Protagonist: Confident Black woman in sleek futuristic tech attire (bodysuit, trenchcoat, or professional futuristic outfit)
- Technology: Holographic floating UI panels, transparent data dashboards, glowing charts and graphs
- Color palette: Deep dark backgrounds with neon cyan, electric magenta, vivid purple, gold/amber accents
- Lighting: Cinematic dramatic lighting, volumetric light rays, neon reflections on wet surfaces
- Atmosphere: Atmospheric fog/haze, depth of field, urban energy, flying drones in background
- Composition: Wide or medium shot, protagonist interacting with holographic displays
- Style: Ultra-realistic digital art, 8K detail, photorealistic rendering
- NEVER include readable text, words, or letters in the image"""


# Topic-specific visual elements to layer on top of brand DNA
TOPIC_VISUALS = {
    "crypto": {
        "elements": "cryptocurrency trading dashboards, Bitcoin/Ethereum holographic symbols, candlestick charts glowing green, blockchain network visualization, digital wallet interfaces floating in air",
        "mood": "high-tech trading floor energy, wealth and power, digital gold rush",
        "colors": "neon gold, electric green, cyan blue accents",
    },
    "credit_repair": {
        "elements": "credit score gauge rising to 800+, financial documents being organized by AI, debt chains breaking apart, credit report hologram showing improvements",
        "mood": "empowerment, financial freedom, breaking free from debt, professional confidence",
        "colors": "emerald green, cyan, white highlights on dark background",
    },
    "ai_automation": {
        "elements": "neural network holographic web, AI assistant robot/avatar, automated workflow pipelines visualized as glowing streams, multiple holographic screens showing analytics",
        "mood": "cutting-edge innovation, power of automation, limitless possibility",
        "colors": "electric blue, vivid purple, magenta energy streams",
    },
    "general": {
        "elements": "digital wealth dashboard, multiple revenue streams visualized as data flows, entrepreneurship tools floating holographically, modern business ecosystem",
        "mood": "success, ambition, digital entrepreneurship, modern wealth building",
        "colors": "balanced neon palette — cyan, magenta, purple, gold",
    },
}

# Product-specific visual overlays
PRODUCT_VISUALS = {
    "credit repair": "AI-powered credit analyzer hologram, dispute letter generator interface, credit score transformation dashboard",
    "ebook": "digital book floating holographically, pages turning with glowing data, knowledge download visualization",
    "course": "virtual classroom hologram, learning pathway visualization, certification badge glowing",
    "ai tool": "AI workflow builder interface, automation pipeline visualized, bot army deployment",
    "consulting": "strategy hologram, business growth chart, one-on-one virtual meeting visualization",
    "yieldbot": "crypto trading bot interface, automated DeFi yield farming dashboard, token analytics",
}


def _get_recent_image_styles() -> str:
    """Scan temp_images/ for recent files to understand what's been generated.
    
    Returns a summary string of recent image filenames for style continuity.
    """
    try:
        if not TEMP_IMAGES_DIR.exists():
            return ""
        
        files = sorted(TEMP_IMAGES_DIR.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
        recent = [f.name for f in files[:10] if f.suffix in (".png", ".jpg", ".jpeg")]
        
        if not recent:
            return ""
        
        # Extract provider info from filenames
        providers = set()
        for name in recent:
            if "pollinations" in name.lower():
                providers.add("Pollinations")
            elif "freepik" in name.lower():
                providers.add("Freepik")
            elif "hf_" in name.lower():
                providers.add("HuggingFace")
        
        return f"Recent images ({len(recent)} files, providers: {', '.join(providers) or 'mixed'})"
    except Exception:
        return ""


def generate_image_prompt(
    post_text: str,
    topic: str | None = None,
    product_name: str | None = None,
    product_price: str | None = None,
    platform: str = "general",
    use_llm: bool = True,
) -> str:
    """Generate a detailed, brand-consistent image prompt using the LLM.

    Args:
        post_text: The social media post text to visualize.
        topic: Content topic ('crypto', 'credit_repair', 'ai_automation', 'general').
                Auto-detected from post_text if not provided.
        product_name: Optional product name for selling-focused images.
        product_price: Optional price for product-focused images.
        platform: Target platform (affects composition — square for IG, wider for blog).
        use_llm: If True, uses LLM for creative prompt. If False, uses template fallback.

    Returns:
        A detailed image generation prompt string (300-500 chars).
    """
    # Auto-detect topic if not provided
    if not topic:
        topic = detect_topic(post_text)
    
    topic_data = TOPIC_VISUALS.get(topic, TOPIC_VISUALS["general"])
    
    # Clean the post text for context extraction
    clean_text = re.sub(r"#\w+", "", post_text)
    clean_text = re.sub(r"https?://\S+", "", clean_text)
    clean_text = re.sub(r"[@*_\[\]{}()\\'\"\\\\]", "", clean_text)
    clean_text = " ".join(clean_text.split())[:150]
    
    # Product overlay
    product_context = ""
    if product_name:
        # Find matching product visual
        for key, visual in PRODUCT_VISUALS.items():
            if key in product_name.lower():
                product_context = f"\nProduct focus: {product_name}"
                if product_price:
                    product_context += f" (${product_price})"
                product_context += f"\nProduct visual elements: {visual}"
                break
        if not product_context and product_name:
            product_context = f"\nProduct focus: {product_name}"
            if product_price:
                product_context += f" (${product_price})"
    
    # Recent images context
    recent = _get_recent_image_styles()
    
    if use_llm:
        prompt = _llm_generate_prompt(
            clean_text, topic, topic_data, product_context, platform, recent
        )
        if prompt and len(prompt) > 50:
            return prompt
        logger.warning("LLM prompt generation failed, using template fallback")
    
    # Template fallback (no LLM needed)
    return _template_prompt(clean_text, topic, topic_data, product_name)


def _llm_generate_prompt(
    clean_text: str,
    topic: str,
    topic_data: dict,
    product_context: str,
    platform: str,
    recent_context: str,
) -> str:
    """Use the cascading LLM to craft a creative, brand-aligned image prompt."""
    
    composition_hint = {
        "instagram": "Square 1:1 composition, centered subject, high visual impact",
        "blog": "Wide 16:9 composition, dramatic landscape orientation, editorial quality",
        "twitter": "Wide composition, bold visual, high contrast for small thumbnails",
        "general": "Versatile composition, works at any aspect ratio",
    }.get(platform, "Versatile composition")
    
    system_prompt = f"""You are FDWA's visual creative director. Your job is to write image generation prompts
that perfectly match the FDWA cyberpunk brand aesthetic.

{FDWA_VISUAL_DNA}

TOPIC: {topic}
TOPIC ELEMENTS: {topic_data['elements']}
MOOD: {topic_data['mood']}
COLORS: {topic_data['colors']}
{product_context}

COMPOSITION: {composition_hint}
{f'CONTINUITY: {recent_context}' if recent_context else ''}

RULES FOR YOUR PROMPT:
1. Output ONLY the image generation prompt — no explanation, no quotes
2. 300-500 characters maximum
3. Always include the Black woman protagonist in futuristic attire
4. Always include the cyberpunk cityscape backdrop
5. Always include holographic UI/dashboard elements
6. Incorporate topic-specific visual elements naturally
7. Specify lighting, atmosphere, and camera angle
8. End with quality keywords: ultra realistic, 8K, cinematic lighting
9. NEVER include text, words, watermarks, or logos in the prompt
10. Each prompt should feel unique while staying on-brand"""

    user_prompt = f"""Create an image prompt for this social media post:

"{clean_text}"

Remember: cyberpunk cityscape, Black woman in futuristic tech attire, holographic dashboards, 
neon {topic_data['colors']}, cinematic atmosphere. Make it unique and vivid."""

    try:
        llm = get_llm(purpose="image prompt design")
        from langchain_core.messages import SystemMessage, HumanMessage
        
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        
        result = response.content if hasattr(response, "content") else str(response)
        
        # Clean up LLM response
        result = result.strip().strip('"\'')
        # Remove any "Here is" prefixes
        result = re.sub(r"^(Here'?s?|I'?ve created|Prompt:|Image prompt:)\s*:?\s*", "", result, flags=re.IGNORECASE)
        result = result.strip().strip('"\'')
        
        # Ensure quality suffix
        if "8K" not in result and "8k" not in result:
            result = result.rstrip(".") + ". Ultra realistic, 8K, cinematic lighting."
        
        # Cap length
        if len(result) > 500:
            result = result[:497] + "..."
        
        logger.info("LLM image prompt: %d chars — %s", len(result), result[:80])
        return result
        
    except Exception as e:
        logger.warning("LLM image prompt failed: %s", e)
        return ""


def _template_prompt(
    clean_text: str,
    topic: str,
    topic_data: dict,
    product_name: str | None = None,
) -> str:
    """Fallback: build prompt from templates without LLM."""
    
    parts = [
        "Confident Black woman in sleek futuristic tech attire",
        f"standing in cyberpunk neon-lit cityscape",
        f"interacting with holographic {topic_data['elements'].split(',')[0].strip()}",
        f"{topic_data['mood'].split(',')[0].strip()}",
    ]
    
    if product_name:
        parts.insert(2, f"showcasing {product_name}")
    
    if clean_text and len(clean_text) > 20:
        # Extract key concept from post
        concept = clean_text.split(".")[0][:60]
        parts.insert(1, f"visualizing {concept}")
    
    parts.extend([
        f"neon {topic_data['colors']}",
        "atmospheric fog, volumetric lighting, rain reflections",
        "ultra realistic, 8K, cinematic lighting, photorealistic, no text in image",
    ])
    
    prompt = ", ".join(parts)
    return prompt[:500]
