"""FDWA Autonomous Twitter AI Agent.

This graph defines a three-step autonomous process:
1. Research trending topics using SERPAPI (primary) with Tavily fallback
2. Generate strategic FDWA-branded tweet using Google AI
3. Post the tweet to Twitter using Composio
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from composio import Composio
from dotenv import load_dotenv
from langgraph.graph import StateGraph
from langsmith import traceable
from langsmith.integrations.otel import configure
from typing_extensions import TypedDict

from src.agent import telegram_agent
from src.agent.blog_email_agent import generate_and_send_blog
from src.agent.duplicate_detector import is_duplicate_post, record_post
from src.agent.instagram_agent import convert_to_instagram_caption
from src.agent.instagram_comment_agent import generate_instagram_reply
from src.agent.linkedin_agent import convert_to_linkedin_post
from src.agent.llm_provider import get_llm
from src.agent.ai_decision_engine import get_decision_engine  # ✅ NEW: AI Brain
# Optional CoinMarketCap helper for Telegram crypto market data
try:
    from src.agent.cmc_client import get_top_gainers
except Exception:
    # optional integration — continue without CoinMarketCap if not configured
    def get_top_gainers(limit: int = 5):
        return []

from src.agent.realtime_status import broadcaster

# Load environment variables from .env file
load_dotenv()

# Configure LangSmith OpenTelemetry integration
configure(project_name=os.getenv("LANGSMITH_PROJECT", "fdwa-multi-agent"))

# Initialize Composio client with env entity_id
composio_client = Composio(
    api_key=os.getenv("COMPOSIO_API_KEY"),
    entity_id=os.getenv("TWITTER_ENTITY_ID")
)

# Configure logging
logger = logging.getLogger(__name__)

# Helper function to call async broadcaster from sync code
def _broadcast_sync(method_name: str, *args, **kwargs):
    """Call async broadcaster method from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new task in the running loop
            asyncio.create_task(getattr(broadcaster, method_name)(*args, **kwargs))
        else:
            # Run in a new event loop  
            asyncio.run(getattr(broadcaster, method_name)(*args, **kwargs))
    except Exception as e:
        logger.debug(f"Broadcast error (non-critical): {e}")

class AgentState(TypedDict):
    """Represents the state of our autonomous agent.

    Attributes:
        trend_data: Raw trend data from SERPAPI or Tavily search.
        insight: Extracted insight aligned with FDWA brand.
        tweet_text: The generated tweet text (Twitter-specific, 280 chars).
        facebook_text: Facebook-specific post (longer, conversational).
        linkedin_text: The LinkedIn post text (professional).
        instagram_caption: Instagram-specific caption (visual, emojis).
        telegram_message: Telegram-specific message (direct, action).
        image_url: The URL of the generated image.
        image_path: The local path of the generated image.
        twitter_url: The URL of the created Twitter post.
        facebook_status: The status of the Facebook post.
        facebook_post_id: The ID of the Facebook post.
        linkedin_status: The status of the LinkedIn post.
        comment_status: The status of the Facebook comment.
        error: To capture any errors that might occur.
    """
    trend_data: str
    insight: str
    tweet_text: str
    facebook_text: str
    linkedin_text: str
    instagram_caption: str
    telegram_message: str
    image_url: str
    image_path: str
    twitter_url: str
    twitter_post_id: str
    twitter_reply_status: str
    facebook_status: str
    facebook_post_id: str
    linkedin_status: str
    instagram_status: str
    instagram_post_id: str
    instagram_comment_status: str
    comment_status: str
    blog_status: str
    blog_title: str
    telegram_status: str
    error: str


def _download_image_from_url(image_url: str) -> str:
    """Download image from URL and save locally.
    
    Args:
        image_url: URL of the image to download (https://) or local file path (file://).
        
    Returns:
        Local file path of downloaded image.
    """
    try:
        # Handle local file:// URIs (from Hugging Face local generation)
        if image_url.startswith("file:///"):
            local_path = image_url.replace("file:///", "").replace("/", chr(92))
            if os.path.exists(local_path):
                logger.info("Using local file: %s", local_path)
                return local_path
            else:
                logger.error("Local file not found: %s", local_path)
                return None
        
        # Download from remote URL
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        # Create temp directory if it doesn't exist
        temp_dir = Path("temp_images")
        temp_dir.mkdir(exist_ok=True)
        
        # Extract filename from URL or generate one
        filename = image_url.split("/")[-1] or "image.jpg"
        if not filename.endswith((".jpg", ".jpeg", ".png")):
            filename += ".jpg"
        
        local_path = temp_dir / filename
        local_path.write_bytes(response.content)
        
        logger.info("Downloaded image to: %s", local_path)
        return str(local_path)
    except Exception as e:
        logger.exception("Failed to download image: %s", e)
        return None


@traceable(name="enhance_image_prompt")
def _enhance_prompt_for_image(text: str, ai_strategy: dict = None) -> str:
    """Convert social media text into FDWA-branded visual prompt for image generation.
    
    ✅ NEW: Uses AI Decision Engine strategy to create topic-appropriate images.

    Args:
        text: Social media post text with hashtags and formatting.
        ai_strategy: Optional AI strategy dict with topic and products info

    Returns:
        FDWA-branded image prompt optimized for Hugging Face FLUX model.
    """
    logger.info("Enhancing image prompt with FDWA branding...")

    # Clean up text: remove hashtags, @ mentions, URLs, special chars
    clean_text = re.sub(r"#\w+", "", text)  # Remove hashtags
    clean_text = re.sub(r"@\w+", "", clean_text)  # Remove mentions
    clean_text = re.sub(r"https?://\S+", "", clean_text)  # Remove URLs
    clean_text = re.sub(r"[*#@\[\]{}()\'\"\\]", "", clean_text)  # Remove special chars
    clean_text = re.sub(r"\s+", " ", clean_text).strip()  # Normalize whitespace
    
    # Truncate to reasonable length (120 chars)
    clean_text = clean_text[:120]
    
    # Determine visual style based on AI strategy topic
    topic = ai_strategy.get("topic", "business") if ai_strategy else "business"
    topic_lower = topic.lower()
    
    # Topic-specific visual elements
    if "ai" in topic_lower or "automation" in topic_lower:
        style = (
            "futuristic AI automation workspace, holographic interfaces, "
            "neural network visualizations, robotic assistants, glowing blue/purple tech, "
            "modern minimalist office, professional business setting"
        )
    elif "credit" in topic_lower or "financial" in topic_lower or "debt" in topic_lower:
        style = (
            "professional financial growth concept, credit score dashboard rising, "
            "banking documents organized, calculator and charts, green upward graphs, "
            "clean modern business office, wealth building imagery"
        )
    elif "real estate" in topic_lower or "property" in topic_lower:
        style = (
            "modern real estate investment concept, aerial city view with buildings, "
            "property blueprints with digital overlays, keys and contracts, "
            "professional real estate office, clean architecture photography"
        )
    elif "crypto" in topic_lower or "bitcoin" in topic_lower:
        style = (
            "cryptocurrency trading dashboard, Bitcoin and Ethereum symbols, "
            "candlestick charts rising, digital blockchain visualization, "
            "futuristic finance concept, neon blue/gold accents on dark background"
        )
    else:
        # Default business/entrepreneurship style
        style = (
            "modern successful entrepreneur workspace, professional business growth, "
            "laptop with analytics dashboard, clean minimalist office design, "
            "urban skyline through windows, motivational business imagery"
        )
    
    # Add product visual elements if products are featured
    product_hint = ""
    if ai_strategy and ai_strategy.get("products"):
        products = ai_strategy.get("products", [])
        # Subtle product hints in visual
        product_hint = ", course materials visible, digital product showcase"
    
    # Create structured prompt for FLUX
    visual_prompt = (
        f"Professional high-quality photograph: {clean_text}. "
        f"{style}{product_hint}. "
        "Cinematic lighting, ultra realistic, 8K quality, sharp focus, "
        "proper composition, professional color grading, inspirational mood, "
        "no text or words in image, photorealistic style"
    )
    
    logger.info("Generated FDWA-branded visual prompt for '%s': %s...", topic, visual_prompt[:80])
    return visual_prompt


