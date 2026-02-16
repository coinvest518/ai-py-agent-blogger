"""Agent state definition for the LangGraph workflow.

Single source of truth for all keys flowing through the graph.
"""

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """State flowing through the FDWA multi-agent graph.

    Every node reads/writes specific keys. Using ``total=False`` lets nodes
    return partial dicts without filling every field.
    """

    # ── Research ──
    trend_data: str
    insight: str

    # ── AI Decision Engine ──
    ai_strategy: dict  # topic, products, cta, platform_guidance, memory_examples
    base_insights: str  # Enriched insights (trend_data + products + CTA)

    # ── Platform-specific content (generated independently) ──
    tweet_text: str
    facebook_text: str
    linkedin_text: str
    instagram_caption: str
    telegram_message: str

    # ── Image ──
    image_url: str   # Public HTTP URL (for Instagram / blog embeds)
    image_path: str  # Local filesystem path (for Twitter / FB upload)

    # ── Posting results ──
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
    telegram_status: str

    # ── Blog ──
    blog_status: str
    blog_title: str

    # ── Memory ──
    memory_status: str
    crypto_analysis: dict  # best_gainers, best_losers from CMC

    # ── Errors ──
    error: str
