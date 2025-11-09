"""Instagram Comment Response Sub-Agent.

Monitors Instagram posts for comments and generates helpful replies.
"""

import logging
from langchain_google_genai import GoogleGenerativeAI
from langsmith import traceable
import os

logger = logging.getLogger(__name__)


@traceable(name="generate_instagram_reply")
def generate_instagram_reply(comment_text: str, commenter_username: str) -> str:
    """Generate a helpful reply to an Instagram comment.
    
    Args:
        comment_text: The comment text from the user
        commenter_username: Username of the commenter
        
    Returns:
        Reply text for the comment
    """
    logger.info("Generating Instagram reply for comment: %s", comment_text[:50])
    
    llm = GoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0.7,
        google_api_key=os.getenv("GOOGLE_AI_API_KEY")
    )
    
    prompt = f"""You are the customer engagement AI for FWDA AI Automation Agency.

BRAND: FWDA builds custom AI automation workflows for SMBs.

COMMENT from @{commenter_username}: {comment_text}

Generate a helpful, friendly reply (max 100 characters, will add link after).

REQUIREMENTS:
- Tone: Helpful, friendly, professional
- If they ask a question: Answer briefly
- If they show interest: Thank them
- If it's positive feedback: Thank them genuinely
- Include 1 emoji max
- Keep it conversational and human
- DO NOT mention links (we'll add it automatically)

Return ONLY the reply text. No explanations."""

    try:
        response = llm.invoke(prompt)
        reply = response.strip()
        
        # Clean up
        reply = reply.replace('"""', '').replace("'''", "").replace('---', '').strip()
        
        # Ensure under 100 chars for reply text
        if len(reply) > 100:
            reply = reply[:97] + "..."
        
        # Add website link
        reply = f"{reply} Learn more: https://fdwa.site"
        
        logger.info("Generated reply: %s", reply)
        return reply
        
    except Exception as e:
        logger.exception("Failed to generate Instagram reply: %s", e)
        return f"Thanks for your comment! 😊 Learn more: https://fdwa.site"
