"""Memory Agent — record post outcomes to long-term memory for learning.

Runs at the END of the workflow to save:
- Platform success/failure
- Product mentions + effectiveness
- Crypto insights
- Topic performance for future decisions
"""

import logging
from datetime import datetime

from src.agent.memory_store import get_memory_store
from src.agent.ai_decision_engine import get_decision_engine

logger = logging.getLogger(__name__)


def run(state: dict) -> dict:
    """Record outcomes to memory.

    Returns dict with memory_status.
    """
    logger.info("--- MEMORY AGENT ---")

    try:
        memory = get_memory_store(user_id="fdwa_agent")
        ai_strategy = state.get("ai_strategy") or {}
        topic = ai_strategy.get("topic", "general")
        products = [p.get("name") for p in ai_strategy.get("products", [])]

        platforms_success = {
            "twitter": bool(
                (state.get("twitter_post_id") and str(state.get("twitter_post_id")) not in ("unknown", ""))
                or (isinstance(state.get("twitter_url"), str) and state.get("twitter_url", "").startswith("http"))
            ),
            "facebook": "Posted" in str(state.get("facebook_status", "")),
            "linkedin": "Posted" in str(state.get("linkedin_status", "")),
            "instagram": "Posted" in str(state.get("instagram_status", "")),
            "telegram": "Posted" in str(state.get("telegram_status", "")),
        }

        successful = sum(platforms_success.values())
        overall = successful >= 3
        engagement = successful * 10

        logger.info("Results: %d/5 platforms, topic=%s", successful, topic)

        for platform, ok in platforms_success.items():
            if ok:
                memory.record_post_performance(
                    topic=topic,
                    platform=platform,
                    engagement=engagement,
                    success=True,
                    metadata={
                        "products": products,
                        "tweet_text": state.get("tweet_text", "")[:100],
                        "has_image": bool(state.get("image_url")),
                        "blog_posted": bool(state.get("blog_title")),
                    },
                )

        for name in products:
            for platform, ok in platforms_success.items():
                if ok:
                    memory.record_product_mention(
                        product_name=name,
                        platform=platform,
                        engagement=engagement,
                        conversion=False,
                    )

        # Record crypto insights
        if platforms_success.get("telegram") and "crypto" in topic.lower():
            _save_crypto_insights(state, memory, topic)

        # AI Decision Engine record
        try:
            engine = get_decision_engine()
            engine.record_post_outcome(
                topic=topic,
                products=products,
                platform="multi",
                engagement=engagement,
                success=overall,
            )
        except Exception as e:
            logger.warning("Decision engine record failed: %s", e)

        return {"memory_status": f"Recorded: {successful} platforms, topic={topic}, success={overall}"}

    except Exception as e:
        logger.error("Memory recording failed: %s", e)
        return {"memory_status": f"Failed: {e!s}"}


def _save_crypto_insights(state: dict, memory, topic: str):
    """Persist crypto token picks to memory."""
    crypto = state.get("crypto_analysis", {})
    for group, label in [("best_gainers", "gainer_pick"), ("best_losers", "loser_pick")]:
        for token in crypto.get(group, []):
            symbol = token.get("symbol") if isinstance(token, dict) else getattr(token, "symbol", None)
            if not symbol:
                continue
            data = {
                "topic": topic,
                "platform": "telegram",
                "price": token.get("price_usd") if isinstance(token, dict) else getattr(token, "price_usd", None),
                "percent_change_24h": token.get("percent_change_24h") if isinstance(token, dict) else getattr(token, "percent_change_24h", None),
                "timestamp": str(datetime.now()),
            }
            try:
                memory.record_crypto_insight(token_symbol=symbol, insight_type=label, data=data)
            except Exception:
                pass
