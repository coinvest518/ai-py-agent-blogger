"""Telegram Crypto Agent v2 — crypto data ONLY, NO images, NO fallback spam.

✅ FIX: This replaces the old _telegram_crypto_fallback() that posted hardcoded admin
  debug instructions ("Add COINMARKETCAP_API_KEY to .env...") every 80 minutes.

Rules:
  1. Telegram posts ONLY crypto token symbols + % changes.
  2. NO images ever — text only via send_to_group().
  3. If CMC API is unavailable, post a SHORT graceful message — no admin text.
  4. Uses CryptoTradingAnalyzer for quality filtering (no pump & dumps).
  5. Saves crypto tokens to Google Sheets (preserving old telegram_crypto_agent feature).
"""

import logging
import os

from src.agent.agents.content_agent import generate_telegram
from src.agent.duplicate_detector import record_post

logger = logging.getLogger(__name__)

# Google Sheets integration (best-effort)
try:
    from src.agent.sheets_agent import save_tokens_to_sheets_batch
    SHEETS_ENABLED = True
except ImportError:
    SHEETS_ENABLED = False
    logger.info("Google Sheets not available for Telegram token tracking")


def run(state: dict) -> dict:
    """Generate Telegram crypto update and post to group (text only).

    Returns dict with telegram_message, telegram_status, crypto_analysis.
    """
    logger.info("--- TELEGRAM CRYPTO AGENT ---")

    insights = state.get("base_insights", "")
    strategy = state.get("ai_strategy")

    # Generate content (fetches CMC data internally, returns dict)
    tg_result = generate_telegram(insights, strategy)
    message = tg_result.get("message", "") if isinstance(tg_result, dict) else str(tg_result)
    crypto_analysis = tg_result.get("crypto_analysis", {}) if isinstance(tg_result, dict) else {}

    if not message:
        return {"telegram_message": "", "telegram_status": "Skipped: empty", "crypto_analysis": {}}

    # Post — TEXT ONLY, never send_photo
    try:
        from src.agent import telegram_agent

        result = telegram_agent.send_to_group(message)

        if result.get("success"):
            msg_data = result.get("data", {}).get("result", {})
            msg_id = msg_data.get("message_id", "N/A")
            record_post(message, "telegram", post_id=str(msg_id))
            logger.info("Telegram posted: message_id=%s", msg_id)

            # Save tokens to Google Sheets (preserves old telegram_crypto_agent feature)
            _save_tokens_to_sheets(crypto_analysis)

            return {
                "telegram_message": message,
                "telegram_status": f"Posted: message_id={msg_id}",
                "crypto_analysis": crypto_analysis,
            }
        else:
            err = result.get("error", "Unknown")
            logger.error("Telegram post failed: %s", err)
            return {"telegram_message": message, "telegram_status": f"Failed: {err}", "crypto_analysis": crypto_analysis}

    except Exception as e:
        logger.exception("Telegram error: %s", e)
        return {"telegram_message": message, "telegram_status": f"Error: {e!s}", "crypto_analysis": crypto_analysis}


def _save_tokens_to_sheets(crypto_analysis: dict):
    """Save top crypto tokens to Google Sheets in a single batch call."""
    if not SHEETS_ENABLED or not crypto_analysis:
        return

    try:
        token_rows = []
        for group in ["best_gainers", "best_losers"]:
            for token in crypto_analysis.get(group, []):
                is_dict = isinstance(token, dict)
                token_rows.append({
                    "symbol": token.get("symbol", "?") if is_dict else getattr(token, "symbol", "?"),
                    "name": token.get("name", "") if is_dict else getattr(token, "name", ""),
                    "price": token.get("price", 0) if is_dict else getattr(token, "price_usd", 0),
                    "percent_change_24h": token.get("change_24h", 0) if is_dict else getattr(token, "percent_change_24h", 0),
                    "market_cap": token.get("market_cap", 0) if is_dict else getattr(token, "market_cap", 0),
                    "volume_24h": token.get("volume_24h", 0) if is_dict else getattr(token, "volume_24h", 0),
                    "trading_signal": token.get("signal", "HOLD") if is_dict else getattr(token, "trading_signal", "HOLD"),
                    "source": "telegram_agent_v2",
                })

        if token_rows:
            saved = save_tokens_to_sheets_batch(token_rows)
            logger.info("Batch-saved %d/%d tokens to Google Sheets", saved, len(token_rows))
    except Exception as e:
        logger.warning("Sheets batch save failed (non-fatal): %s", e)
