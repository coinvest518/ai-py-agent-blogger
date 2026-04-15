"""FDWA Autonomous Social Media AI Agent — Slim Orchestrator.

Replaces the monolithic 2695-line graph.py.  Each node now delegates to
a focused sub-agent in  src/agent/agents/.

Workflow:
  research → generate_content → generate_image →
  post_twitter → post_facebook → post_linkedin →
  post_telegram → post_instagram →
  monitor_ig_comments → reply_twitter → comment_facebook →
  generate_blog → record_memory → END
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import StateGraph
from langsmith import traceable

# ── Core ────────────────────────────────────────────────────────────────
from src.agent.core.state import AgentState
from src.agent.core.config import validate_account_ids
from src.agent.core.knowledge import load_knowledge_context, FDWA_IDENTITY

# ── Sub-agents ──────────────────────────────────────────────────────────
from src.agent.agents import research_agent
from src.agent.agents import content_agent
from src.agent.agents import content_refiner_agent
from src.agent.agents import sentiment_agent
from src.agent.agents import analytics_agent
from src.agent.agents import twitter_agent
from src.agent.agents import facebook_agent
from src.agent.agents import linkedin_agent_v2 as linkedin_agent
from src.agent.agents import instagram_agent_v2 as instagram_agent
from src.agent.agents import telegram_agent_v2 as telegram_agent
from src.agent.agents import blog_agent
from src.agent.agents import comment_agent
from src.agent.agents import memory_agent
from src.agent.agents import upload_post_agent
from src.agent.agents import buffer_agent
from src.agent.agents import notion_agent
from src.agent.agents import gdocs_agent
from src.agent.agents import ganalytics_agent
from src.agent.agents import onchain_agent
from src.agent.agents import final_report_agent
from src.agent.agents import engagement_reader_agent
from src.agent.agents import supervisor_agent
from src.agent.middleware.retry import with_retry

# ── Existing modules kept as-is ────────────────────────────────────────
from src.agent.ai_decision_engine import get_decision_engine
from src.agent.realtime_status import broadcaster
from src.agent.tools.image_tools import generate_image, upload_image, save_image_locally

# Load environment
load_dotenv()

# ── LangSmith OTEL ─────────────────────────────────────────────────────
try:
    from langsmith.integrations.otel import configure as ls_configure
    configured = ls_configure(project_name=os.getenv("LANGSMITH_PROJECT", "fdwa-multi-agent"))
    if not configured:
        from langsmith.integrations.otel import OtelSpanProcessor
        from opentelemetry import trace as _ot_trace
        try:
            _ot_trace.get_tracer_provider().add_span_processor(
                OtelSpanProcessor(project=os.getenv("LANGSMITH_PROJECT", "fdwa-multi-agent"))
            )
        except Exception:
            pass
except Exception:
    pass

logger = logging.getLogger(__name__)

# ── Startup validation ──────────────────────────────────────────────────
_ids = validate_account_ids()
for name, val in _ids.items():
    if not val:
        logger.warning("Missing env var: %s", name)

# ── Broadcast helper ────────────────────────────────────────────────────
_broadcast_tasks: set = set()


def _broadcast_sync(method_name: str, *args, **kwargs):
    """Call async broadcaster method from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            task = asyncio.create_task(getattr(broadcaster, method_name)(*args, **kwargs))
            _broadcast_tasks.add(task)
            task.add_done_callback(_broadcast_tasks.discard)
        else:
            asyncio.run(getattr(broadcaster, method_name)(*args, **kwargs))
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
# NODE FUNCTIONS — each one delegates to its sub-agent
# ═══════════════════════════════════════════════════════════════════════

@traceable(name="supervisor_plan")
def supervisor_plan_node(state: AgentState) -> dict:
    """Plan the cycle — see src/agent/agents/supervisor_agent.py."""
    return supervisor_agent.plan(state)


@traceable(name="supervisor_reflect")
def supervisor_reflect_node(state: AgentState) -> dict:
    """Reflect on the cycle, persist to Mem0."""
    return supervisor_agent.reflect(state)


@traceable(name="pull_engagement")
def pull_engagement_node(state: AgentState) -> dict:
    """Pull yesterday's engagement from FB/LI/IG/Telegram so research can bias picks."""
    _broadcast_sync("start_step", "pull_engagement", "Reading yesterday's engagement…")
    result = engagement_reader_agent.run(state)
    _broadcast_sync("complete_step", "pull_engagement", {"summary": (result.get("engagement_summary") or "")[:160]})
    return result


