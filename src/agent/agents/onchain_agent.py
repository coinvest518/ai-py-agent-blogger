"""On-chain subagent — wallet balance + token stats + guarded transfers.

Reads:
  - Alchemy RPC for `eth_getBalance` (cheap, no CDP auth needed)
  - CoinMarketCap via existing `cmc_client` for token prices
  - CDP SDK for transfers (opt-in; dry-run by default)

Env (read-only path):
  ALCHEMY_API_KEY, CDP_NETWORK_ID, AGENT_WALLET_ADDRESS

Env (send path — all required):
  CDP_API_KEY_ID, CDP_API_KEY_SECRET, CDP_WALLET_SECRET, CDP_ENABLE_SEND=true
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

NETWORK_ALIAS = {
    "base-sepolia": "base-sepolia",
    "base-mainnet": "base-mainnet",
    "base": "base-mainnet",
}

ALCHEMY_HOST = {
    "base-sepolia": "base-sepolia.g.alchemy.com",
    "base-mainnet": "base-mainnet.g.alchemy.com",
}


def _network() -> str:
    raw = (os.getenv("CDP_NETWORK_ID") or "base-sepolia").strip().lower()
    return NETWORK_ALIAS.get(raw, raw)


def _alchemy_url() -> Optional[str]:
    key = os.getenv("ALCHEMY_API_KEY")
    net = _network()
    host = ALCHEMY_HOST.get(net)
    if not key or not host:
        return None
    return f"https://{host}/v2/{key}"


def get_wallet_balance(address: Optional[str] = None) -> Dict[str, Any]:
    """Return the wallet's native-token balance on the current network."""
    addr = address or os.getenv("AGENT_WALLET_ADDRESS")
    if not addr:
        return {"success": False, "error": "AGENT_WALLET_ADDRESS not set"}
    url = _alchemy_url()
    if not url:
        return {"success": False, "error": "ALCHEMY_API_KEY or network unsupported"}
    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_getBalance",
               "params": [addr, "latest"]}
    try:
        resp = requests.post(url, json=payload, timeout=15)
    except Exception as e:
        return {"success": False, "error": f"Alchemy request failed: {e}"}
    if resp.status_code != 200:
        return {"success": False, "error": f"Alchemy HTTP {resp.status_code}: {resp.text[:200]}"}
    body = resp.json()
    if "result" not in body:
        return {"success": False, "error": f"Alchemy no result: {body}"}
    wei = int(body["result"], 16)
    return {
        "success": True,
        "address": addr,
        "network": _network(),
        "wei": wei,
        "eth": wei / 1e18,
    }


def get_token_stats(symbol: str) -> Dict[str, Any]:
    """Price + 24h change via existing CMC client."""
    try:
        from src.agent.cmc_client import get_quote
    except Exception as e:
        return {"success": False, "error": f"cmc_client import failed: {e}"}
    try:
        data = get_quote(symbol)
        return {"success": True, "symbol": symbol.upper(), "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_yieldbot_stats() -> Dict[str, Any]:
    """Yieldbot token snapshot — contract from `YIELDBOT_TOKEN_ADDRESS`."""
    addr = os.getenv("YIELDBOT_TOKEN_ADDRESS")
    if not addr:
        return {"skipped": True, "reason": "YIELDBOT_TOKEN_ADDRESS not set"}
    url = _alchemy_url()
    if not url:
        return {"skipped": True, "reason": "ALCHEMY_API_KEY not set"}
    # Simplest useful signal: ERC-20 totalSupply
    totalsupply_sig = "0x18160ddd"
    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
               "params": [{"to": addr, "data": totalsupply_sig}, "latest"]}
    try:
        resp = requests.post(url, json=payload, timeout=15)
        body = resp.json()
        raw = body.get("result", "0x0")
        supply = int(raw, 16)
        return {"success": True, "address": addr, "total_supply_wei": supply,
                "network": _network()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _cdp_max_transfer() -> float:
    try:
        return float(os.getenv("CDP_MAX_TRANSFER_ETH", "0.01"))
    except ValueError:
        return 0.01


def send_transfer(to: str, amount_eth: float, dry_run: bool = True) -> Dict[str, Any]:
    """Transfer native ETH via CDP SDK. Dry-run default; double-gate live sends."""
    plan = {
        "to": to,
        "amount_eth": amount_eth,
        "network": _network(),
        "from": os.getenv("AGENT_WALLET_ADDRESS", "?"),
    }
    cap = _cdp_max_transfer()
    if amount_eth > cap:
        return {"success": False, "error": f"amount_eth {amount_eth} > CDP_MAX_TRANSFER_ETH {cap}",
                "plan": plan}

    live = (not dry_run) and os.getenv("CDP_ENABLE_SEND") == "true"
    if not live:
        logger.info("CDP dry-run transfer: %s", plan)
        return {"success": True, "dry_run": True, "plan": plan}

    try:
        from cdp import Cdp, Wallet  # type: ignore
    except Exception as e:
        return {"success": False, "error": f"cdp-sdk not installed: {e}", "plan": plan}

    key_id = os.getenv("CDP_API_KEY_ID")
    key_sec = os.getenv("CDP_API_KEY_SECRET")
    if not (key_id and key_sec):
        return {"success": False, "error": "CDP_API_KEY_ID/SECRET missing", "plan": plan}

    try:
        Cdp.configure(api_key_id=key_id, api_key_secret=key_sec)
        wallet = Wallet.fetch(os.getenv("AGENT_WALLET_ADDRESS"))
        tx = wallet.transfer(amount_eth, "eth", to).wait()
        return {
            "success": True,
            "dry_run": False,
            "tx_hash": getattr(tx, "transaction_hash", None) or str(tx),
            "plan": plan,
        }
    except Exception as e:
        logger.exception("CDP transfer failed: %s", e)
        return {"success": False, "error": str(e), "plan": plan}


def snapshot() -> Dict[str, Any]:
    """One-shot bundle for the final report agent."""
    return {
        "wallet": get_wallet_balance(),
        "yieldbot": get_yieldbot_stats(),
        "network": _network(),
    }


def run(state: dict) -> dict:
    """Graph entry — writes `onchain_snapshot` into state."""
    return {"onchain_snapshot": snapshot()}
