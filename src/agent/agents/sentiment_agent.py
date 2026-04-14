"""Sentiment Agent — score generated content + (optional) crypto picks.

Cheap LLM call (cascade default). Returns a dict that the graph layers
into state for memory recording. Failures are non-fatal.

Output shape:
  {
    "content_sentiment": {
       "score": -1.0..1.0,
       "label": "positive|neutral|negative",
       "confidence": 0..1,
    },
    "crypto_sentiment": {  # optional, only when crypto picks present
       "label": "bullish|neutral|bearish",
       "rationale": "..."
    }
  }
"""

import json
import logging
import re
from typing import Dict

from src.agent.llm_router import route

logger = logging.getLogger(__name__)


def _safe_parse(text: str) -> Dict | None:
    """Extract first JSON object from LLM output."""
    if not text:
        return None
    text = text.strip()
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _score_content(text: str) -> Dict:
    if not text or len(text.strip()) < 10:
        return {"score": 0.0, "label": "neutral", "confidence": 0.0}
    prompt = f"""Score the sentiment of this social media post.

POST:
{text[:1200]}

Return STRICT JSON only (no prose, no markdown):
{{"score": <-1.0..1.0>, "label": "positive|neutral|negative", "confidence": <0..1>}}"""
    try:
        llm = route(task="sentiment_classify", budget="cheap")
        resp = llm.invoke(prompt)
        raw = resp.content if hasattr(resp, "content") else str(resp)
        parsed = _safe_parse(raw)
        if parsed and "label" in parsed:
            return {
                "score": float(parsed.get("score", 0.0)),
                "label": str(parsed.get("label", "neutral")).lower(),
                "confidence": float(parsed.get("confidence", 0.5)),
            }
    except Exception as e:
        logger.debug("Sentiment LLM call failed: %s", e)
    return {"score": 0.0, "label": "neutral", "confidence": 0.0}


def _score_crypto(crypto_analysis: dict) -> Dict | None:
    """Bullish/bearish read on the run's crypto picks (when present)."""
    if not crypto_analysis:
        return None
    gainers = crypto_analysis.get("best_gainers", [])
    losers = crypto_analysis.get("best_losers", [])
    if not gainers and not losers:
        return None

    def _fmt(t):
        if isinstance(t, dict):
            return f"{t.get('symbol', '?')} {t.get('change_24h', 0):+.1f}%"
        return str(t)[:30]

    g = ", ".join(_fmt(t) for t in gainers[:3])
    l = ", ".join(_fmt(t) for t in losers[:3])
    prompt = f"""Read the market signal from these 24h moves and return STRICT JSON.

GAINERS: {g or "none"}
LOSERS: {l or "none"}

JSON: {{"label": "bullish|neutral|bearish", "rationale": "<one short sentence>"}}"""
    try:
        llm = route(task="sentiment_crypto", budget="cheap")
        resp = llm.invoke(prompt)
        raw = resp.content if hasattr(resp, "content") else str(resp)
        parsed = _safe_parse(raw)
        if parsed and "label" in parsed:
            return {
                "label": str(parsed["label"]).lower(),
                "rationale": str(parsed.get("rationale", ""))[:200],
            }
    except Exception as e:
        logger.debug("Crypto sentiment LLM failed: %s", e)
    return {"label": "neutral", "rationale": ""}


def run(state: dict) -> dict:
    """Score the refined Twitter post (representative draft) + crypto picks."""
    logger.info("--- SENTIMENT AGENT ---")
    repr_text = state.get("tweet_text") or state.get("linkedin_text") or ""
    content_sent = _score_content(repr_text)

    crypto = _score_crypto(state.get("crypto_analysis") or {})
    out = {"content_sentiment": content_sent}
    if crypto:
        out["crypto_sentiment"] = crypto
    logger.info("Sentiment: content=%s (%.2f) crypto=%s",
                content_sent["label"], content_sent["score"],
                (crypto or {}).get("label", "n/a"))
    return out
