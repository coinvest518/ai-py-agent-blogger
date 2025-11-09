"""Instagram Caption Sub-Agent.

Converts tweet text into Instagram-optimized caption with hashtags.
"""

import logging
from langchain_google_genai import GoogleGenerativeAI
from langsmith import traceable
import os

logger = logging.getLogger(__name__)


@traceable(name="convert_to_instagram_caption")
def convert_to_instagram_caption(tweet_text: str) -> str:
    """Convert tweet text to Instagram caption format.
    
    Args:
        tweet_text: Original tweet text with hashtags
        
    Returns:
        Instagram-optimized caption
    """
    logger.info("Converting tweet to Instagram caption")
    
    llm = GoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0.7,
        google_api_key=os.getenv("GOOGLE_AI_API_KEY")
    )
    
    prompt = f"""You are the Marketing Intelligence AI for FWDA AI Automation Agency.

Short Post: {tweet_text}

Create an INSTAGRAM CAPTION (150-200 words) that expands on this message.

BRAND: FWDA builds custom AI automation workflows for SMBs (coaches, agencies, consultants, trades, wellness, beauty, fitness, local businesses).

REQUIREMENTS:
- Tone: Engaging, visual, conversational
- Structure:
  * Hook (1-2 sentences)
  * Value statement about AI automation for SMBs
  * Benefits (time, leads, efficiency)
  * CTA with link in bio reference
- Include 5-8 emojis throughout (not just at end)
- Include 15-20 hashtags at the end
- Hashtags: Mix of #AIAutomation #SmallBusiness #BusinessGrowth #Productivity #AIAgents #WorkflowAutomation #Entrepreneurship #BusinessOwner #ServiceBusiness #DigitalTransformation #BusinessAutomation #SMB #TechForBusiness #FutureOfWork #BusinessSystems
- Mention "Link in bio" for booking
- No generic clichés
- Active voice
- Instagram-friendly formatting (line breaks for readability)

Return ONLY the Instagram caption text. No explanations."""

    try:
        response = llm.invoke(prompt)
        instagram_caption = response.strip()
        
        # Remove triple quotes and dashes if present
        instagram_caption = instagram_caption.replace('"""', '').replace("'''", "").replace('---', '').strip()
        
        logger.info("Instagram caption created: %d characters", len(instagram_caption))
        return instagram_caption
        
    except Exception as e:
        logger.exception("Failed to convert to Instagram caption: %s", e)
        # Fallback: return original tweet
        return tweet_text
