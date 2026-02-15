"""Lightweight CoinMarketCap helper used by the agent.

Provides small, resilient helpers to fetch top gainers/losers for Telegram posts.
- Uses environment variable `COINMARKETCAP_API_KEY` (preferred header: X-CMC_PRO_API_KEY)
- Falls back gracefully when key / network is missing.

This file is intentionally small and dependency-free (only requests).
"""
from __future__ import annotations

import logging
import os
from typing import List, Dict

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
CMC_API_KEY_ENV = "COINMARKETCAP_API_KEY"


def _get_headers() -> Dict[str, str]:
    key = os.getenv(CMC_API_KEY_ENV)
    if not key:
        return {}
    return {"X-CMC_PRO_API_KEY": key, "Accept": "application/json"}


def get_top_gainers(limit: int = 5) -> List[Dict]:
    """Return top gainers sorted by 24h percent change.

    Returns a list of dicts: {symbol, name, price_usd, percent_change_24h, market_cap}
    Empty list on error or missing API key.
    """
    headers = _get_headers()
    if not headers:
        logger.debug("CoinMarketCap API key not configured (skipping top gainers)")
        return []

    try:
        params = {"start": 1, "limit": max(30, limit * 5), "convert": "USD", "sort": "percent_change_24h", "sort_dir": "desc"}
        resp = requests.get(BASE_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", [])

        results = []
        for item in data[: limit * 2]:
            quote = item.get("quote", {}).get("USD", {})
            results.append({
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "price_usd": quote.get("price"),
                "percent_change_24h": quote.get("percent_change_24h"),
                "market_cap": quote.get("market_cap")
            })
            if len(results) >= limit:
                break

        return results

    except Exception as e:
        logger.warning("CoinMarketCap top gainers call failed: %s", e)
        return []


def get_top_losers(limit: int = 5) -> List[Dict]:
    """Return top losers (biggest negative percent_change_24h).

    Same return structure as get_top_gainers.
    """
    headers = _get_headers()
    if not headers:
        return []

    try:
        params = {"start": 1, "limit": max(30, limit * 5), "convert": "USD", "sort": "percent_change_24h", "sort_dir": "asc"}
        resp = requests.get(BASE_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", [])

        results = []
        for item in data[: limit * 2]:
            quote = item.get("quote", {}).get("USD", {})
            results.append({
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "price_usd": quote.get("price"),
                "percent_change_24h": quote.get("percent_change_24h"),
                "market_cap": quote.get("market_cap")
            })
            if len(results) >= limit:
                break

        return results

    except Exception as e:
        logger.warning("CoinMarketCap top losers call failed: %s", e)
        return []
