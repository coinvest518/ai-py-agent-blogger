# CDP Skill

Coinbase Developer Platform (CDP) SDK for programmatic wallet ops —
balance reads and token transfers. Combined with Alchemy RPC for
read-only queries that don't need CDP auth.

Install: `pip install cdp-sdk` (already declared in requirements).

## Environment

| Var | Purpose |
|---|---|
| `CDP_API_KEY_ID` | CDP API key id |
| `CDP_API_KEY_SECRET` | CDP API key secret (PEM) |
| `CDP_WALLET_SECRET` | Server-side wallet seed |
| `CDP_NETWORK_ID` | `base-sepolia` (default) or `base-mainnet` |
| `CDP_ENABLE_SEND` | Must be `true` to actually broadcast a transfer |
| `AGENT_WALLET_ADDRESS` | Public address of the agent's wallet |
| `ALCHEMY_API_KEY` | For `eth_getBalance` reads (cheaper than CDP read-calls) |

## Read patterns

```python
# Balance via Alchemy RPC (no CDP call needed)
url = f"https://{NETWORK}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
rpc = {"jsonrpc": "2.0", "method": "eth_getBalance",
       "params": [AGENT_WALLET_ADDRESS, "latest"], "id": 1}
# result is hex wei → int(result, 16) / 1e18 for ETH
```

## Send pattern (DRY-RUN by default)

```python
from cdp import Cdp, Wallet
Cdp.configure(api_key_id=..., api_key_secret=...)
wallet = Wallet.fetch(AGENT_WALLET_ADDRESS)

def send_transfer(to, amount_eth, dry_run=True):
    if dry_run or os.getenv("CDP_ENABLE_SEND") != "true":
        return {"dry_run": True, "to": to, "amount_eth": amount_eth,
                "network": CDP_NETWORK_ID}
    tx = wallet.transfer(amount_eth, "eth", to).wait()
    return {"tx_hash": tx.transaction_hash, "network": CDP_NETWORK_ID}
```

## Guardrails (non-negotiable)

1. **`dry_run=True` is the default** on every public-facing transfer call.
2. Requires BOTH `dry_run=False` AND `CDP_ENABLE_SEND=true` env to broadcast.
3. Testnet (`base-sepolia`) is the default network until user flips explicitly.
4. Per-call amount cap: reject transfers > `CDP_MAX_TRANSFER_ETH` (default 0.01).
5. Log every send attempt (dry-run or real) to `agent_status.json` for audit.
