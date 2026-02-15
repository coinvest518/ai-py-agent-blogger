"""Instagram Caption Sub-Agent.

Converts tweet text into Instagram-optimized caption with hashtags.
"""

import logging
from src.agent.llm_provider import get_llm

logger = logging.getLogger(__name__)


def convert_to_instagram_caption(tweet_text: str) -> str:
    """Convert tweet text to Instagram caption format.
    
    Args:
        tweet_text: Original tweet text with hashtags
        
    Returns:
        Instagram-optimized caption
    """
    logger.info("Converting tweet to Instagram caption")
    
    # Try LLM-first approach with template fallback
    try:
        llm = get_llm(purpose="Instagram caption conversion")
        
        prompt = f"""Convert this tweet into an Instagram caption:

Tweet: "{tweet_text}"

Requirements:
- Visual-first, lifestyle-focused tone
- 400-600 characters
- Expand on the tweet with inspirational angle
- Include relevant emojis (but tasteful)
- Mention FWDA: AI automation workflows for SMBs (coaches, agencies, local businesses)
- Focus on benefits: save time, generate leads, scale smart
- Add CTA: link in bio for free consultation
- Hashtags: #AIAutomation #SmallBusiness #BusinessGrowth #Entrepreneur
- Be engaging and aspirational

Output ONLY the Instagram caption text, nothing else."""

        response = llm.invoke(prompt)
        instagram_caption = response.content if hasattr(response, 'content') else str(response)
        instagram_caption = instagram_caption.strip()
        
        logger.info("Instagram caption created with LLM: %d characters", len(instagram_caption))
        return instagram_caption
        
    except Exception as e:
        logger.warning("LLM generation failed for Instagram, using template: %s", e)
        
        # Template fallback
        instagram_caption = f"""🚀 Transform Your Business with AI

{tweet_text}

📊 FWDA builds custom AI automation workflows for SMBs:
• Coaches & Consultants 🎯
• Agencies & Creators 🎨
• Local Businesses 🏢
• Wellness & Fitness 💪

✨ Save time. Generate leads. Scale smart.

👉 Link in bio for free consultation!

#AIAutomation #SmallBusiness #BusinessGrowth #Productivity #AIAgents #WorkflowAutomation #Entrepreneurship #BusinessOwner #ServiceBusiness #DigitalTransformation #BusinessAutomation #SMB #TechForBusiness #FutureOfWork #BusinessSystems"""
        
        logger.info("Instagram caption created: %d characters", len(instagram_caption))
        return instagram_caption
