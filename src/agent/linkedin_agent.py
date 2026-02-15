"""LinkedIn Post Conversion Sub-Agent.

Converts tweet text into professional LinkedIn post format.
"""

import logging
from src.agent.llm_provider import get_llm

logger = logging.getLogger(__name__)


def convert_to_linkedin_post(tweet_text: str) -> str:
    """Convert tweet text to LinkedIn post format.
    
    Args:
        tweet_text: Original tweet text with hashtags
        
    Returns:
        Professional LinkedIn post text
    """
    logger.info("Converting tweet to LinkedIn post format")
    
    # Try LLM-first approach with template fallback
    try:
        llm = get_llm(purpose="LinkedIn post conversion")
        
        prompt = f"""Convert this tweet into a professional LinkedIn post:

Tweet: "{tweet_text}"

Requirements:
- Professional, business-focused tone
- 600-800 characters
- Expand on the tweet's key message with business insights
- Mention FWDA AI Automation Agency: custom AI workflows for SMBs
- Include benefits: save 20+ hours/week, 3x lead generation, reduce costs
- Add consultation CTA: https://cal.com/bookme-daniel/ai-consultation-smb
- Professional hashtags: #AIAutomation #SmallBusiness #BusinessGrowth #Productivity
- Be authoritative and value-driven

Output ONLY the LinkedIn post text, nothing else."""

        response = llm.invoke(prompt)
        linkedin_post = response.content if hasattr(response, 'content') else str(response)
        linkedin_post = linkedin_post.strip()
        
        logger.info("LinkedIn post created with LLM: %d characters", len(linkedin_post))
        return linkedin_post
        
    except Exception as e:
        logger.warning("LLM generation failed for LinkedIn, using template: %s", e)
        
        # Template fallback
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