def _extract_search_insights(search_data: dict) -> str:
    """Extract clean, readable text from SERPAPI/Tavily search results.
    
    Converts raw API response dict into human-readable insights for content generation.
    Handles nested response structures from Composio.
    
    Args:
        search_data: Raw search API response dict (may be nested)
        
    Returns:
        Clean text summary of search results
    """
    insights = []
    
    # SERPAPI format: Check for nested structure first
    # Option 1: data.results.organic_results (Composio nested)
    # Option 2: data.organic_results (direct)
    organic_results = None
    
    if "results" in search_data and isinstance(search_data["results"], dict):
        # Nested format: search_data.results.organic_results
        nested_results = search_data.get("results", {})
        organic_results = nested_results.get("organic_results", [])
    elif "organic_results" in search_data:
        # Direct format: search_data.organic_results
        organic_results = search_data.get("organic_results", [])
    
    if organic_results and isinstance(organic_results, list):
        for result in organic_results[:5]:  # Top 5 results
            if isinstance(result, dict):
                title = result.get("title", "")
                snippet = result.get("snippet", "")
                if title:
                    insights.append(f"{title}")
                if snippet and snippet != title:
                    insights.append(f"{snippet}")
    
    # Tavily format: Check for nested structure first
    # Option 1: data.response_data.results (Composio nested)
    # Option 2: data.results (direct)
    tavily_results = None
    tavily_answer = None
    
    if "response_data" in search_data and isinstance(search_data["response_data"], dict):
        # Nested format: search_data.response_data.results
        response_data = search_data.get("response_data", {})
        tavily_results = response_data.get("results", [])
        tavily_answer = response_data.get("answer", "")
    elif "results" in search_data and isinstance(search_data["results"], list):
        # Direct format: search_data.results
        tavily_results = search_data.get("results", [])
        tavily_answer = search_data.get("answer", "")
    
    if tavily_results and isinstance(tavily_results, list):
        for result in tavily_results[:5]:  # Top 5 results
            if isinstance(result, dict):
                title = result.get("title", "")
                content = result.get("content", "")
                if title:
                    insights.append(f"{title}")
                if content and content != title:
                    # Take first 200 chars of content
                    insights.append(f"{content[:200]}")
    
    # Handle answer field (Tavily)
    if tavily_answer:
        insights.insert(0, tavily_answer)
    
    # Join with newlines and limit total length
    text = "\n".join(insights)
    return text[:800] if text else "No results found"


# ==================== MARKDOWN CLEANING UTILITY ====================

def _strip_markdown(text: str) -> str:
    """Remove Markdown formatting from text for social media posts.
    
    Social media platforms don't render Markdown, so we need plain text.
    Converts:
    - **bold** → bold
    - *italic* → italic
    - [text](url) → text (url)
    - ### Headers → Headers
    - `code` → code
    
    Args:
        text: Text potentially containing Markdown syntax
        
    Returns:
        Plain text without Markdown formatting
    """
    import re
    
    # Remove bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    
    # Remove italic: *text* or _text_ (but not URLs or email)
    text = re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'\1', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)
    
    # Convert links: [text](url) → text (url) or just text if URL is mentioned
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', lambda m: f"{m.group(1)} ({m.group(2)})" if m.group(1).lower() not in m.group(2).lower() else m.group(1), text)
    
    # Remove headers: ### text → text
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Remove code blocks: `code` → code
    text = re.sub(r'`(.+?)`', r'\1', text)
    
    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)
    
    # Clean up multiple spaces/newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    
    return text.strip()


# ==================== PLATFORM-SPECIFIC CONTENT ADAPTERS ====================

def _adapt_for_twitter(base_insights: str) -> str:
    """Adapt content for Twitter: Short, hashtag-heavy, engaging (280 chars max).
    
    Args:
        base_insights: Research insights from trend data
        
    Returns:
        Twitter-optimized content (280 chars)
    """
    # Get current year for context
    from datetime import datetime
    current_year = datetime.now().year
    
    # Try LLM-first approach with template fallback
    try:
        llm = get_llm(purpose="Twitter content adaptation")
        
        prompt = f"""Current year: {current_year}. Create a Twitter post (MAX 280 characters) based on this insight:

{base_insights[:300]}

Requirements:
- MUST be under 280 characters total
- Plain text only (NO Markdown formatting like **bold** or *italic*)
- Use {current_year} for any year references (NOT 2025 or older years)
- Include relevant emojis
- Mention FDWA AI automation: https://fdwa.site
- Add hashtags: #YBOT #AIAutomation
- Be engaging and actionable

Output ONLY the tweet text, nothing else."""

        response = llm.invoke(prompt)
        tweet = response.content if hasattr(response, 'content') else str(response)
        tweet = _strip_markdown(tweet.strip())  # Remove Markdown formatting
        
        # Ensure under 280 characters
        if len(tweet) > 280:
            tweet = tweet[:277] + "..."

        # Ensure our primary site / CTA is always present (post-process)
        primary_site = os.getenv("PRIMARY_SITE", "https://fdwa.site")
        try:
            if primary_site and "fdwa.site" not in tweet.lower():
                suffix = " " + primary_site
                if len(tweet) + len(suffix) <= 280:
                    tweet = tweet + suffix
                else:
                    allowed = 280 - len(suffix) - 3
                    tweet = tweet[:allowed].rstrip() + "..." + suffix
        except Exception:
            # non-critical if post-processing fails
            pass

        logger.info("Generated Twitter content with LLM (%d chars)", len(tweet))
        return tweet
        
    except Exception as e:
        logger.warning("LLM generation failed for Twitter, using template: %s", e)
        
        # Template fallback
        first_line = base_insights.split('\n')[0][:100]
        tweet = (
            f"🚀 {first_line}\n\n"
            f"Get AI automation tools at https://fdwa.site ✨\n\n"
            f"#YBOT #AIAutomation #CreditRepair #FinancialFreedom"
        )
        
        if len(tweet) > 280:
            tweet = tweet[:277] + "..."
        
        return tweet


def _adapt_for_facebook(base_insights: str) -> str:
    """Adapt content for Facebook: Longer, conversational, community-focused.
    
    Args:
        base_insights: Research insights from trend data
        
    Returns:
        Facebook-optimized content (500+ chars)
    """
    # Try LLM-first approach with template fallback
    try:
        llm = get_llm(purpose="Facebook content adaptation")
        
        prompt = f"""Create a Facebook post based on this insight:

{base_insights[:500]}

Requirements:
- Conversational and community-focused tone
- 400-600 characters
- Plain text only (NO Markdown formatting: no **bold**, *italic*, or ### headers)
- Include relevant emojis
- Mention FDWA services: AI automation, credit repair, digital products
- Include call-to-action: https://fdwa.site
- Add hashtags: #AIAutomation #BusinessGrowth #FinancialFreedom
- Be engaging and value-driven

Output ONLY the Facebook post text, nothing else."""

        response = llm.invoke(prompt)
        post = response.content if hasattr(response, 'content') else str(response)
        post = _strip_markdown(post.strip())  # Remove Markdown formatting
        
        logger.info("Generated Facebook content with LLM (%d chars)", len(post))
        return post
        
    except Exception as e:
        logger.warning("LLM generation failed for Facebook, using template: %s", e)
        
        # Template fallback
        first_line = base_insights.split('\n')[0][:150]
        post = (
            f"💡 {first_line}\n\n"
            f"The future of business is here, and it's powered by AI automation. "
            f"Whether you're building credit, scaling your business, or creating passive income streams, "
            f"the right tools make all the difference.\n\n"
            f"🎯 What we're focused on:\n"
            f"• AI automation for business workflows\n"
            f"• Credit repair strategies that actually work\n"
            f"• Digital products and passive income\n"
            f"• Financial empowerment through technology\n\n"
            f"Ready to transform your business? Visit https://fdwa.site to learn more.\n\n"
            f"#AIAutomation #BusinessGrowth #FinancialFreedom #CreditRepair #FDWA"
        )
        
        return post


def _adapt_for_linkedin(base_insights: str) -> str:
    """Adapt content for LinkedIn: Professional, business-focused, value-driven.
    
    Args:
        base_insights: Research insights from trend data
        
    Returns:
        LinkedIn-optimized content (professional tone)
    """
    # Try LLM-first approach with template fallback
    try:
        llm = get_llm(purpose="LinkedIn content adaptation")
        
        prompt = f"""Create a LinkedIn post based on this insight:

{base_insights[:500]}

Requirements:
- Professional, business-focused tone
- 500-700 characters
- Data-driven language (metrics, percentages)
- Focus on business transformation and ROI
- Mention FDWA: AI automation, financial optimization, digital products
- Include call-to-action: https://fdwa.site
- Add hashtags: #BusinessTransformation #AI #Automation #FinancialStrategy
- Be authoritative and value-driven

Output ONLY the LinkedIn post text, nothing else."""

        response = llm.invoke(prompt)
        post = response.content if hasattr(response, 'content') else str(response)
        post = _strip_markdown(post.strip())  # Remove Markdown formatting
        
        logger.info("Generated LinkedIn content with LLM (%d chars)", len(post))
        return post
        
    except Exception as e:
        logger.warning("LLM generation failed for LinkedIn, using template: %s", e)
        
        # Template fallback
        first_line = base_insights.split('\n')[0][:120]
        post = (
            f"📊 {first_line}\n\n"
            f"In today's rapidly evolving business landscape, organizations that embrace AI automation "
            f"and data-driven strategies are achieving 3-5x better operational efficiency.\n\n"
            f"Key areas driving business transformation:\n\n"
            f"🤖 AI Automation - Streamlining workflows and reducing operational costs\n"
            f"📈 Financial Optimization - Strategic credit management and wealth building\n"
            f"💼 Digital Product Development - Creating scalable revenue streams\n"
            f"🎯 Process Automation - Eliminating manual tasks and human error\n\n"
            f"At FDWA, we help businesses implement these strategies through custom AI solutions "
            f"and proven financial frameworks.\n\n"
            f"Interested in learning more? Connect with us at https://fdwa.site\n\n"
            f"#BusinessTransformation #AI #Automation #FinancialStrategy #DigitalInnovation"
        )
        
        return post


