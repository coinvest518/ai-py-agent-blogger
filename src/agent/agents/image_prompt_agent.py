"""Image Prompt Agent — LLM-powered visual prompt designer for FDWA brand.

Uses the cascading LLM to craft detailed, brand-consistent image prompts
based on the post content, topic, and FDWA's visual identity.

FDWA Visual Identity (post-pivot — product / infographic / dev-focused):
- Digital product mockups (ebook covers, dashboard screenshots, code editors)
- Infographics with charts, flowcharts, agent architecture diagrams
- Marketing flyers for AI tools and skills
- NO humans, NO people, NO faces, NO characters of any kind
- Tech-clean aesthetic: deep dark backgrounds, neon accents, glassmorphism
- Visual elements: terminals, agents-as-nodes diagrams, framework logos placeholder shapes
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

FDWA_VISUAL_DNA = """FDWA VISUAL IDENTITY (DEV / PRODUCT / INFOGRAPHIC):
- Subject: Digital product mockups, infographic compositions, dashboard UIs, code editors, agent architecture diagrams, marketing flyers
- HARD RULE: NO humans, NO people, NO faces, NO characters, NO body parts, NO portraits — products and diagrams ONLY
- Style: Clean tech aesthetic with glassmorphism, depth, glowing accents
- Color palette: Deep dark backgrounds (#0a0a14, #111122) with neon cyan, electric magenta, gold/amber accents
- Common elements: holographic UI panels, terminal windows, flowcharts, node-based agent diagrams, ebook/PDF covers, app screenshots
- Lighting: Cinematic, soft volumetric glow, no harsh shadows
- Composition: Centered product or balanced infographic layout, depth of field
- Style references: Product hunt header art, modern SaaS landing page hero, dev tool marketing assets
- NEVER include readable text, words, or letters in the image (text added separately by overlay)"""


# Topic-specific visual elements — products / infographics / diagrams only
TOPIC_VISUALS = {
    "crypto": {
        "elements": "candlestick chart hologram, agent-as-node diagram showing trading bot loop, dashboard UI mockup with portfolio metrics, Bitcoin/Ethereum coin renders floating, NO traders or people",
        "mood": "data-driven, automated, algorithmic precision",
        "colors": "neon gold, electric green, cyan accents",
    },
    "credit_repair": {
        "elements": "credit score gauge UI mockup, dispute letter PDF cover, dashboard showing before/after score, automated workflow diagram, NO humans",
        "mood": "professional, automated, financial clarity",
        "colors": "emerald green, cyan, white accents",
    },
    "ai_automation": {
        "elements": "agent architecture diagram (nodes connected with glowing lines), terminal showing code, LangGraph-style flowchart, dashboard UI mockup with metrics, framework logo placeholder shapes (LangChain, Composio etc.)",
        "mood": "developer-focused, system-design clarity, technical sophistication",
        "colors": "electric blue, vivid purple, magenta accents",
    },
    "openclaw": {
        "elements": "Claude/OpenClaw skill bundle visualized as 3D card, agent skill marketplace UI mockup, MCP server diagram, code snippet floating in glass panel",
        "mood": "developer tool launch, premium product mockup",
        "colors": "deep navy, cyan, magenta highlights",
    },
    "ai_agent_dev": {
        "elements": "tutorial cover for 'build your first AI agent', step-by-step infographic with numbered nodes, framework comparison chart, beginner-friendly dashboard mockup",
        "mood": "approachable, educational, builder-focused",
        "colors": "purple, cyan, soft white accents",
    },
    "general": {
        "elements": "digital product showcase, ebook covers stacked, dashboard UI hero shot, agent flow diagram, marketing flyer composition",
        "mood": "premium SaaS launch, product hunt hero",
        "colors": "balanced cyan, magenta, gold",
    },
}

# Product-specific visual overlays — all object/diagram, no humans
PRODUCT_VISUALS = {
    "credit repair": "AI credit analyzer dashboard mockup, dispute letter PDF cover with FDWA branding placeholder, score-gauge widget — NO faces",
    "ebook": "3D ebook cover render with subtle shadow, pages slightly fanned, glowing edge — product shot only",
    "course": "course curriculum infographic, module flowchart, certification badge render — no instructors visible",
    "ai tool": "agent architecture node diagram, terminal UI screenshot, framework integration map",
    "consulting": "service tier comparison infographic, calendar booking UI mockup, deliverables checklist visual — no people",
    "yieldbot": "trading bot dashboard UI mockup, automated yield-farming flowchart, token analytics widget",
    "openclaw": "Claude-themed skill card, MCP server diagram, code-block hero shot in glass panel",
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
    research_summary: str | None = None,
) -> str:
    """Generate a detailed, brand-consistent image prompt using the LLM.

    Args:
        post_text: Refined caption the image must visualize (not the raw tweet).
        topic: Content topic ('crypto', 'credit_repair', 'ai_automation', 'general').
        product_name: Optional product name for selling-focused images.
        product_price: Optional price.
        platform: Target platform (composition hint).
        use_llm: If True, LLM-first. Template is last-resort.
        research_summary: Optional trend/research snippet so the image reflects what
            the caption is actually about, not just generic brand DNA.
    """
    if not topic:
        topic = detect_topic(post_text)

    topic_data = TOPIC_VISUALS.get(topic, TOPIC_VISUALS["general"])

    clean_text = re.sub(r"#\w+", "", post_text)
    clean_text = re.sub(r"https?://\S+", "", clean_text)
    clean_text = re.sub(r"[@*_\[\]{}()\\'\"\\\\]", "", clean_text)
    clean_text = " ".join(clean_text.split())[:220]

    research_ctx = ""
    if research_summary:
        rs = " ".join(str(research_summary).split())[:300]
        research_ctx = f"\nRESEARCH / TREND CONTEXT: {rs}"

    product_context = ""
    if product_name:
        for key, visual in PRODUCT_VISUALS.items():
            if key in product_name.lower():
                product_context = f"\nProduct focus: {product_name}"
                if product_price:
                    product_context += f" (${product_price})"
                product_context += f"\nProduct visual elements: {visual}"
                break
        if not product_context:
            product_context = f"\nProduct focus: {product_name}"
            if product_price:
                product_context += f" (${product_price})"

    recent = _get_recent_image_styles()

    if use_llm:
        prompt = _llm_generate_prompt(
            clean_text, topic, topic_data, product_context, platform, recent, research_ctx
        )
        if prompt and len(prompt) > 50:
            return prompt
        logger.warning("LLM prompt generation failed, using template fallback")

    return _template_prompt(clean_text, topic, topic_data, product_name)


def generate_caption_image_prompt(
    refined_caption: str,
    research_data: str | None = None,
    product_name: str | None = None,
    product_price: str | None = None,
    topic: str | None = None,
    platform: str = "general",
) -> str:
    """Shortcut for the graph: build an image prompt from the REFINED caption
    (post_refine_content) + research_data + product. LLM-first, falls back to
    template. Used by generate_image_node.
    """
    return generate_image_prompt(
        post_text=refined_caption or "",
        topic=topic,
        product_name=product_name,
        product_price=product_price,
        platform=platform,
        use_llm=True,
        research_summary=research_data,
    )


def _llm_generate_prompt(
    clean_text: str,
    topic: str,
    topic_data: dict,
    product_context: str,
    platform: str,
    recent_context: str,
    research_ctx: str = "",
) -> str:
    """Use the cascading LLM to craft a product/infographic image prompt derived
    from the finalized caption + research. No humans — subject is product/diagram."""

    composition_hint = {
        "instagram": "Square 1:1 composition, centered product/diagram subject, high visual impact",
        "blog": "Wide 16:9 composition, editorial hero-shot framing",
        "twitter": "Wide composition, bold visual, high contrast for small thumbnails",
        "general": "Versatile composition, works at any aspect ratio",
    }.get(platform, "Versatile composition")

    system_prompt = f"""You are FDWA's visual creative director. You write image generation prompts
that match the FDWA product/infographic brand aesthetic — NO humans, NO faces, NO characters.

{FDWA_VISUAL_DNA}

TOPIC: {topic}
TOPIC ELEMENTS: {topic_data['elements']}
MOOD: {topic_data['mood']}
COLORS: {topic_data['colors']}
{product_context}

COMPOSITION: {composition_hint}
{f'CONTINUITY: {recent_context}' if recent_context else ''}

RULES FOR YOUR PROMPT:
1. Output ONLY the image generation prompt — no explanation, no quotes.
2. 300-500 characters.
3. The subject MUST be a product mockup, infographic, dashboard UI, code editor, agent diagram, or marketing flyer. Never a person.
4. Let the REFINED CAPTION and RESEARCH CONTEXT drive the concept — pick visual metaphors that illustrate the specific idea in the caption, not a generic brand shot.
5. Incorporate the topic-specific visual elements naturally.
6. Specify lighting, atmosphere, and camera angle.
7. End with quality keywords: ultra realistic, 8K, cinematic lighting.
8. NEVER include readable text, words, watermarks, or logos (text-free composition).
9. Each prompt should feel unique to the caption while staying on-brand."""

    user_prompt = f"""Create an image prompt that visualizes this refined social caption:

"{clean_text}"
{research_ctx}

Translate the caption's specific idea into a product mockup, dashboard, or infographic scene.
Colors: {topic_data['colors']}. No people, no faces, no characters."""

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
