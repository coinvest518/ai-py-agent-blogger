"""LLM Router — task-aware delegation over the existing cascade.

Replaces `get_llm("purpose")` calls when the agent wants per-task model
selection (different model for drafting vs refining vs classification vs
long-form blog generation). Wraps each call with @traceable so LangSmith
shows `llm:<task>` spans.

The router does NOT introduce new providers — it reorders the existing
cascade defined in `llm_provider.py` so different tasks prefer different
heads.

  - tool_call         → Qwen first (best tool-calling), then Cloudflare/NVIDIA/Cerebras/Nebius/Moonshot
  - long_context      → Cloudflare first, then Google/Moonshot/Qwen/NVIDIA
  - blog_generation   → Cloudflare first, then Google/Qwen/Moonshot/NVIDIA
  - classification    → Qwen/Cloudflare first, then Google/HuggingFace
  - sentiment         → Qwen/Cloudflare first, then Google/HuggingFace
  - explain_self      → Qwen/Cloudflare first, then Google/HuggingFace
  - refine_*          → Qwen first, then Cloudflare/Google
  - default           → existing cascade order

Falls back through the full cascade on any provider failure — no behavior
change vs `get_llm()` aside from preference.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from langsmith import traceable

from src.agent.llm_provider import CascadingLLMWrapper, get_llm

logger = logging.getLogger(__name__)


# Ordered preference per task. First name wins if its key is set.
_TASK_PREFERENCE: dict[str, list[str]] = {
    "tool_call": ["QWEN_API_KEY", "CLOUDFLARE_AI_API_KEY", "NVIDIA_API_KEY", "CEREBRAS_API_KEY", "NEBIUS_API_KEY", "MOONSHOT_API_KEY", "GOOGLE_AI_API_KEY", "HF_TOKEN"],
    "long_context": ["CLOUDFLARE_AI_API_KEY", "GOOGLE_AI_API_KEY", "MOONSHOT_API_KEY", "QWEN_API_KEY", "NVIDIA_API_KEY", "CEREBRAS_API_KEY", "NEBIUS_API_KEY", "HF_TOKEN"],
    "blog_generation": ["CLOUDFLARE_AI_API_KEY", "GOOGLE_AI_API_KEY", "QWEN_API_KEY", "MOONSHOT_API_KEY", "NVIDIA_API_KEY", "CEREBRAS_API_KEY", "NEBIUS_API_KEY", "HF_TOKEN"],
    "classification": ["QWEN_API_KEY", "CLOUDFLARE_AI_API_KEY", "GOOGLE_AI_API_KEY", "HF_TOKEN"],
    "sentiment": ["QWEN_API_KEY", "CLOUDFLARE_AI_API_KEY", "GOOGLE_AI_API_KEY", "HF_TOKEN"],
    "explain_self": ["QWEN_API_KEY", "CLOUDFLARE_AI_API_KEY", "GOOGLE_AI_API_KEY", "HF_TOKEN"],
    "supervisor_plan": ["QWEN_API_KEY", "CLOUDFLARE_AI_API_KEY", "GOOGLE_AI_API_KEY", "HF_TOKEN"],
    "supervisor_reflect": ["QWEN_API_KEY", "CLOUDFLARE_AI_API_KEY", "GOOGLE_AI_API_KEY", "HF_TOKEN"],
    "schedule_parse": ["QWEN_API_KEY", "CLOUDFLARE_AI_API_KEY", "GOOGLE_AI_API_KEY", "HF_TOKEN"],
}


def _preferred_provider(task: str) -> Optional[str]:
    """Return the first env-keyed provider name actually available for this task."""
    task_key = task.lower()
    if task_key.startswith("refine"):
        prefs = ["QWEN_API_KEY", "CLOUDFLARE_AI_API_KEY", "GOOGLE_AI_API_KEY", "HF_TOKEN"]
    else:
        prefs = _TASK_PREFERENCE.get(task_key, [])
    for env_key in prefs:
        if os.getenv(env_key):
            return env_key
    return None


class _RoutedWrapper(CascadingLLMWrapper):
    """Cascading wrapper that biases ordering toward a preferred provider."""

    def __init__(self, task: str, preferred_env: Optional[str], structured_output_schema=None):
        super().__init__(purpose=task, structured_output_schema=structured_output_schema)
        self.task = task
        self._preferred_env = preferred_env

    def _get_all_providers(self):
        providers = super()._get_all_providers()
        if not self._preferred_env:
            return providers
        # Reorder so the preferred provider's init is tried first
        env_to_name = {
            "MISTRAL_API_KEY": "Mistral",
            "OPENROUTER_API_KEY": "OpenRouter",
            "CLOUDFLARE_AI_API_KEY": "Cloudflare",
            "HF_TOKEN": "HuggingFace",
            "GOOGLE_AI_API_KEY": "Google",
            "QWEN_API_KEY": "Qwen",
            "NEBIUS_API_KEY": "Nebius",
            "CEREBRAS_API_KEY": "Cerebras",
            "MOONSHOT_API_KEY": "Moonshot",
            "NVIDIA_API_KEY": "NVIDIA",
        }
        target = env_to_name.get(self._preferred_env)
        if not target:
            return providers
        head = [p for p in providers if p[0] == target]
        tail = [p for p in providers if p[0] != target]
        reordered = head + tail
        self.provider_names = [n for n, _ in reordered]
        return reordered


def route(
    task: str,
    needs_tools: bool = False,
    needs_long_context: bool = False,
    budget: str = "default",
    structured_output_schema=None,
) -> CascadingLLMWrapper:
    """Return an LLM wrapper biased toward the right model for the task.

    Args:
        task: short task tag (e.g. "refine_twitter", "blog_generation",
              "sentiment_classify", "explain_self").
        needs_tools: True if the task needs function calling (forces tool_call routing).
        needs_long_context: True for long-form work (forces long_context routing).
        budget: "cheap" forces classification routing.
        structured_output_schema: passed through to the wrapper.
    """
    if needs_tools:
        task = "tool_call"
    elif needs_long_context or budget == "long":
        task = "long_context"
    elif budget == "cheap":
        task = "classification"

    preferred = _preferred_provider(task)
    if preferred is None:
        # No preference configured — return plain cascade
        return get_llm(purpose=task, structured_output_schema=structured_output_schema)

    wrapper = _RoutedWrapper(task=task, preferred_env=preferred,
                             structured_output_schema=structured_output_schema)

    original_invoke = wrapper.invoke

    @traceable(name=f"llm:{task}")
    def _traced_invoke(prompt: Any):
        return original_invoke(prompt)

    wrapper.invoke = _traced_invoke  # type: ignore[assignment]
    return wrapper
