"""Crypto market data tools — CoinMarketCap API + trading analyzer.

Used by the Telegram crypto agent to get token data.
"""

import logging

logger = logging.getLogger(__name__)

# Re-export from existing modules so agents only import from tools/
try:
    from src.agent.cmc_client import get_top_by_market_cap, get_top_gainers, get_top_losers
    from src.agent.crypto_trading_analyzer import CryptoTradingAnalyzer
    CMC_AVAILABLE = True
except Exception:
    CMC_AVAILABLE = False

    def get_top_gainers(limit: int = 5):
        return []

    def get_top_losers(limit: int = 5):
        return []

    def get_top_by_market_cap(limit: int = 200):
        return []

    class CryptoTradingAnalyzer:
        @staticmethod
        def analyze_tokens(gainers=None, losers=None, top_n=5):
            return [], []


def fetch_quality_tokens(top_n: int = 5) -> dict:
    """Fetch and analyze quality crypto tokens.

    Returns dict with:
      - gainers: list of analyzed token dicts
      - losers: list of analyzed token dicts
      - success: bool
    """
    try:
        all_tokens = get_top_by_market_cap(limit=200)
        if not all_tokens:
            return {"gainers": [], "losers": [], "success": False}

        gainers_raw = sorted(
            [t for t in all_tokens if t.get("quote", {}).get("USD", {}).get("percent_change_24h", 0) > 0],
            key=lambda x: x.get("quote", {}).get("USD", {}).get("percent_change_24h", 0),
            reverse=True,
        )[:50]
        losers_raw = sorted(
            [t for t in all_tokens if t.get("quote", {}).get("USD", {}).get("percent_change_24h", 0) < 0],
            key=lambda x: x.get("quote", {}).get("USD", {}).get("percent_change_24h", 0),
        )[:50]

        best_gainers, best_losers = CryptoTradingAnalyzer.analyze_tokens(
            gainers=gainers_raw, losers=losers_raw, top_n=top_n
        )

        def _to_dict(token):
            if isinstance(token, dict):
                return token
            return {
                "symbol": getattr(token, "symbol", "?"),
                "name": getattr(token, "name", ""),
                "price": getattr(token, "price_usd", 0),
                "change_24h": getattr(token, "percent_change_24h", 0),
                "market_cap": getattr(token, "market_cap", 0),
                "volume_24h": getattr(token, "volume_24h", 0),
                "trade_score": getattr(token, "trade_score", 0),
                "signal": getattr(token, "trading_signal", "HOLD"),
                "risk_level": getattr(token, "risk_level", "MEDIUM"),
            }

        return {
            "gainers": [_to_dict(t) for t in best_gainers],
            "losers": [_to_dict(t) for t in best_losers],
            "success": True,
        }
    except Exception as e:
        logger.error("Crypto fetch failed: %s", e)
        return {"gainers": [], "losers": [], "success": False}