def _adapt_for_telegram(base_insights: str) -> str:
    """Adapt content for Telegram: Crypto/DeFi focused with market data.
    
    This creates crypto-specific content for Telegram group members
    interested in DeFi, tokens, and cryptocurrency trends.
    
    Uses LLM-first approach with intelligent template fallback.
    
    Args:
        base_insights: Research insights from trend data
        
    Returns:
        Telegram crypto-optimized content
    """
    # Get current year for context
    from datetime import datetime
    current_year = datetime.now().year
    
    # Try LLM-first approach (RECOMMENDED for quality)
    llm_failed = False
    try:
        llm = get_llm(purpose="Telegram content adaptation")
        
        if not llm:
            logger.warning("No LLM provider available for Telegram, using template")
            llm_failed = True
        else:
            prompt = f"""Current year: {current_year}. Create a Telegram message for a crypto/DeFi community based on this insight:

{base_insights[:800]}

Requirements:
- Start with topic-relevant hook (AI/automation OR crypto/DeFi OR credit/business - match the insight)
- 400-800 characters (detailed but readable)
- Plain text only (NO Markdown: no **bold**, *italic*, or [links](url) syntax)
- Use {current_year} for any year references (NOT 2025)
- Include specific data, tools, or strategies from the insights
- Add relevant emojis (🚀 📊 💰 📈 🤖)
- Mention FDWA tools/products if relevant: https://fdwa.site
- Add consultation link: https://cal.com/bookme-daniel
- End with relevant hashtags (#AI #DeFi #Crypto #Automation #YieldBot)
- Be actionable and valuable

Output ONLY the Telegram message text, nothing else."""

            response = llm.invoke(prompt)
            message = response.content if hasattr(response, 'content') else str(response)
            message = _strip_markdown(message.strip())  # Remove Markdown formatting
            
            # Validation: Ensure message is substantial (not just template)
            if len(message) < 150 or "Key opportunities:" in message:
                logger.warning("LLM generated low-quality content, using template fallback")
                llm_failed = True
            else:
                logger.info("✅ Generated Telegram content with LLM (%d chars)", len(message))
                return message
        
    except Exception as e:
        logger.warning("LLM generation failed for Telegram: %s - using intelligent template", str(e)[:100])
        llm_failed = True
    
    # Template fallback (only if LLM failed or unavailable)
    if llm_failed:
        logger.info("Using template-based Telegram content generation")
        
        # Extract crypto tokens from insights
        crypto_keywords = ["BTC", "ETH", "SOL", "MATIC", "AVAX", "DOT", "LINK", "UNI", 
                           "AAVE", "CRV", "bitcoin", "ethereum", "defi", "crypto", "token",
                           "blockchain", "web3", "nft", "dao"]
        
        found_tokens = []
        insights_lower = base_insights.lower()
        
        for keyword in crypto_keywords:
            if keyword.lower() in insights_lower:
                found_tokens.append(keyword.upper() if len(keyword) <= 5 else keyword.title())
        
        # Remove duplicates and limit
        found_tokens = list(dict.fromkeys(found_tokens))[:5]
        
        # Get first line for context
        first_line = base_insights.split('\n')[0][:100]
        
        # Build crypto-focused Telegram message
        if found_tokens:
            tokens_list = " | ".join(found_tokens)
            message = (
                f"🚀 DeFi Market Update\n\n"
                f"📊 Trending: {tokens_list}\n\n"
                f"📈 {first_line}\n\n"
                f"💡 Stay ahead with real-time DeFi insights and AI-powered automation.\n"
                f"Get YBOT tools at https://fdwa.site\n\n"
                f"#DeFi #Crypto #YieldBot #FinancialFreedom"
            )
        else:
            # Intelligent fallback: Extract key content instead of generic template
            # Get more context from base_insights (not just title)
            lines = [l.strip() for l in base_insights.split('\n') if l.strip()]
            
            # Build message from actual content
            topic = lines[0][:100] if lines else "Market Update"
            
            # Extract 2-3 key points from insights
            key_points = []
            for line in lines[1:6]:  # Check next 5 lines
                if len(line) > 20 and not line.startswith('http'):  # Skip links
                    key_points.append(f"→ {line[:80]}")
                    if len(key_points) >= 3:
                        break
            
            # If no key points found, use content-aware defaults based on topic
            if not key_points:
                topic_lower = topic.lower()
                if 'ai' in topic_lower or 'automation' in topic_lower:
                    key_points = [
                        "→ AI workflow automation tools",
                        "→ No-code AI agent builders", 
                        "→ Productivity & cost savings"
                    ]
                elif 'credit' in topic_lower or 'debt' in topic_lower:
                    key_points = [
                        "→ Automated credit dispute letters",
                        "→ AI-powered credit analysis",
                        "→ 72-hour credit optimization"
                    ]
                else:
                    key_points = [
                        "→ Digital business automation",
                        "→ Revenue growth strategies",
                        "→ AI-powered marketing systems"
                    ]
            
            message = (
                f"🚀 {topic}\n\n"  # Removed ** markdown
                f"💡 Key insights:\n"
                + "\n".join(key_points) + "\n\n"
                f"🤖 Automate with FDWA tools: https://fdwa.site\n"
                f"📅 Free consultation: https://cal.com/bookme-daniel\n\n"
                f"#Automation #AI #Business #YieldBot"
            )
            
            # Strip Markdown from template fallback too (in case any remains)
            message = _strip_markdown(message)
            message = _strip_markdown(message)
            
            logger.warning("Using intelligent template fallback for Telegram (no crypto tokens found)")
        
        return message


def _adapt_for_instagram(base_insights: str) -> str:
    """Adapt content for Instagram: Visual-first, emoji-heavy, lifestyle-focused.
    
    Args:
        base_insights: Research insights from trend data
        
    Returns:
        Instagram-optimized caption (visual, engaging)
    """
    # Get current year for context
    from datetime import datetime
    current_year = datetime.now().year
    
    # Try LLM-first approach with template fallback
    try:
        llm = get_llm(purpose="Instagram content adaptation")
        
        prompt = f"""Current year: {current_year}. Create an Instagram caption based on this insight:

{base_insights[:400]}

Requirements:
- Visual-first, lifestyle-focused tone
- 400-600 characters
- Plain text only (NO Markdown formatting)
- Use {current_year} for any year references (NOT 2025)
- Emoji-heavy (but tasteful)
- Focus on entrepreneurship, financial freedom, AI automation
- Mention FDWA services: AI systems, credit repair, digital products
- Include call-to-action: fdwa.site
- Add hashtags: #AIAutomation #FinancialFreedom #Entrepreneur #PassiveIncome
- Be inspiring and aspirational

Output ONLY the Instagram caption text, nothing else."""

        response = llm.invoke(prompt)
        caption = response.content if hasattr(response, 'content') else str(response)
        caption = _strip_markdown(caption.strip())  # Remove Markdown formatting
        
        logger.info("Generated Instagram content with LLM (%d chars)", len(caption))
        return caption
        
    except Exception as e:
        logger.warning("LLM generation failed for Instagram, using template: %s", e)
        
        # Template fallback
        first_line = base_insights.split('\n')[0][:80]
        caption = (
            f"✨ {first_line}\n\n"
            f"🤖 AI automation isn't just for tech companies anymore\n"
            f"💎 It's for entrepreneurs who want freedom\n"
            f"🚀 It's for businesses ready to scale\n"
            f"💰 It's for anyone building their financial future\n\n"
            f"We help you:\n"
            f"→ Build AI systems that work 24/7\n"
            f"→ Fix your credit strategically\n"
            f"→ Create digital products that sell\n"
            f"→ Automate everything\n\n"
            f"🔗 Learn more: fdwa.site\n\n"
            f"#AIAutomation #FinancialFreedom #Entrepreneur #PassiveIncome #CreditRepair "
            f"#DigitalProducts #BusinessGrowth #YBOT #FutureOfWork #Automation"
        )
        
        return caption