@traceable(name="research_trends")
def research_trends_node(state: AgentState) -> dict:
    """Research trending topics."""
    logger.info("──── RESEARCH ────")
    _broadcast_sync("start_step", "research", "Researching trends…")

    result = research_agent.research_trends()
    trend_data = result.get("trend_data", "")

    if not trend_data or len(trend_data) < 20:
        trend_data = (
            f"AI automation is transforming business operations in {datetime.now().year}. "
            "Smart entrepreneurs are using AI agents to scale their businesses, "
            "automate customer service, and build passive income streams."
        )

    _broadcast_sync("complete_step", "research", {"source": result.get("source", "?"), "len": len(trend_data)})
    return {"trend_data": trend_data}


@traceable(name="generate_content")
def generate_content_node(state: AgentState) -> dict:
    """Generate platform-specific content via AI Decision Engine + content agents."""
    logger.info("──── GENERATE CONTENT ────")
    _broadcast_sync("start_step", "generate_content", "🧠 Consulting AI Decision Engine…")

    trend_data = state.get("trend_data", "")
    base_insights = trend_data if trend_data and len(trend_data) > 20 else (
        f"AI automation is transforming business operations in {datetime.now().year}."
    )

    # ── Inject shared FDWA knowledge so every agent knows the brand ──
    try:
        kb_snippet = load_knowledge_context()[:1500]  # enough for context, not too heavy
        base_insights = f"{FDWA_IDENTITY}\n\n{base_insights}\n\nBrand context: {kb_snippet}"
    except Exception:
        pass

    # ── AI Decision Engine ──
    strategy = None
    try:
        engine = get_decision_engine()
        strategy = engine.get_content_strategy(trend_data=base_insights)
        logger.info("AI strategy: topic=%s, products=%s",
                     strategy.get("topic"), [p["name"][:30] for p in strategy.get("products", [])])
        _broadcast_sync("update", f"Topic: {strategy.get('topic')}")

        # Enrich insights with product info
        products = strategy.get("products", [])
        if products:
            base_insights += "\n\nFeatured products:\n" + "\n".join(
                f"- {p['name']} ({p['price']})" for p in products[:2]
            )
        base_insights += f"\n\nCTA: {strategy.get('cta', 'https://fdwa.site')}"
    except Exception as e:
        logger.warning("Decision engine failed: %s", e)

    # Append FDWA context (recent posts)
    try:
        from src.agent.blog_email_agent import _load_business_profile, _get_recent_posts_for_prompt
        bp = _load_business_profile() or {}
        about = bp.get("about", "")[:240]
        recent = json.loads(_get_recent_posts_for_prompt(limit=3) or "[]")
        titles = ", ".join(p.get("title", "") for p in recent[:3])
        base_insights = (base_insights + f"\n\nFDWA: {about}. Recent: {titles}")[:2000]
    except Exception:
        pass

    # Generate per-platform content (each function calls LLM independently)
    tweet = content_agent.generate_twitter(base_insights, strategy)
    fb = content_agent.generate_facebook(base_insights, strategy)
    li = content_agent.generate_linkedin(base_insights, strategy)
    ig = content_agent.generate_instagram(base_insights, strategy)
    tg_result = content_agent.generate_telegram(base_insights, strategy)

    # generate_telegram returns dict {message, crypto_analysis}
    tg = tg_result.get("message", "") if isinstance(tg_result, dict) else str(tg_result)
    crypto_analysis = tg_result.get("crypto_analysis", {}) if isinstance(tg_result, dict) else {}

    logger.info("Content generated: TW=%d FB=%d LI=%d IG=%d TG=%d",
                len(tweet), len(fb), len(li), len(ig), len(tg))
    _broadcast_sync("complete_step", "generate_content", {
        "twitter_length": len(tweet), "facebook_length": len(fb),
        "linkedin_length": len(li), "instagram_length": len(ig),
        "telegram_length": len(tg),
    })

    return {
        "tweet_text": tweet,
        "facebook_text": fb,
        "linkedin_text": li,
        "instagram_caption": ig,
        "telegram_message": tg,
        "base_insights": base_insights,
        "ai_strategy": strategy,
        "crypto_analysis": crypto_analysis,
    }


