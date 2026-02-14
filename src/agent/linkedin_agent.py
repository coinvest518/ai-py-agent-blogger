"""LinkedIn Post Conversion Sub-Agent.

Converts tweet text into professional LinkedIn post format.
"""

import logging

logger = logging.getLogger(__name__)


def convert_to_linkedin_post(tweet_text: str) -> str:
    """Convert tweet text to LinkedIn post format.
    
    Args:
        tweet_text: Original tweet text with hashtags
        
    Returns:
        Professional LinkedIn post text
    """
    logger.info("Converting tweet to LinkedIn post format")
    
    # Template-based conversion (no Google AI needed)
    linkedin_post = f"""🚀 AI Automation Insight

{tweet_text}

At FWDA AI Automation Agency, we build custom AI automation workflows for SMBs - coaches, agencies, consultants, trades, wellness, beauty, fitness, and local businesses.

📊 Benefits:
• Save 20+ hours per week
• Increase lead generation by 3x
• Reduce operational costs
• Scale without adding headcount

💡 Our solutions: AI Agents, Workflow Automation, System Integration

Ready to transform your business with AI?

👉 Visit: https://fwda.site
📅 Book consultation: https://cal.com/bookme-daniel/ai-consultation-smb

#AIAutomation #SmallBusiness #BusinessGrowth #Productivity #AIAgents #WorkflowAutomation #DigitalTransformation #ServiceBusiness"""
    
    logger.info("LinkedIn post created: %d characters", len(linkedin_post))
    return linkedin_post