def research_trends_node(state: AgentState) -> dict:
    """Research trending topics using SERPAPI with Tavily fallback.

    Args:
        state: Current agent state.

    Returns:
        Dictionary with trend_data or error.
    """
    logger.info("---RESEARCHING TRENDS---")
    _broadcast_sync("start_step", "research", "Researching trending topics and market insights")
    _broadcast_sync("update", "Analyzing current trends in credit repair, AI automation, and digital products...")

    # Get current year for search queries
    from datetime import datetime
    current_year = datetime.now().year

    # Diverse search queries for different business topics (use current year)
    search_queries = [
        f"credit repair tips {current_year}",
        "AI automation for credit repair",
        "digital products for financial freedom",
        "AI dispute letter generators",
        "passive income with ebooks",
        "credit score improvement hacks",
        "AI tools for business automation",
        "how to sell digital products online",
        "financial empowerment strategies",
        f"credit repair laws and updates {current_year}",
        "AI credit report analyzers",
        "building wealth with digital tools",
        "credit denial solutions",
        "automate business workflows with AI",
        "create and sell step-by-step guides",
        "financial education for entrepreneurs",
        "credit repair digital products",
        "AI for passive income streams",
        f"modern wealth building techniques {current_year}",
        "credit repair automation tools",
    ]

    query = random.choice(search_queries)
    logger.info("Researching: %s", query)

    trend_data = ""
    today = datetime.now().strftime("%Y-%m-%d")
    cache_file = "trend_cache.json"

    try:
        # Primary: Try SERPAPI search first
        logger.info("Fetching search results with SERPAPI...")
        try:
            search_response = composio_client.tools.execute(
                "SERPAPI_SEARCH",
                {"query": query},
                connected_account_id=os.getenv("SERPAPI_ACCOUNT_ID")
            )
            # Remove error text if present
            data = search_response.get('data', {})
            if isinstance(data, dict) and any(
                k in str(data).lower() for k in ["account out of searches", "error", "limit"]):
                raise Exception("SERPAPI out of searches or error")
            
            # Extract clean text from search results instead of raw dict
            trend_data = _extract_search_insights(data)
            if not trend_data or len(trend_data) < 20:
                raise Exception("No useful data extracted from SERPAPI")
                
            logger.info("SERPAPI search successful: %d characters", len(trend_data))
            _broadcast_sync("complete_step", "research", {"source": "SERPAPI", "data_length": len(trend_data)})
            return {"trend_data": trend_data}
        except Exception as serpapi_error:
            logger.warning("SERPAPI search failed: %s", serpapi_error)
            # Fallback: Try Tavily search, but only once per day
            logger.info("Falling back to Tavily search...")
            # Check cache
            if os.path.exists(cache_file):
                with open(cache_file, encoding="utf-8") as f:
                    cache = json.load(f)
                if cache.get("date") == today and cache.get("trend_data"):
                    logger.info("Using cached Tavily trend data for today.")
                    _broadcast_sync("complete_step", "research", {"source": "Tavily (cached)"})
                    return {"trend_data": cache["trend_data"]}
            # Not cached, do Tavily search
            search_response = composio_client.tools.execute(
                "TAVILY_SEARCH",
                {
                    "query": query,
                    "max_results": 10,
                    "search_depth": "advanced",
                    "include_answer": True,
                    "include_raw_content": True,
                    "exclude_domains": [
                        "pinterest.com",
                        "facebook.com", 
                        "instagram.com",
                        "twitter.com",
                        "tiktok.com"
                    ]
                },
                connected_account_id=os.getenv("TAVILY_ACCOUNT_ID")
            )
            
            # Extract clean text from Tavily results
            search_data = search_response.get('data', {})
            trend_data = _extract_search_insights(search_data)
            if not trend_data or len(trend_data) < 20:
                raise Exception("No useful data extracted from Tavily")
            
            # Save to cache
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"date": today, "trend_data": trend_data}, f)
            logger.info("Tavily fallback successful: %d characters", len(trend_data))
            _broadcast_sync("complete_step", "research", {"source": "Tavily", "data_length": len(trend_data)})
            return {"trend_data": trend_data}
    except Exception as e:
        logger.exception("Both search methods failed: %s", e)
        _broadcast_sync("error", f"Research failed: {str(e)}")
        return {"error": str(e), "trend_data": "No trend data available"}


def generate_tweet_node(state: AgentState) -> dict:
    """Generate platform-specific content for ALL social media platforms using AI DECISION ENGINE.
    
    ✅ NEW: Consults ALL data sources via AI Decision Engine:
    - Google Sheets (recent posts, engagement)
    - Products Catalog (150+ products)
    - Knowledge Base (writing guidelines)
    - Business Profile (offerings, CTAs)
    - Memory (past performance)
    
    Uses base research insights to create tailored content for:
    - Twitter: Short, hashtag-heavy (280 chars)
    - Facebook: Longer, conversational
    - LinkedIn: Professional, business-focused
    - Instagram: Visual, emoji-heavy
    - Telegram: Direct, action-oriented

    Args:
        state: Current agent state with trend_data.

    Returns:
        Dictionary with platform-specific content for all channels.
    """
    logger.info("---GENERATING PLATFORM-SPECIFIC CONTENT WITH AI DECISION ENGINE---")
    _broadcast_sync("start_step", "generate_content", "🧠 Consulting AI Decision Engine...")
    _broadcast_sync("update", "Analyzing Google Sheets, products catalog, memory...")

    trend_data = state.get("trend_data", "")
    # Remove any error or search system text from trend_data
    for bad in ["SERPAPI_SEARCH:", "TAVILY_SEARCH:", "Account out of searches", "error", "limit"]:
        if bad.lower() in trend_data.lower():
            trend_data = ""
            break

    # Use trend data as base insights, or fallback
    if trend_data and len(trend_data) > 20:
        base_insights = trend_data
    else:
        # Fallback when no trend data
        base_insights = (
            "AI automation is transforming business operations in 2026. "
            "Smart entrepreneurs are using AI agents to scale their businesses, "
            "automate customer service, and build passive income streams. "
            "Financial empowerment through technology is now accessible to everyone."
        )

    # ========== ✅ NEW: AI DECISION ENGINE INTEGRATION ==========
    try:
        decision_engine = get_decision_engine()
        strategy = decision_engine.get_content_strategy(trend_data=base_insights)
        
        logger.info("🧠 AI STRATEGY:")
        logger.info("   Topic: %s", strategy["topic"])
        logger.info("   Products: %s", [p["name"][:40] for p in strategy.get("products", [])])
        logger.info("   CTA: %s", strategy["cta"][:60])
        logger.info("   Memory: %s", strategy.get("memory_insights", "None"))
        
        # Broadcast AI thinking process to UI
        _broadcast_sync("update", f"✅ Topic: {strategy['topic']}")
        _broadcast_sync("update", f"✅ Products: {', '.join([p['name'][:30] for p in strategy.get('products', [])])}")
        _broadcast_sync("update", f"✅ Strategy: {strategy.get('memory_insights', 'First time!')[:50]}")
        
        # Enhance base insights with product info
        products = strategy.get("products", [])
        if products:
            product_context = "\n\nFeatured products to mention:\n"
            for product in products[:2]:  # Max 2 products
                product_context += f"- {product['name']} ({product['price']})\n"
            base_insights = base_insights + product_context
            
        # Add CTA to base insights
        base_insights = base_insights + f"\n\nCall-to-action: {strategy['cta']}"
        
        # Store strategy in state for later use
        state["ai_strategy"] = strategy
        
    except Exception as e:
        logger.warning("⚠️ AI Decision Engine failed, using standard approach: %s", e)
        strategy = None
    # ========== END AI DECISION ENGINE ==========

    # --- Append short FDWA context so LLMs reference our profile + recent posts ---
    try:
        from src.agent.blog_email_agent import _load_business_profile, _get_recent_posts_for_prompt
        bp = _load_business_profile() or {}
        kb_about = bp.get("about", "")[:240]
        recent_json = _get_recent_posts_for_prompt(limit=3)
        import json as _json
        recent_posts = []
        try:
            recent_posts = _json.loads(recent_json)
        except Exception:
            recent_posts = []
        recent_titles = ", ".join([p.get("title", "") for p in recent_posts[:3]])
        context_snippet = f"FDWA profile: {kb_about}. Recent posts: {recent_titles}".strip()
        if context_snippet:
            # keep context short to avoid overly long LLM prompts
            base_insights = (base_insights + "\n\n" + context_snippet[:400]).strip()
    except Exception:
        # non-critical: continue without FDWA context
        pass

    
    logger.info("Generating content from base insights (%d chars)", len(base_insights))
    
    # Generate platform-specific content using adapters
    twitter_content = _adapt_for_twitter(base_insights)
    facebook_content = _adapt_for_facebook(base_insights)
    linkedin_content = _adapt_for_linkedin(base_insights)
    instagram_content = _adapt_for_instagram(base_insights)
    telegram_content = _adapt_for_telegram(base_insights)
    
    # Check Twitter for duplicates (main check)
    if is_duplicate_post(twitter_content, "twitter"):
        logger.warning("⚠️  Duplicate content detected! Adding timestamp variation...")
        _broadcast_sync("update", "Duplicate detected, creating unique variation...")
        
        # Add timestamp to make it unique
        from datetime import datetime
        unique_suffix = f"\n\n⏰ {datetime.now().strftime('%I:%M %p')}"
        twitter_content = twitter_content[:280 - len(unique_suffix)] + unique_suffix

    logger.info("✅ Generated Twitter content: %d chars", len(twitter_content))
    logger.info("✅ Generated Facebook content: %d chars", len(facebook_content))
    logger.info("✅ Generated LinkedIn content: %d chars", len(linkedin_content))
    logger.info("✅ Generated Instagram content: %d chars", len(instagram_content))
    logger.info("✅ Generated Telegram content: %d chars", len(telegram_content))
    
    _broadcast_sync("complete_step", "generate_content", {
        "twitter_length": len(twitter_content),
        "facebook_length": len(facebook_content),
        "linkedin_length": len(linkedin_content),
        "instagram_length": len(instagram_content),
        "telegram_length": len(telegram_content)
    })

    return {
        "tweet_text": twitter_content,
        "facebook_text": facebook_content,
        "linkedin_text": linkedin_content,
        "instagram_caption": instagram_content,
        "telegram_message": telegram_content
    }


