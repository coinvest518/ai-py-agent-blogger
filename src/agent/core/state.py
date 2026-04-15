"""Agent state definition for the LangGraph workflow.

Single source of truth for all keys flowing through the graph.
"""

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """State flowing through the FDWA multi-agent graph.

    Every node reads/writes specific keys. Using ``total=False`` lets nodes
    return partial dicts without filling every field.
    """

    # ── Engagement (Phase 16 — pulled pre-research) ──
    engagement: dict
    engagement_summary: str

    # ── Supervisor (Phase 17) ──
    plan: dict
    reflection: dict
    upload_post_remaining: int
    upload_post_status: str

    # ── Video (Phase 15) ──
    video_path: str
    video_url: str

    # ── Research ──
    trend_data: str
    insight: str

    # ── Operator inputs ──
    topic_override: str  # set by /post <topic> or scheduled job — threads to research + strategy

    # ── AI Decision Engine ──
    ai_strategy: dict  # topic, products, cta, platform_guidance, memory_examples
    base_insights: str  # Enriched insights (trend_data + products + CTA)

    # ── Strategy Brief (Phase 18 — engagement+GA-aware) ──
    content_strategy_brief: dict  # topic, angle, avoid, tone, platform_priorities, reasoning

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

    # ── Final report / docs ──
    final_briefing_markdown: str
    briefing_markdown: str
    briefing_title: str
    briefing_gmail: dict
    gdocs_status: str
    gdocs_url: str
    gdocs_document_id: str
    notion_status: str

    # ── Snapshots ──
    ga_snapshot: dict
    onchain_snapshot: dict

    # ── Buffer ──
    buffer_status: str
    buffer_post_ids: list
    buffer_text: str
    buffer_scheduled_at: str

    # ── Errors ──
    error: str
