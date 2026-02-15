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


def get_top_gainers(limit: int = 50) -> List[Dict]:
    """Return top gainers sorted by 24h percent change.

    Returns a list of full token dicts with all CoinMarketCap data including:
    {symbol, name, quote: {USD: {price, percent_change_24h, volume_24h, market_cap, ...}}}
    
    Args:
        limit: Number of top gainers to fetch (default 50 for AI analysis filtering)
    
    Returns:
        List of token dicts with full CMC data, or empty list on error
    """
    headers = _get_headers()
    if not headers:
        logger.debug("CoinMarketCap API key not configured (skipping top gainers)")
        return []

    try:
        # Fetch more tokens than needed so AI can filter out low-quality ones
        params = {"start": 1, "limit": limit, "convert": "USD", "sort": "percent_change_24h", "sort_dir": "desc"}
        resp = requests.get(BASE_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", [])

        # Return full token data (analyzer will extract what it needs)
        return data

    except Exception as e:
        logger.warning("CoinMarketCap top gainers call failed: %s", e)
        return []


def get_top_losers(limit: int = 50) -> List[Dict]:
    """Return top losers (biggest negative percent_change_24h).

    Returns a list of full token dicts with all CoinMarketCap data including:
    {symbol, name, quote: {USD: {price, percent_change_24h, volume_24h, market_cap, ...}}}
    
    Args:
        limit: Number of top losers to fetch (default 50 for AI analysis filtering)
    
    Returns:
        List of token dicts with full CMC data, or empty list on error
    """
    headers = _get_headers()
    if not headers:
        return []

    try:
        # Fetch more tokens than needed so AI can filter out low-quality ones
        params = {"start": 1, "limit": limit, "convert": "USD", "sort": "percent_change_24h", "sort_dir": "asc"}
        resp = requests.get(BASE_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", [])

        # Return full token data (analyzer will extract what it needs)
        return data

    except Exception as e:
        logger.warning("CoinMarketCap top losers call failed: %s", e)
        return []


def get_top_by_market_cap(limit: int = 200) -> List[Dict]:
    """Return top cryptocurrencies by market cap (filters quality tokens).
    
    Fetches established tokens with real volume/liquidity, avoiding pump & dumps.
    
    Args:
        limit: Number of top tokens to fetch by market cap (default 200)
    
    Returns:
        List of quality token dicts sorted by market cap, or empty list on error
    """
    headers = _get_headers()
    if not headers:
        logger.debug("CoinMarketCap API key not configured")
        return []

    try:
        params = {"start": 1, "limit": limit, "convert": "USD", "sort": "market_cap"}
        resp = requests.get(BASE_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", [])
        return data
    except Exception as e:
        logger.warning("CoinMarketCap top by market cap call failed: %s", e)
        return []