def generate_image_node(state: AgentState) -> dict:
    """Generate FDWA-branded image using Hugging Face FLUX model with AI strategy.
    
    ✅ NEW: Uses AI Decision Engine strategy for topic-appropriate visuals.

    Args:
        state: Current agent state with tweet_text and optional ai_strategy.

    Returns:
        Dictionary with image_path (local file) and image_url (HTTP) or error.
    """
    logger.info("---GENERATING FDWA-BRANDED IMAGE WITH HUGGING FACE---")
    _broadcast_sync("start_step", "generate_image", "Generating strategic AI image with FLUX")
    
    tweet_text = state.get("tweet_text", "")
    ai_strategy = state.get("ai_strategy")  # ✅ Get AI strategy from state

    if not tweet_text:
        return {"error": "No tweet text for image generation"}

    # Use enhanced prompt with AI strategy
    if ai_strategy:
        topic = ai_strategy.get("topic", "business")
        _broadcast_sync("update", f"Creating {topic}-themed image with FDWA branding...")
        logger.info("Using AI strategy for image: topic=%s", topic)
        visual_prompt = _enhance_prompt_for_image(tweet_text, ai_strategy)
    else:
        _broadcast_sync("update", "Creating FDWA-branded business image...")
        visual_prompt = _enhance_prompt_for_image(tweet_text)
    
    logger.info("Enhanced visual prompt: %s", visual_prompt[:150])
    
    try:
        # Import Hugging Face image generator
        from src.agent.hf_image_gen import (
            generate_image_hf,
            save_image_locally,
            upload_to_imgbb,
        )
        
        # Generate image with Hugging Face FLUX (fast and high quality)
        result = generate_image_hf(
            prompt=visual_prompt,
            model="flux-schnell",  # FLUX.1-schnell - fast and high quality
            width=1024,  # ✅ Higher resolution for better quality
            height=1024,
        )
        
        if result.get("success"):
            # Save image locally
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hf_generated_{timestamp}.png"
            
            image_path = save_image_locally(result["image_bytes"], filename)
            logger.info("Generated image saved to: %s", image_path)
            
            # Upload to imgbb for public HTTP URL (needed for Instagram/Blog/Email)
            logger.info("Uploading to imgbb for public URL...")
            upload_result = upload_to_imgbb(result["image_bytes"])
            
            if upload_result.get("success"):
                http_url = upload_result["url"]
                logger.info("Image uploaded to imgbb: %s", http_url)
                _broadcast_sync("complete_step", "generate_image", {"url": http_url, "path": image_path})
                
                return {
                    "image_path": image_path,
                    "image_url": http_url  # HTTP URL works everywhere
                }
            else:
                logger.warning("Upload to imgbb failed: %s", upload_result.get("error"))
                logger.info("Falling back to local file for Twitter/Facebook")
                
                # Return local file path - still works for Twitter/Facebook
                return {
                    "image_path": image_path,
                    "image_url": f"file:///{image_path.replace(chr(92), '/')}"  # Local fallback
                }
        else:
            error_msg = result.get("error", "Unknown HF error")
            logger.error("Hugging Face image generation failed: %s", error_msg)
            _broadcast_sync("error", f"Image generation failed: {error_msg}")
            return {"error": f"HF generation failed: {error_msg}"}
            
    except Exception as e:
        logger.exception("Error generating image with Hugging Face: %s", e)
        _broadcast_sync("error", f"Image generation error: {str(e)}")
        return {"error": f"Image generation error: {e!s}"}


def monitor_instagram_comments_node(state: AgentState) -> dict:
    """Monitor Instagram post for comments and reply.

    Args:
        state: Current agent state with instagram_post_id.

    Returns:
        Dictionary with instagram_comment_status.
    """
    logger.info("---MONITORING INSTAGRAM COMMENTS---")
    instagram_post_id = state.get("instagram_post_id")

    if not instagram_post_id:
        logger.warning("No Instagram post ID, skipping comment monitoring")
        return {"instagram_comment_status": "Skipped: No post ID"}

    # Wait 30 seconds for comments to come in
    logger.info("Waiting 30 seconds for comments...")
    time.sleep(30)

    try:
        # Get comments on the post
        comments_response = composio_client.tools.execute(
            "INSTAGRAM_GET_POST_COMMENTS",
            {"ig_post_id": instagram_post_id, "limit": 5},
            connected_account_id=os.getenv("INSTAGRAM_ACCOUNT_ID"),
        )

        logger.info("Instagram comments response: %s", comments_response)
        
        if not comments_response.get("successful", False):
            return {"instagram_comment_status": "No comments yet"}

        comments_data = comments_response.get("data", {}).get("data", [])
        
        if not comments_data:
            logger.info("No comments found")
            return {"instagram_comment_status": "No comments yet"}

        # Reply to first comment
        first_comment = comments_data[0]
        comment_id = first_comment.get("id", "")
        comment_text = first_comment.get("text", "")
        commenter_username = first_comment.get("username", "user")

        logger.info("Replying to comment from @%s: %s", commenter_username, comment_text)

        # Generate reply
        reply_text = generate_instagram_reply(comment_text, commenter_username)

        # Post reply
        reply_response = composio_client.tools.execute(
            "INSTAGRAM_REPLY_TO_COMMENT",
            {"ig_comment_id": comment_id, "message": reply_text},
            connected_account_id=os.getenv("INSTAGRAM_ACCOUNT_ID"),
        )

        if reply_response.get("successful", False):
            logger.info("Instagram reply posted successfully!")
            return {"instagram_comment_status": f"Replied to @{commenter_username}"}
        else:
            error_msg = reply_response.get("error", "Reply failed")
            logger.error("Instagram reply failed: %s", error_msg)
            return {"instagram_comment_status": f"Failed: {error_msg}"}

    except Exception as e:
        logger.exception("Instagram comment monitoring failed: %s", e)
        return {"instagram_comment_status": f"Failed: {e!s}"}


def reply_to_twitter_node(state: AgentState) -> dict:
    """Reply to own Twitter post with FWDA link.

    Args:
        state: Current agent state with twitter_post_id.

    Returns:
        Dictionary with twitter_reply_status.
    """
    logger.info("---REPLYING TO TWITTER POST---")
    twitter_post_id = state.get("twitter_post_id")

    # Validate Twitter post ID: Must be numeric (Twitter IDs are 1-19 digits)
    if not twitter_post_id or twitter_post_id == "unknown" or not str(twitter_post_id).isdigit():
        logger.warning("No valid Twitter post ID (got: %s), skipping reply", twitter_post_id)
        return {"twitter_reply_status": "Skipped: No valid post ID"}

    # Wait 5 seconds before replying
    logger.info("Waiting 5 seconds before replying...")
    time.sleep(5)
    logger.info("Proceeding with reply")

    reply_message = "Learn more about AI Consulting and Development for your business: https://fdwa.site 🚀"

    try:
        reply_response = composio_client.tools.execute(
            "TWITTER_CREATION_OF_A_POST",
            {
                "text": reply_message,
                "reply_in_reply_to_tweet_id": str(twitter_post_id)  # Ensure string format
            },
            connected_account_id=os.getenv("TWITTER_ACCOUNT_ID"),
        )

        reply_data = reply_response.get("data", {})
        reply_id = reply_data.get("id", "replied")
        logger.info("Twitter reply posted successfully!")
        logger.info("Reply ID: %s", reply_id)
        return {"twitter_reply_status": f"Replied: {reply_id}"}

    except Exception as e:
        logger.exception("Twitter reply failed: %s", e)
        return {"twitter_reply_status": f"Failed: {e!s}"}


def comment_on_facebook_node(state: AgentState) -> dict:
    """Comment on the Facebook post with company URL.

    Args:
        state: Current agent state with facebook_post_id.

    Returns:
        Dictionary with comment_status.
    """
    logger.info("---COMMENTING ON FACEBOOK POST---")
    facebook_post_id = state.get("facebook_post_id")

    if not facebook_post_id:
        logger.warning("No Facebook post ID, skipping comment")
        return {"comment_status": "Skipped: No post ID"}

    # Wait 10 seconds for Facebook to process the post
    logger.info("Waiting 10 seconds for post to be processed...")
    time.sleep(10)
    logger.info("Proceeding with comment")

    comment_message = "Learn more at https://fdwa.site 🚀"

    try:
        comment_response = composio_client.tools.execute(
            "FACEBOOK_CREATE_COMMENT",
            {
                "message": comment_message,
                "object_id": facebook_post_id,
            },
            connected_account_id="ca_ztimDVH28syB",
        )

        comment_data = comment_response.get("data", {})
        comment_id = comment_data.get("id", "commented")
        logger.info("Facebook comment posted successfully!")
        logger.info("Comment ID: %s", comment_id)
        return {"comment_status": f"Commented: {comment_id}"}

    except Exception as e:
        logger.exception("Facebook comment failed: %s", e)
        return {"comment_status": f"Failed: {e!s}"}


