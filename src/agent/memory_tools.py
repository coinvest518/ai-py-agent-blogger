"""Memory tools for AI agent to read/write long-term memory.

These tools allow the LLM to:
- Remember user preferences
- Learn from past performance
- Track product success
- Access historical insights
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from langchain.tools import tool
from langchain.tools import ToolRuntime

from src.agent.memory_store import get_memory_store

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Context passed to memory tools."""
    user_id: str = "fdwa_agent"
    platform: Optional[str] = None
    topic: Optional[str] = None


# ================ READ TOOLS ================


@tool
def get_successful_topics(runtime: ToolRuntime[AgentContext]) -> str:
    """Look up topics that performed well in the past.
    
    Use this to find content topics that got high engagement.
    Returns a list of successful topics.
    """
    try:
        store = get_memory_store(runtime.context.user_id)
        platform = runtime.context.platform
        
        topics = store.get_successful_topics(platform=platform, limit=10)
        
        if not topics:
            return "No successful topics recorded yet. This is a learning opportunity!"
        
        return f"Successful topics: {', '.join(topics)}"
        
    except Exception as e:
        logger.error(f"Error getting successful topics: {e}")
        return f"Error: {e}"


@tool
def get_user_preferences(runtime: ToolRuntime[AgentContext]) -> str:
    """Look up user preferences like best posting times, preferred topics.
    
    Returns all saved preferences for this agent.
    """
    try:
        store = get_memory_store(runtime.context.user_id)
        prefs = store.get_all_user_preferences()
        
        if not prefs:
            return "No preferences saved yet."
        
        return f"User preferences: {prefs}"
        
    except Exception as e:
        logger.error(f"Error getting user preferences: {e}")
        return f"Error: {e}"


@tool
def get_platform_insights(runtime: ToolRuntime[AgentContext]) -> str:
    """Get performance insights for a specific social media platform.
    
    Returns best practices, top topics, and engagement metrics.
    """
    try:
        store = get_memory_store(runtime.context.user_id)
        platform = runtime.context.platform or "twitter"
        
        insights = store.get_platform_best_practices(platform)
        
        return f"{platform} insights: {insights}"
        
    except Exception as e:
        logger.error(f"Error getting platform insights: {e}")
        return f"Error: {e}"


@tool
def get_top_performing_products(runtime: ToolRuntime[AgentContext]) -> str:
    """Get products that drove the most engagement when mentioned.
    
    Use this to decide which products to feature in content.
    """
    try:
        store = get_memory_store(runtime.context.user_id)
        products = store.get_top_products(limit=5)
        
        if not products:
            return "No product performance data yet."
        
        result = "Top products:\n"
        for p in products:
            result += f"- {p['product_name']}: {p['mention_count']} mentions, "
            result += f"{p['total_engagement']} engagement, "
            result += f"{p['conversions']} conversions\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting top products: {e}")
        return f"Error: {e}"


@tool
def get_crypto_insights(token: Optional[str], runtime: ToolRuntime[AgentContext]) -> str:
    """Get insights about crypto token performance.
    
    Args:
        token: Token symbol (e.g., BTC, ETH) or None for all tokens
    
    Returns insights about token trading patterns and predictions.
    """
    try:
        store = get_memory_store(runtime.context.user_id)
        insights = store.get_crypto_insights(token_symbol=token, limit=10)
        
        if not insights:
            return f"No crypto insights recorded for {token or 'any token'}."
        
        return f"Crypto insights: {insights[:3]}"  # Return top 3 most recent
        
    except Exception as e:
        logger.error(f"Error getting crypto insights: {e}")
        return f"Error: {e}"


# ================ WRITE TOOLS ================


@tool
def record_content_success(
    topic: str,
    engagement: int,
    runtime: ToolRuntime[AgentContext]
) -> str:
    """Record that a content topic performed well.
    
    Args:
        topic: The topic that was posted (e.g., "AI automation")
        engagement: Engagement score (likes + comments + shares)
    
    Use this after publishing content to learn what works.
    """
    try:
        store = get_memory_store(runtime.context.user_id)
        platform = runtime.context.platform or "unknown"
        
        store.record_post_performance(
            topic=topic,
            platform=platform,
            engagement=engagement,
            success=engagement > 10  # Consider 10+ engagement as success
        )
        
        return f"✅ Recorded: '{topic}' with {engagement} engagement on {platform}"
        
    except Exception as e:
        logger.error(f"Error recording success: {e}")
        return f"Error: {e}"


@tool
def save_preference(key: str, value: str, runtime: ToolRuntime[AgentContext]) -> str:
    """Save a user preference for future reference.
    
    Args:
        key: Preference name (e.g., "best_posting_time")
        value: Preference value (e.g., "9:00 AM EST")
    
    Use this to remember learned patterns.
    """
    try:
        store = get_memory_store(runtime.context.user_id)
        store.save_user_preference(key, value)
        
        return f"✅ Saved preference: {key} = {value}"
        
    except Exception as e:
        logger.error(f"Error saving preference: {e}")
        return f"Error: {e}"


@tool
def record_product_performance(
    product_name: str,
    engagement: int,
    conversion: bool,
    runtime: ToolRuntime[AgentContext]
) -> str:
    """Record how well a product mention performed.
    
    Args:
        product_name: Name of the product mentioned
        engagement: Engagement score for the post
        conversion: Whether it led to a sale/signup (True/False)
    
    Use this to learn which products resonate with audience.
    """
    try:
        store = get_memory_store(runtime.context.user_id)
        platform = runtime.context.platform or "unknown"
        
        store.record_product_mention(
            product_name=product_name,
            platform=platform,
            engagement=engagement,
            conversion=conversion
        )
        
        return f"✅ Recorded product performance: {product_name}"
        
    except Exception as e:
        logger.error(f"Error recording product performance: {e}")
        return f"Error: {e}"


# ================ TOOL COLLECTION ================


MEMORY_READ_TOOLS = [
    get_successful_topics,
    get_user_preferences,
    get_platform_insights,
    get_top_performing_products,
    get_crypto_insights,
]

MEMORY_WRITE_TOOLS = [
    record_content_success,
    save_preference,
    record_product_performance,
]

ALL_MEMORY_TOOLS = MEMORY_READ_TOOLS + MEMORY_WRITE_TOOLS
