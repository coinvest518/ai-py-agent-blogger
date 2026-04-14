"""Smoke-test each configured LLM provider with both str and message-list inputs.

Run: python -m scripts.smoke_llms
"""
from __future__ import annotations

import traceback
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

from src.agent.llm_provider import CascadingLLMWrapper, list_configured_llm_providers

PROMPT_STR = "Reply with exactly one word: READY"
PROMPT_MSGS = [
    SystemMessage(content="You are a health check. Respond tersely."),
    HumanMessage(content="Reply with exactly one word: READY"),
]

w = CascadingLLMWrapper(purpose="smoke")
init_map = {
    "Cloudflare": w._init_cloudflare,
    "Nebius": w._init_nebius,
    "Cerebras": w._init_cerebras,
    "Moonshot": w._init_moonshot,
    "NVIDIA": w._init_nvidia,
    "Google": w._init_google,
    "Qwen": w._init_qwen,
    "HuggingFace": w._init_huggingface,
}

for p in list_configured_llm_providers():
    name = p["name"]
    print(f"\n=== {name} ({p['model']}) ===")
    init = init_map.get(name)
    if not init:
        print("  no init mapping — skip")
        continue
    try:
        llm = init()
    except Exception as e:
        print(f"  INIT FAIL: {type(e).__name__}: {str(e)[:200]}")
        continue
    for label, prompt in [("str", PROMPT_STR), ("messages", PROMPT_MSGS)]:
        try:
            resp = llm.invoke(prompt)
            content = getattr(resp, "content", None) or str(resp)
            print(f"  {label:8} OK -> {str(content)[:100].strip()}")
        except Exception as e:
            print(f"  {label:8} FAIL {type(e).__name__}: {str(e)[:220]}")