def generate_blog_email_node(state: AgentState) -> dict:
    """Generate blog content and send via email with image URL in body.

    Args:
        state: Current agent state with trend_data and image_url.

    Returns:
        Dictionary with blog_status and blog_title.
    """
    logger.info("---GENERATING AND SENDING BLOG EMAIL---")
    trend_data = state.get("trend_data", "")
    
    # Get the generated image URL from state
    image_url = state.get("image_url")
    
    if image_url:
        logger.info("Blog email will include image URL: %s", image_url[:60] if image_url else "None")
        # Set environment variable so blog_email_agent can access it
        os.environ["BLOG_IMAGE_URL"] = image_url
    else:
        logger.warning("No image URL available for blog email")
    
    try:
        # Pass richer context from the main agent to the blog sub-agent so the LLM
        # can reuse insights, tweet text and any platform-specific content.
        ctx = {
            "tweet_text": state.get("tweet_text"),
            "insight": state.get("insight"),
            "platforms": {
                "twitter": state.get("tweet_text"),
                "facebook": state.get("facebook_text"),
                "linkedin": state.get("linkedin_text")
            }
        }

        blog_result = generate_and_send_blog(trend_data, image_url=image_url, context=ctx)

        if "error" in blog_result:
            logger.error("Blog generation failed: %s", blog_result["error"])
            return {"blog_status": f"Failed: {blog_result['error']}", "blog_title": ""}
        
        logger.info("Blog email process completed successfully!")
        logger.info("Blog title: %s", blog_result["blog_title"])
        logger.info("Email status: %s", blog_result["email_status"])
        logger.info("Image included: %s", blog_result.get("has_image", False))
        
        return {
            "blog_status": blog_result["email_status"],
            "blog_title": blog_result["blog_title"]
        }
        
    except Exception as e:
        logger.exception("Blog email node failed: %s", e)
        return {"blog_status": f"Failed: {str(e)}", "blog_title": ""}


def convert_to_telegram_crypto_post(trend_data: str, tweet_text: str) -> str:
    """Parse trend data and convert to Telegram crypto market update.
    
    This sub-agent extracts crypto/token data from the research and structures
    it into a Telegram-ready format with trends, top tokens, and market data.
    No additional SERP/Tavily calls - reuses existing research.
    No AI needed - uses template-based parsing.
    
    Args:
        trend_data: Raw research data from SERPAPI/Tavily
        tweet_text: Generated tweet for context
        
    Returns:
        Formatted Telegram message with crypto data
    """
    logger.info("---CONVERTING TO TELEGRAM CRYPTO POST---")
    
    # Template-based crypto post (no AI needed)
    # Extract potential crypto tokens from trend data
    crypto_keywords = ["BTC", "ETH", "SOL", "MATIC", "AVAX", "DOT", "LINK", "UNI", 
                       "AAVE", "CRV", "bitcoin", "ethereum", "defi", "crypto", "token"]
    
    found_tokens = []
    trend_lower = trend_data.lower()
    
    for keyword in crypto_keywords[:10]:  # Check first 10
        if keyword.lower() in trend_lower:
            found_tokens.append(keyword.upper())
    
    # Remove duplicates and limit to 5
    found_tokens = list(set(found_tokens))[:5]
    
    # Build structured Telegram post
    if found_tokens:
        tokens_list = " | ".join(found_tokens)
        telegram_post = f"""🚀 DeFi Market Update

📊 Trending: {tokens_list}

📈 {tweet_text.split('#')[0].strip()}

💡 Stay ahead with real-time DeFi insights and AI-powered automation.

#DeFi #Crypto #YieldBot #FinancialFreedom"""
    else:
        # Fallback when no crypto tokens found — try to enrich with live market movers from CoinMarketCap
        cmc_section = ""
        try:
            movers = get_top_gainers(5)
            if movers:
                top_lines = []
                for t in movers:
                    sym = t.get("symbol") or "?"
                    pct = t.get("percent_change_24h")
                    price = t.get("price_usd")
                    if pct is None:
                        continue
                    pct_str = f"{pct:+.2f}%"
                    price_str = f"${price:,.2f}" if isinstance(price, (int, float)) else ""
                    top_lines.append(f"{sym} {pct_str} {price_str}")
                if top_lines:
                    cmc_section = "\n\nTop gainers (24h): \n" + " | ".join(top_lines) + "\n\nData provided by CoinMarketCap.com"
        except Exception:
            cmc_section = ""

        telegram_post = f"""🚀 DeFi Market Update

{tweet_text}{cmc_section}

📊 Stay informed about the latest trends in DeFi and crypto.

💡 AI-powered insights for smarter financial decisions.

#DeFi #Crypto #YieldBot #FinancialFreedom"""

    # Ensure it's not too long for Telegram (aim for 500-800 chars)
    if len(telegram_post) > 1000:
        telegram_post = telegram_post[:997] + "..."
    
    logger.info("Telegram post generated: %d chars", len(telegram_post))
    return telegram_post


def post_telegram_node(state: AgentState) -> dict:
    """Post to Telegram group using platform-specific content.
    
    Args:
        state: Current agent state with telegram_message and image_url.
        
    Returns:
        Dictionary with telegram_status and telegram_message.
    """
    logger.info("---POSTING TO TELEGRAM---")
    
    # Use platform-specific Telegram content generated earlier
    telegram_message = state.get("telegram_message", "")
    trend_data = state.get("trend_data", "")
    tweet_text = state.get("tweet_text", "")
    image_url = state.get("image_url", "")
    
    # Fallback to crypto conversion if no telegram_message (backward compatibility)
    if not telegram_message:
        if not tweet_text:
            logger.warning("No content available for Telegram, skipping post")
            return {
                "telegram_status": "Skipped: No content",
                "telegram_message": ""
            }
        telegram_message = convert_to_telegram_crypto_post(trend_data, tweet_text)
    
    try:
        logger.info("Telegram message (platform-specific): %s", telegram_message[:100])
        
        # Telegram caption limit is 1024 chars - truncate proactively to prevent API errors
        TELEGRAM_CAPTION_LIMIT = 1000  # Safe margin under 1024
        safe_caption = telegram_message
        if len(telegram_message) > TELEGRAM_CAPTION_LIMIT:
            safe_caption = telegram_message[:TELEGRAM_CAPTION_LIMIT-3] + "..."
            logger.info("Truncated Telegram caption from %d to %d chars", len(telegram_message), len(safe_caption))
        
        # Send to Telegram group
        if image_url:
            # Try sending with photo and truncated caption
            result = telegram_agent.send_photo(
                chat_id=telegram_agent.TELEGRAM_GROUP_USERNAME or telegram_agent.TELEGRAM_GROUP_CHAT_ID,
                photo=image_url,
                caption=safe_caption
            )
            if not result.get('success'):
                # Fallback to text-only if image fails (use full message for text-only)
                logger.warning("Image send failed, sending text only with full message")
                result = telegram_agent.send_to_group(telegram_message)
        else:
            # Send text only (no limit for text messages)
            result = telegram_agent.send_to_group(telegram_message)
        
        if result.get('success'):
            msg_data = result.get('data', {}).get('result', {})
            message_id = msg_data.get('message_id', 'N/A')
            logger.info("✅ Telegram post successful: message_id=%s", message_id)
            
            # Record post to prevent duplicates
            record_post(telegram_message, "telegram", post_id=str(message_id))
            
            return {
                "telegram_status": f"Posted: message_id={message_id}",
                "telegram_message": telegram_message
            }
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error("❌ Telegram post failed: %s", error_msg)
            return {
                "telegram_status": f"Failed: {error_msg}",
                "telegram_message": telegram_message
            }
            
    except Exception as e:
        logger.exception("Telegram post error: %s", e)
        return {
            "telegram_status": f"Error: {str(e)}",
            "telegram_message": ""
        }