@traceable(name="refine_content")
def refine_content_node(state: AgentState) -> dict:
    """Second-pass refinement using a different LLM purpose tag (delegation)."""
    logger.info("──── REFINE CONTENT ────")
    _broadcast_sync("start_step", "refine_content", "Polishing drafts…")
    result = content_refiner_agent.run(state)
    _broadcast_sync("complete_step", "refine_content", {
        "tw": len(result.get("tweet_text", "")),
        "li": len(result.get("linkedin_text", "")),
    })
    return result


@traceable(name="sentiment")
def sentiment_node(state: AgentState) -> dict:
    logger.info("──── SENTIMENT ────")
    return sentiment_agent.run(state)


@traceable(name="analytics")
def analytics_node(state: AgentState) -> dict:
    logger.info("──── ANALYTICS ────")
    return analytics_agent.run(state)


@traceable(name="generate_image")
def generate_image_node(state: AgentState) -> dict:
    """Generate FDWA-branded image using LLM-powered prompt agent."""
    logger.info("──── IMAGE ────")
    _broadcast_sync("start_step", "generate_image", "Designing image prompt with AI…")

    tweet_text = state.get("tweet_text", "")
    if not tweet_text:
        return {"image_url": None, "image_path": None}

    # Extract strategy context for the image prompt agent
    ai_strategy = state.get("ai_strategy") or {}
    topic = ai_strategy.get("topic", "business") if isinstance(ai_strategy, dict) else "business"
    products = ai_strategy.get("products", []) if isinstance(ai_strategy, dict) else []
    product_name = products[0].get("name") if products else None
    product_price = products[0].get("price") if products else None

    from src.agent.agents.image_prompt_agent import generate_caption_image_prompt
    prompt = generate_caption_image_prompt(
        refined_caption=tweet_text,
        research_data=state.get("trend_data"),
        product_name=product_name,
        product_price=product_price,
        topic=topic,
        platform="general",
    )
    logger.info("Image prompt (%d chars): %s", len(prompt), prompt[:120])

    try:
        from src.agent.pollinations_image_gen import (
            generate_image_with_fallback,
            save_image_locally as save_img,
            upload_to_imgbb,
        )

        result = generate_image_with_fallback(prompt=prompt, width=1024, height=1024, timeout=90)

        if result.get("success"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            provider = result.get("provider", "pollinations").lower().replace(" ", "_")
            path = save_img(result["image_bytes"], f"{provider}_{ts}.png",
                            provider=result.get("provider", "pollinations"))

            upload = upload_to_imgbb(result["image_bytes"])
            url = upload.get("url") if upload.get("success") else None  # Never use file:// — platforms need public HTTP URL

            _broadcast_sync("complete_step", "generate_image", {"url": url, "path": path})
            return {"image_path": path, "image_url": url}

        logger.warning("Image gen failed — continuing text-only")
        return {"image_path": None, "image_url": None}

    except Exception as e:
        logger.exception("Image error: %s", e)
        return {"image_path": None, "image_url": None}


# ── Platform posting nodes ──────────────────────────────────────────────

@traceable(name="post_twitter")
@with_retry(max_attempts=2)
def post_twitter_node(state: AgentState) -> dict:
    if os.getenv("SKIP_TWITTER", "").lower() in ("1", "true", "yes"):
        logger.info("post_twitter skipped by SKIP_TWITTER env")
        return {"twitter_url": "", "twitter_post_id": "skipped_by_config"}
    if supervisor_agent.should_skip(state, "post_twitter"):
        logger.info("post_twitter skipped by supervisor plan")
        return {"twitter_url": "", "twitter_post_id": "skipped_by_supervisor"}
    logger.info("──── POST: TWITTER ────")
    _broadcast_sync("start_step", "post_social", "Publishing to Twitter…")
    result = twitter_agent.run(state)
    _broadcast_sync("update", f"Twitter: {result.get('twitter_url', '?')[:60]}")
    return result


@traceable(name="post_facebook")
@with_retry(max_attempts=2)
def post_facebook_node(state: AgentState) -> dict:
    if supervisor_agent.should_skip(state, "post_facebook"):
        logger.info("post_facebook skipped by supervisor plan")
        return {"facebook_status": "skipped_by_supervisor"}
    logger.info("──── POST: FACEBOOK ────")
    _broadcast_sync("update", "Publishing to Facebook…")
    result = facebook_agent.run(state)
    _broadcast_sync("update", f"Facebook: {result.get('facebook_status', '?')[:60]}")
    _broadcast_sync("complete_step", "post_social", result)
    return result


@traceable(name="post_linkedin")
@with_retry(max_attempts=2)
def post_linkedin_node(state: AgentState) -> dict:
    if supervisor_agent.should_skip(state, "post_linkedin"):
        logger.info("post_linkedin skipped by supervisor plan")
        return {"linkedin_status": "skipped_by_supervisor"}
    logger.info("──── POST: LINKEDIN ────")
    _broadcast_sync("start_step", "post_linkedin", "Publishing to LinkedIn…")
    result = linkedin_agent.run(state)
    _broadcast_sync("complete_step", "post_linkedin", result)
    return result


@traceable(name="post_telegram")
@with_retry(max_attempts=2)
def post_telegram_node(state: AgentState) -> dict:
    """Post to Telegram — prefer the final-report briefing when available."""
    if supervisor_agent.should_skip(state, "post_telegram"):
        logger.info("post_telegram skipped by supervisor plan")
        return {"telegram_status": "skipped_by_supervisor"}
    logger.info("──── POST: TELEGRAM ────")
    _broadcast_sync("start_step", "post_telegram", "Publishing to Telegram…")

    briefing = state.get("final_briefing_markdown")
    if briefing:
        state = {**state, "telegram_message": briefing[:3500]}

    result = telegram_agent.run(state)
    _broadcast_sync("complete_step", "post_telegram", result)
    return result


@traceable(name="post_instagram")
@with_retry(max_attempts=2)
def post_instagram_node(state: AgentState) -> dict:
    if supervisor_agent.should_skip(state, "post_instagram"):
        logger.info("post_instagram skipped by supervisor plan")
        return {"instagram_status": "skipped_by_supervisor"}
    logger.info("──── POST: INSTAGRAM ────")
    _broadcast_sync("start_step", "post_instagram", "Publishing to Instagram…")
    result = instagram_agent.run(state)
    _broadcast_sync("complete_step", "post_instagram", result)
    return result


@traceable(name="ga_snapshot")
def ga_snapshot_node(state: AgentState) -> dict:
    logger.info("──── GA SNAPSHOT ────")
    return ganalytics_agent.run(state)


@traceable(name="onchain_snapshot")
def onchain_snapshot_node(state: AgentState) -> dict:
    logger.info("──── ONCHAIN SNAPSHOT ────")
    return onchain_agent.run(state)


@traceable(name="final_report")
def final_report_node(state: AgentState) -> dict:
    logger.info("──── FINAL REPORT ────")
    _broadcast_sync("start_step", "final_report", "Synthesising briefing…")
    result = final_report_agent.run(state)
    _broadcast_sync("complete_step", "final_report", {
        "len": len(result.get("final_briefing_markdown", "")),
        "gmail": result.get("briefing_gmail"),
    })
    return result


@traceable(name="post_notion")
def post_notion_node(state: AgentState) -> dict:
    logger.info("──── POST: NOTION ────")
    return notion_agent.run(state)


@traceable(name="post_gdocs")
def post_gdocs_node(state: AgentState) -> dict:
    logger.info("──── POST: GDOCS ────")
    return gdocs_agent.run(state)


@traceable(name="generate_video")
def generate_video_node(state: AgentState) -> dict:
    """Optional video generation for promote-product runs.

    Only fires when `ai_strategy.video == True`. Writes `video_url` + `video_path`
    to state; safe to skip entirely (image-only posts still work).
    """
    # Global operator switch to entirely disable video generation/uploads
    if os.getenv("DISABLE_VIDEO_GEN", "false").lower() in ("1", "true", "yes"):
        return {"video_url": None, "video_path": None}

    strat = state.get("ai_strategy") or {}
    if not (isinstance(strat, dict) and strat.get("video")):
        return {"video_url": None, "video_path": None}

    prompt = state.get("tweet_text", "")[:220] or state.get("base_insights", "")[:220]
    if not prompt:
        return {"video_url": None, "video_path": None}

    logger.info("──── VIDEO ────")
    _broadcast_sync("start_step", "generate_video", "Generating video (CogVideoX)…")
    try:
        from src.agent.video_gen.cascade import generate_with_cascade
        result = generate_with_cascade(prompt=prompt)
    except Exception as e:
        logger.warning("Video cascade crashed: %s", e)
        return {"video_url": None, "video_path": None}

    if result.get("success"):
        path = result.get("path")
        video_url = None
        if path:
            try:
                from src.agent.video_gen.gdrive_upload import upload_and_share
                up = upload_and_share(path)
                if up.get("success"):
                    video_url = up.get("direct_link")
                    logger.info("Video uploaded to Drive: %s", up.get("web_link"))
                else:
                    logger.warning("Drive upload skipped: %s", up.get("error"))
            except Exception as e:
                logger.warning("Drive upload crashed: %s", e)
        _broadcast_sync("complete_step", "generate_video", {"path": path, "url": video_url})
        return {"video_path": path, "video_url": video_url}
    return {"video_url": None, "video_path": None}


@traceable(name="post_buffer")
def post_buffer_node(state: AgentState) -> dict:
    """Buffer fan-out — schedules to every connected Buffer channel (YT/TikTok/Pinterest/etc.)."""
    logger.info("──── POST: BUFFER ────")
    if supervisor_agent.should_skip(state, "post_buffer"):
        return {"buffer_status": "skipped_by_supervisor"}
    _broadcast_sync("start_step", "post_buffer", "Queuing to Buffer channels…")
    result = buffer_agent.run(state)
    _broadcast_sync("complete_step", "post_buffer", result)
    return result


@traceable(name="post_upload_post")
def post_upload_post_node(state: AgentState) -> dict:
    """Pinterest + X + Google Business + Threads bundled fan-out through upload-post.com.

    One call → all 4 platforms → counts as 1 of 2 weekly quota units.
    """
    logger.info("──── POST: UPLOAD-POST ────")
    # Disabled by default — requires a video generator. Set UPLOAD_POST_ENABLE=true to re-enable.
    if os.getenv("UPLOAD_POST_ENABLE", "false").lower() not in ("1", "true", "yes"):
        return {"upload_post_status": "Skipped: UPLOAD_POST_ENABLE not set"}
    if supervisor_agent.should_skip(state, "post_upload_post"):
        return {"upload_post_status": "skipped_by_supervisor"}
    _broadcast_sync("start_step", "post_upload_post", "Publishing to upload-post…")
    result = upload_post_agent.run(state)
    _broadcast_sync("complete_step", "post_upload_post", result)
    return result


# ── Engagement nodes ────────────────────────────────────────────────────

@traceable(name="monitor_instagram_comments")
def monitor_ig_comments_node(state: AgentState) -> dict:
    logger.info("──── IG COMMENTS ────")
    return comment_agent.monitor_instagram(state)


@traceable(name="reply_twitter")
def reply_twitter_node(state: AgentState) -> dict:
    logger.info("──── TWITTER REPLY ────")
    return twitter_agent.reply_to_own_tweet(state)


@traceable(name="comment_facebook")
def comment_facebook_node(state: AgentState) -> dict:
    logger.info("──── FB COMMENT ────")
    return facebook_agent.comment_on_post(state)


# ── Blog + Memory ──────────────────────────────────────────────────────

@traceable(name="generate_blog")
def generate_blog_node(state: AgentState) -> dict:
    logger.info("──── BLOG ────")
    _broadcast_sync("start_step", "generate_blog", "Generating blog email…")
    result = blog_agent.run(state)
    _broadcast_sync("complete_step", "generate_blog", result)
    return result


@traceable(name="record_memory")
def record_memory_node(state: AgentState) -> dict:
    logger.info("──── MEMORY ────")
    return memory_agent.run(state)


# ═══════════════════════════════════════════════════════════════════════
# GRAPH DEFINITION
# ═══════════════════════════════════════════════════════════════════════

workflow = StateGraph(AgentState)

# Nodes
workflow.add_node("supervisor_plan", supervisor_plan_node)
workflow.add_node("pull_engagement", pull_engagement_node)
workflow.add_node("research_trends", research_trends_node)
workflow.add_node("generate_content", generate_content_node)
workflow.add_node("refine_content", refine_content_node)
workflow.add_node("sentiment", sentiment_node)
workflow.add_node("generate_image", generate_image_node)
workflow.add_node("post_twitter", post_twitter_node)
workflow.add_node("post_facebook", post_facebook_node)
workflow.add_node("post_linkedin", post_linkedin_node)
workflow.add_node("post_telegram", post_telegram_node)
workflow.add_node("post_instagram", post_instagram_node)
workflow.add_node("generate_video", generate_video_node)
workflow.add_node("post_upload_post", post_upload_post_node)
workflow.add_node("post_buffer", post_buffer_node)
workflow.add_node("ga_snapshot", ga_snapshot_node)
workflow.add_node("onchain_snapshot", onchain_snapshot_node)
workflow.add_node("final_report", final_report_node)
workflow.add_node("post_notion", post_notion_node)
workflow.add_node("post_gdocs", post_gdocs_node)
workflow.add_node("monitor_ig_comments", monitor_ig_comments_node)
workflow.add_node("reply_twitter", reply_twitter_node)
workflow.add_node("comment_facebook", comment_facebook_node)
workflow.add_node("generate_blog", generate_blog_node)
workflow.add_node("analytics", analytics_node)
workflow.add_node("record_memory", record_memory_node)
workflow.add_node("supervisor_reflect", supervisor_reflect_node)

# Entry point — supervisor plans BEFORE anything else.
workflow.set_entry_point("supervisor_plan")

# Edges — sequential flow
workflow.add_edge("supervisor_plan", "pull_engagement")
workflow.add_edge("pull_engagement", "research_trends")
workflow.add_edge("research_trends", "generate_content")
workflow.add_edge("generate_content", "refine_content")
workflow.add_edge("refine_content", "sentiment")
workflow.add_edge("sentiment", "generate_image")
# Optional video step runs in parallel with social posts (only fires when
# `ai_strategy.video == True`; otherwise returns no-op dict).
workflow.add_edge("generate_image", "generate_video")
# Fan-out: all 4 social platforms + upload-post aggregator after image is ready.
# Telegram runs LAST (joins on all branches) so its briefing reflects actual statuses.
workflow.add_edge("generate_image", "post_twitter")
workflow.add_edge("generate_image", "post_facebook")
workflow.add_edge("generate_image", "post_linkedin")
workflow.add_edge("generate_image", "post_instagram")
workflow.add_edge("generate_video", "post_upload_post")
workflow.add_edge("generate_image", "post_buffer")
workflow.add_edge("post_buffer", "ga_snapshot")
# Barrier: ga_snapshot waits for all 5 parallel social branches, then we
# chain GA → onchain → final_report → fan-out (Telegram / Notion / GDocs).
workflow.add_edge("post_twitter", "ga_snapshot")
workflow.add_edge("post_facebook", "ga_snapshot")
workflow.add_edge("post_linkedin", "ga_snapshot")
workflow.add_edge("post_instagram", "ga_snapshot")
workflow.add_edge("post_upload_post", "ga_snapshot")
workflow.add_edge("ga_snapshot", "onchain_snapshot")
workflow.add_edge("onchain_snapshot", "final_report")
workflow.add_edge("final_report", "post_telegram")
workflow.add_edge("final_report", "post_notion")
workflow.add_edge("final_report", "post_gdocs")
# Barrier: monitor_ig_comments waits for all 3 briefing destinations
workflow.add_edge("post_telegram", "monitor_ig_comments")
workflow.add_edge("post_notion", "monitor_ig_comments")
workflow.add_edge("post_gdocs", "monitor_ig_comments")
workflow.add_edge("monitor_ig_comments", "reply_twitter")
workflow.add_edge("reply_twitter", "comment_facebook")
workflow.add_edge("comment_facebook", "generate_blog")
workflow.add_edge("generate_blog", "analytics")
workflow.add_edge("analytics", "record_memory")
workflow.add_edge("record_memory", "supervisor_reflect")
workflow.add_edge("supervisor_reflect", "__end__")

# Compile
graph = workflow.compile()


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting FDWA Autonomous Social Media AI Agent (v2 — restructured)…")

    try:
        final = graph.invoke({})

        logger.info("\n════ EXECUTION COMPLETE ════")
        for key in [
            "tweet_text", "image_url", "twitter_url", "facebook_status",
            "linkedin_status", "instagram_status", "telegram_status",
            "instagram_comment_status", "twitter_reply_status", "comment_status",
            "blog_status", "blog_title", "memory_status",
        ]:
            logger.info("  %s: %s", key, str(final.get(key, "N/A"))[:120])

        if final.get("error"):
            logger.error("  Error: %s", final["error"])

    except Exception:
        logger.exception("Agent execution failed")
