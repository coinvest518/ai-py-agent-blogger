"""Instagram Caption Sub-Agent.

Converts tweet text into Instagram-optimized caption with hashtags.
"""

import logging

logger = logging.getLogger(__name__)


def convert_to_instagram_caption(tweet_text: str) -> str:
    """Convert tweet text to Instagram caption format.
    
    Args:
        tweet_text: Original tweet text with hashtags
        
    Returns:
        Instagram-optimized caption
    """
    logger.info("Converting tweet to Instagram caption")
    
    # Template-based conversion (no Google AI needed)
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