def post_instagram_node(state: AgentState) -> dict:
    """Post to Instagram with image and platform-specific caption.

    Args:
        state: Current agent state with instagram_caption and image_url.

    Returns:
        Dictionary with instagram_status.
    """
    logger.info("---POSTING TO INSTAGRAM---")
    
    # Use platform-specific Instagram caption generated earlier
    instagram_caption = state.get("instagram_caption", "")
    tweet_text = state.get("tweet_text", "")
    image_url = state.get("image_url")

    # Fallback to conversion if no instagram_caption (backward compatibility)
    if not instagram_caption:
        if not tweet_text or not image_url:
            return {"instagram_status": "Skipped: No content or image"}
        instagram_caption = convert_to_instagram_caption(tweet_text)
    
    if not image_url:
        return {"instagram_status": "Skipped: No image"}
    
    logger.info("Instagram caption (platform-specific): %s", instagram_caption[:100])

    try:
        # Get Instagram user ID from environment
        ig_user_id = os.getenv("INSTAGRAM_USER_ID")
        
        if not ig_user_id:
            logger.error("Instagram user ID not configured")
            return {"instagram_status": "Failed: No user ID", "instagram_caption": instagram_caption}

        # Create media container
        container_params = {
            "ig_user_id": ig_user_id,
            "image_url": image_url,
            "caption": instagram_caption,
            "content_type": "photo"
        }

        container_response = composio_client.tools.execute(
            "INSTAGRAM_CREATE_MEDIA_CONTAINER",
            container_params,
            connected_account_id=os.getenv("INSTAGRAM_ACCOUNT_ID")
        )

        logger.info("Instagram container response: %s", container_response)
        
        if container_response.get("successful", False):
            container_id = container_response.get("data", {}).get("id", "")
            
            # Wait for Instagram to process the media (required by Instagram API)
            logger.info("Waiting 10 seconds for Instagram to process media...")
            time.sleep(10)
            
            # Publish the container
            publish_response = composio_client.tools.execute(
                "INSTAGRAM_CREATE_POST",
                {"ig_user_id": ig_user_id, "creation_id": container_id},
                connected_account_id=os.getenv("INSTAGRAM_ACCOUNT_ID")
            )
            
            if publish_response.get("successful", False):
                post_id = publish_response.get("data", {}).get("id", "")
                logger.info("Instagram posted successfully! Post ID: %s", post_id)
                
                # Record post to prevent duplicates
                record_post(instagram_caption, "instagram", post_id=post_id, image_url=image_url)
                
                return {"instagram_status": "Posted", "instagram_caption": instagram_caption, "instagram_post_id": post_id}
            else:
                error_msg = publish_response.get("error", "Publish failed")
                logger.error("Instagram publish failed: %s", error_msg)
                return {"instagram_status": f"Failed: {error_msg}", "instagram_caption": instagram_caption}
        else:
            error_msg = container_response.get("error", "Container creation failed")
            logger.error("Instagram container failed: %s", error_msg)
            return {"instagram_status": f"Failed: {error_msg}", "instagram_caption": instagram_caption}

    except Exception as e:
        logger.exception("Instagram posting failed: %s", e)
        return {"instagram_status": f"Failed: {e!s}", "instagram_caption": instagram_caption}


def post_linkedin_node(state: AgentState) -> dict:
    """Post to LinkedIn using platform-specific professional content.

    Args:
        state: Current agent state with linkedin_text and image_url.

    Returns:
        Dictionary with linkedin_status.
    """
    logger.info("---POSTING TO LINKEDIN---")
    
    # Use platform-specific LinkedIn content generated earlier
    linkedin_text = state.get("linkedin_text", "")
    tweet_text = state.get("tweet_text", "")
    state.get("image_url")

    # Fallback to conversion if no linkedin_text (backward compatibility)
    if not linkedin_text:
        if not tweet_text:
            return {"linkedin_status": "Skipped: No content"}
        linkedin_text = convert_to_linkedin_post(tweet_text)
    
    logger.info("LinkedIn post (platform-specific): %s", linkedin_text[:100])

    try:
        # Use environment variables for LinkedIn credentials (ACTIVE connection)
        linkedin_account_id = os.getenv("LINKEDIN_ACCOUNT_ID", "ca_AxYGMiT-jtOU")
        author_urn = os.getenv("LINKEDIN_AUTHOR_URN", "urn:li:person:980H7U657m")
        
        logger.info("Using LinkedIn account: %s", linkedin_account_id)
        logger.info("Using author URN: %s", author_urn)

        linkedin_params = {
            "author": author_urn,
            "commentary": linkedin_text,
            "visibility": "PUBLIC"
        }
        
        # Note: LinkedIn text posts only - image support requires different API endpoints

        linkedin_response = composio_client.tools.execute(
            "LINKEDIN_CREATE_LINKED_IN_POST",
            linkedin_params,
            connected_account_id=linkedin_account_id
        )

        logger.info("LinkedIn response: %s", linkedin_response)
        
        if linkedin_response.get("successful", False):
            logger.info("LinkedIn posted successfully!")
            
            # Record post to prevent duplicates
            record_post(linkedin_text, "linkedin")
            
            return {"linkedin_status": "Posted", "linkedin_text": linkedin_text}
        else:
            error_msg = linkedin_response.get("error", "Unknown error")
            logger.error("LinkedIn post failed: %s", error_msg)
            return {"linkedin_status": f"Failed: {error_msg}", "linkedin_text": linkedin_text}

    except Exception as e:
        logger.exception("LinkedIn posting failed: %s", e)
        return {"linkedin_status": f"Failed: {e!s}", "linkedin_text": linkedin_text}


