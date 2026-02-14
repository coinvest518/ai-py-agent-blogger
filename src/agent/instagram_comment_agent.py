"""Instagram Comment Response Sub-Agent.

Monitors Instagram posts for comments and generates helpful replies.
"""

import logging

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
    
    # Simple template-based reply
    reply = f"Thanks @{commenter_username}! 🙏 We appreciate your interest. Learn more: https://fdwa.site"
    
    logger.info("Generated reply: %s", reply)
    return reply
