"""Instagram Comment Response Sub-Agent.

Monitors Instagram posts for comments and generates helpful replies.
"""

import logging

from src.agent.llm_provider import get_llm

logger = logging.getLogger(__name__)


def generate_instagram_reply(comment_text: str, commenter_username: str) -> str:
    """Generate a helpful reply to an Instagram comment.
    
    Args:
        comment_text: The comment text from the user
        commenter_username: Username of the commenter
        
    Returns:
        Reply text for the comment
    """
    logger.info("Generating Instagram reply for comment: %s", comment_text[:50])
    
    # Try LLM-first approach with template fallback
    try:
        llm = get_llm(purpose="Instagram comment reply")
        
        prompt = f"""Generate a friendly, helpful reply to this Instagram comment:

Comment: "{comment_text}"
From: @{commenter_username}

Requirements:
- Be warm, engaging, and authentic
- Address their specific comment/question if possible
- Maximum 100 characters
- Include 1-2 relevant emojis
- Mention FDWA or link to https://fdwa.site if appropriate
- Keep it natural and conversational

Output ONLY the reply text, nothing else."""

        response = llm.invoke(prompt)
        reply = response.content if hasattr(response, 'content') else str(response)
        reply = reply.strip()
        
        # Ensure reasonable length
        if len(reply) > 150:
            reply = reply[:147] + "..."
        
        logger.info("Generated Instagram reply with LLM: %s", reply[:50])
        return reply
        
    except Exception as e:
        logger.warning("LLM generation failed for Instagram reply, using template: %s", e)
        
        # Template fallback
        reply = f"Thanks @{commenter_username}! 🙏 We appreciate your interest. Learn more: https://fdwa.site"
        
        logger.info("Generated reply: %s", reply)
        return reply