def post_social_media_node(state: AgentState) -> dict:
    """Post the generated content to both Twitter and Facebook using Composio.

    Args:
        state: Current agent state with tweet_text and image_url.

    Returns:
        Dictionary with twitter_url and facebook_status.
    """
    logger.info("---POSTING TO SOCIAL MEDIA---")
    _broadcast_sync("start_step", "post_social", "Publishing content to Twitter and Facebook")
    
    tweet_text = state.get("tweet_text")
    twitter_text = tweet_text
    image_url = state.get("image_url")
    image_path = state.get("image_path")

    if not tweet_text:
        _broadcast_sync("error", "Tweet text is empty, skipping post")
        return {"error": "Tweet text is empty, skipping post."}

    if image_url:
        logger.info("Image URL: %s", image_url)
    else:
        logger.info("No image generated")

    if image_path:
        logger.info("Image Path: %s", image_path)
    else:
        logger.info("No image file")

    # Ensure tweet is within 280 character limit for Twitter
    if not twitter_text:
        twitter_text = tweet_text or ""
    if len(twitter_text) > 280:
        twitter_text = twitter_text[:277] + "..."
        logger.info("Twitter text truncated to 280 characters")

    results = {}

    # Post to Twitter with image support
    logger.info("Posting to Twitter: %s", twitter_text)
    _broadcast_sync("update", "Publishing to Twitter...")
    try:
        twitter_params = {"text": twitter_text}
        
        # Upload media if image is available
        if image_url:
            logger.info("Uploading image to Twitter: %s", image_url)
            try:
                # Download image locally first
                local_image_path = _download_image_from_url(image_url)
                
                if local_image_path:
                    # Make sure path is absolute
                    local_image_path = os.path.abspath(local_image_path)
                    logger.warning("Local image path: %s", local_image_path)
                    logger.warning("File exists: %s", os.path.exists(local_image_path))
                    
                    media_upload_response = composio_client.tools.execute(
                        "TWITTER_UPLOAD_MEDIA",
                        {
                            "media": local_image_path,
                            "media_category": "tweet_image"
                        },
                        connected_account_id=os.getenv("TWITTER_ACCOUNT_ID")
                    )
                    
                    logger.warning("Twitter media upload response: %s", media_upload_response)
                    
                    if media_upload_response.get("successful", False):
                        logger.warning("Full media upload response: %s", media_upload_response)
                        # Always extract the media ID from the correct nested field
                        nested_data = media_upload_response.get("data", {})
                        if isinstance(nested_data, dict):
                            media_data = nested_data.get("data", {})
                        else:
                            media_data = {}
                        logger.warning("media_data: %s", media_data)
                        logger.warning("media_data keys: %s", list(media_data.keys()) if isinstance(media_data, dict) else "not dict")
                        media_id = media_data.get("id")
                        logger.warning("Extracted media_id from nested response: %s", media_id)
                        if media_id and str(media_id) not in ["{}", "None", ""]:
                            twitter_params["media_media_ids"] = [str(media_id)]
                            logger.warning("Twitter media uploaded successfully, ID: %s", media_id)
                            logger.warning("Twitter params now include media: %s", twitter_params)
                        else:
                            logger.warning("No media ID returned from Twitter upload. media_id: %s, str(media_id): %s", media_id, str(media_id))
                    else:
                        logger.error("Twitter media upload failed: %s", media_upload_response.get("error"))
                else:
                    logger.error("Failed to download image from URL: %s", image_url)
                    
            except Exception as media_e:
                logger.exception("Twitter media upload error: %s", media_e)
                # Continue with text-only post if media upload fails
        
        # Create the post (with or without media)
        twitter_response = composio_client.tools.execute(
            "TWITTER_CREATION_OF_A_POST",
            twitter_params,
            connected_account_id=os.getenv("TWITTER_ACCOUNT_ID")
        )
        
        # Extract post ID from nested Composio response structure
        twitter_data = twitter_response.get("data", {})
        # Try nested structure first (new Composio format): response['data']['data']['id']
        if isinstance(twitter_data, dict) and "data" in twitter_data:
            nested_data = twitter_data.get("data", {})
            twitter_id = nested_data.get("id", "unknown") if isinstance(nested_data, dict) else "unknown"
        else:
            # Fallback to direct structure: response['data']['id']
            twitter_id = twitter_data.get("id", "unknown")
        
        # If still unknown, check successful flag and use generic success message
        if twitter_id == "unknown" and twitter_response.get("successful", False):
            logger.info("Twitter post succeeded but ID not in expected format. Response keys: %s", list(twitter_data.keys()) if isinstance(twitter_data, dict) else "not dict")
        
        twitter_url = (
            f"https://twitter.com/user/status/{twitter_id}"
            if twitter_id != "unknown"
            else "Twitter posted successfully"
        )
        results["twitter_url"] = twitter_url
        results["twitter_post_id"] = twitter_id
        logger.info("Twitter posted successfully! URL: %s", twitter_url)
        logger.info("Twitter Post ID: %s", twitter_id)
        _broadcast_sync("update", f"✓ Twitter posted: {twitter_url}")
        
        # Record post to prevent duplicates
        record_post(twitter_text, "twitter", post_id=twitter_id, image_url=image_url)
        
    except Exception as e:
        error_msg = str(e)
        # Check for expired account
        if "EXPIRED state" in error_msg or "410" in error_msg:
            logger.error("⚠️  Twitter account expired! Reconnect at: https://app.composio.dev/")
            _broadcast_sync("error", "Twitter account expired - needs reconnection at https://app.composio.dev/")
            results["twitter_url"] = "Twitter failed: Account expired - reconnect at https://app.composio.dev/"
        else:
            logger.exception("Twitter posting failed: %s", e)
            _broadcast_sync("error", f"Twitter error: {error_msg}")
            results["twitter_url"] = f"Twitter failed: {e!s}"
    
    # Post to Facebook (use Facebook-specific content)
    facebook_text = state.get("facebook_text") or tweet_text  # Fall back to tweet if not set
    logger.info("Posting to Facebook")
    logger.info("Message: %s", facebook_text[:100])
    logger.info("Page ID: %s", os.getenv("FACEBOOK_PAGE_ID"))
    logger.info("Image File: %s", image_path if image_path else "None")
    logger.info("Published: True")
    try:
        facebook_params = {
            "page_id": os.getenv("FACEBOOK_PAGE_ID"),
            "message": facebook_text,
            "published": True,
        }

        # Add photo by downloading from URL or using local path
        if image_url and image_url.strip():
            if image_url.startswith("file:///"):
                # Local file from Hugging Face
                local_image_path = image_url.replace("file:///", "").replace("/", chr(92))
                if os.path.exists(local_image_path):
                    facebook_params["photo"] = local_image_path
                    logger.info("Facebook photo attached using HF local path: %s", local_image_path)
                    facebook_tool = "FACEBOOK_CREATE_PHOTO_POST"
                else:
                    logger.error("Local image file not found: %s", local_image_path)
                    facebook_tool = "FACEBOOK_CREATE_POST"
            elif image_url.startswith("https://"):
                # Remote URL (legacy Gemini)
                local_image_path = _download_image_from_url(image_url)
                if local_image_path:
                    facebook_params["photo"] = local_image_path
                    logger.info("Facebook photo attached using downloaded path: %s", local_image_path)
                    facebook_tool = "FACEBOOK_CREATE_PHOTO_POST"
                else:
                    logger.error("Failed to download image from URL: %s", image_url)
                    facebook_tool = "FACEBOOK_CREATE_POST"
            else:
                logger.info("Unknown image URL format, posting text-only to Facebook")
                facebook_tool = "FACEBOOK_CREATE_POST"
        else:
            logger.info("No valid image URL available, posting text-only to Facebook")
            facebook_tool = "FACEBOOK_CREATE_POST"

        facebook_response = composio_client.tools.execute(
            facebook_tool,
            facebook_params,
            connected_account_id="ca_ztimDVH28syB"
        )

        # Composio response structure: {"data": {...}, "successful": bool, "error": null}
        logger.info("Facebook response: %s", facebook_response)
        
        # Check if post was successful
        if not facebook_response.get("successful", False):
            error_msg = facebook_response.get("error", "Unknown error")
            logger.error("Facebook post failed: %s", error_msg)
            results["facebook_status"] = f"Failed: {error_msg}"
            results["facebook_post_id"] = ""
            return results
        
        # Extract data from Composio response
        # Structure: {"data": {"response_data": {"id": "...", "post_id": "..."}}}
        facebook_data = facebook_response.get("data", {})
        response_data = facebook_data.get("response_data", {})
        
        # Use post_id (full format: PAGE_ID_POST_ID) for commenting
        facebook_post_id = response_data.get("post_id", "")
        
        logger.info("Facebook posted successfully!")
        logger.info("Post ID: %s", facebook_post_id)
        _broadcast_sync("update", f"✓ Facebook posted: {facebook_post_id}")
        
        results["facebook_status"] = f"Posted: {facebook_post_id}"
        results["facebook_post_id"] = facebook_post_id
        
        # Record post to prevent duplicates (use Facebook-specific content)
        record_post(facebook_text, "facebook", post_id=facebook_post_id, image_url=image_url)
        
    except Exception as e:
        error_msg = str(e)
        # Check for expired account
        if "EXPIRED state" in error_msg or "410" in error_msg:
            logger.error("⚠️  Facebook account expired! Reconnect at: https://app.composio.dev/")
            _broadcast_sync("error", "Facebook account expired - needs reconnection at https://app.composio.dev/")
            results["facebook_status"] = "Failed: Account expired - reconnect at https://app.composio.dev/"
        else:
            logger.exception("Facebook posting failed: %s", e)
            _broadcast_sync("error", f"Facebook error: {error_msg}")
            results["facebook_status"] = f"Failed: {e!s}"
    
    # Complete social media posting step
    _broadcast_sync("complete_step", "post_social", results)
    return results


# Define the autonomous graph structure
workflow = StateGraph(AgentState)

# Add the nodes
workflow.add_node("research_trends", research_trends_node)
workflow.add_node("generate_content", generate_tweet_node)
workflow.add_node("generate_image", generate_image_node)
workflow.add_node("post_social_media", post_social_media_node)
workflow.add_node("post_linkedin", post_linkedin_node)
workflow.add_node("post_instagram", post_instagram_node)
workflow.add_node("post_telegram", post_telegram_node)
workflow.add_node("monitor_instagram_comments", monitor_instagram_comments_node)
workflow.add_node("reply_to_twitter", reply_to_twitter_node)
workflow.add_node("comment_on_facebook", comment_on_facebook_node)
workflow.add_node("generate_blog_email", generate_blog_email_node)

# Set the entrypoint
workflow.set_entry_point("research_trends")

# Add edges to define the autonomous flow
workflow.add_edge("research_trends", "generate_content")
workflow.add_edge("generate_content", "generate_image")
workflow.add_edge("generate_image", "post_social_media")
workflow.add_edge("post_social_media", "post_linkedin")  # ✅ LinkedIn ENABLED
workflow.add_edge("post_linkedin", "post_telegram")
workflow.add_edge("post_telegram", "post_instagram")
workflow.add_edge("post_instagram", "monitor_instagram_comments")
workflow.add_edge("monitor_instagram_comments", "reply_to_twitter")
workflow.add_edge("reply_to_twitter", "comment_on_facebook")
workflow.add_edge("comment_on_facebook", "generate_blog_email")
workflow.add_edge("generate_blog_email", "__end__")

# Compile the graph
graph = workflow.compile()


# Autonomous execution
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting FDWA Autonomous Social Media AI Agent...")

    # No manual input needed - fully autonomous
    inputs = {}

    try:
        final_state = graph.invoke(inputs)

        logger.info("\nAUTONOMOUS EXECUTION COMPLETE")
        logger.info("Tweet: %s", final_state.get("tweet_text", "N/A"))
        logger.info("Image: %s", final_state.get("image_url", "N/A"))
        logger.info("Twitter: %s", final_state.get("twitter_url", "N/A"))
        logger.info("Facebook: %s", final_state.get("facebook_status", "N/A"))
        logger.info("LinkedIn: %s", final_state.get("linkedin_status", "N/A"))
        logger.info("Instagram: %s", final_state.get("instagram_status", "N/A"))
        logger.info("Instagram Comments: %s", final_state.get("instagram_comment_status", "N/A"))
        logger.info("Telegram: %s", final_state.get("telegram_status", "N/A"))
        logger.info("Twitter Reply: %s", final_state.get("twitter_reply_status", "N/A"))
        logger.info("Facebook Comment: %s", final_state.get("comment_status", "N/A"))
        logger.info("Blog Email: %s", final_state.get("blog_status", "N/A"))
        logger.info("Blog Title: %s", final_state.get("blog_title", "N/A"))

        if final_state.get("error"):
            logger.error("Error: %s", final_state.get("error"))

    except Exception:
        logger.exception("Agent execution failed")