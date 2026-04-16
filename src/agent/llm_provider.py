"""Centralized LLM Provider for FDWA AI Agents.

This module provides a unified interface for accessing multiple LLM providers
with automatic fallback logic. All agents can use this to ensure maximum reliability.

Provider order in this repo now prioritizes the eight configured providers below.
Legacy models `OpenRouter` and `Mistral` are only used as fallback when no primary
provider is configured, never as the default head of the cascade.

Preferred tool-calling providers:
- Qwen (`qwen-2.1-mini`)
- Cloudflare Workers AI (`@cf/meta/llama-3.3-70b-instruct-fp8-fast`)
- Nebius (`nebius-1`)
- Cerebras (`cerebras-gpt`)
- Moonshot (`moonshot-alpha`)
- NVIDIA NIM (`nvidia-default`)
- Google Gemini (`gemini-2.0-flash`)
- HuggingFace (`meta-llama/Meta-Llama-3.1-8B-Instruct`)
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _normalize_prompt(prompt: Any) -> Tuple[str, List[Dict[str, str]]]:
    """Normalize prompt input to (plain_text, openai_messages).

    Accepts:
      - str: single user turn
      - list of LangChain BaseMessage (SystemMessage/HumanMessage/AIMessage)
      - list of {"role","content"} dicts
      - any other object with .content attribute
    """
    role_map = {"system": "system", "human": "user", "ai": "assistant", "user": "user", "assistant": "assistant"}
    messages: List[Dict[str, str]] = []

    def _role_for(obj: Any) -> str:
        t = getattr(obj, "type", None) or getattr(obj, "role", None)
        if isinstance(t, str):
            return role_map.get(t.lower(), "user")
        cls = obj.__class__.__name__.lower()
        if "system" in cls:
            return "system"
        if "ai" in cls or "assistant" in cls:
            return "assistant"
        return "user"

    if isinstance(prompt, str):
        messages = [{"role": "user", "content": prompt}]
    elif isinstance(prompt, list):
        for item in prompt:
            if isinstance(item, dict) and "content" in item:
                messages.append({"role": role_map.get(str(item.get("role", "user")).lower(), "user"),
                                 "content": str(item.get("content", ""))})
            else:
                content = getattr(item, "content", None)
                if content is None:
                    content = str(item)
                messages.append({"role": _role_for(item), "content": str(content)})
    else:
        content = getattr(prompt, "content", None) or str(prompt)
        messages = [{"role": "user", "content": content}]

    plain = "\n\n".join(
        (f"[{m['role'].upper()}]\n{m['content']}" if m["role"] != "user" else m["content"])
        for m in messages
    )
    return plain, messages


def _effective_env_value(env_key: str) -> Optional[str]:
    """Return the configured env value, including known alias fallbacks."""
    value = os.getenv(env_key)
    if value:
        return value
    alias_map = {
        "GOOGLE_AI_API_KEY": ["GOOGLE_API_KEY"],
        "HF_TOKEN": ["HUGGINGFACEHUB_API_TOKEN"],
    }
    for alias in alias_map.get(env_key, []):
        alt_value = os.getenv(alias)
        if alt_value:
            return alt_value
    return None

PROVIDER_REGISTRY: List[Tuple[str, str, str, Optional[str]]] = [
    # Primary (health-verified as of 2026-04-14): Nebius + NVIDIA are the only free providers with live quota.
    ("Nebius", "NEBIUS_API_KEY", "LLM_MODEL_NEBIUS", "meta-llama/Llama-3.3-70B-Instruct"),
    ("NVIDIA", "NVIDIA_API_KEY", "LLM_MODEL_NVIDIA", "meta/llama-3.3-70b-instruct"),
    # Secondary (paid quota / legacy fallback) — used as primary now since the rest are dead:
    ("Mistral", "MISTRAL_API_KEY", "LLM_MODEL_MISTRAL", "mistral-large-2512"),
    ("OpenRouter", "OPENROUTER_API_KEY", "LLM_MODEL_OPENROUTER", "openrouter/free"),
    # Cooldown (daily/monthly quota resets expected) — opt-in via *_ENABLE=true:
    ("Cloudflare", "CLOUDFLARE_AI_API_KEY", "CLOUDFLARE_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast"),
    ("HuggingFace", "HF_TOKEN", "LLM_MODEL_HF", "meta-llama/Meta-Llama-3.1-8B-Instruct"),
    # Dead providers (payment required / suspended) — must be explicitly re-enabled via *_ENABLE=true:
    ("Cerebras", "CEREBRAS_API_KEY", "LLM_MODEL_CEREBRAS", "gpt-oss-120b"),
    ("Moonshot", "MOONSHOT_API_KEY", "LLM_MODEL_MOONSHOT", "moonshot-v1-8k"),
    ("Google", "GOOGLE_AI_API_KEY", "LLM_MODEL_GOOGLE", "gemini-2.0-flash"),
    ("Qwen", "QWEN_API_KEY", "LLM_MODEL_QWEN", "qwen-2.1-mini"),
]


# Per-purpose provider preference — each task prefers a specific model to spread
# rate-limit pressure across providers. Cascade still runs on failure.
PURPOSE_PROVIDER_PREFERENCE: Dict[str, List[str]] = {
    "facebook": ["Nebius", "NVIDIA", "Mistral", "OpenRouter"],
    "linkedin": ["NVIDIA", "Nebius", "Mistral", "OpenRouter"],
    "instagram": ["Mistral", "Nebius", "NVIDIA", "OpenRouter"],
    "twitter": ["NVIDIA", "Nebius", "Mistral", "OpenRouter"],
    "blog": ["Nebius", "Mistral", "NVIDIA", "OpenRouter"],
    "briefing": ["OpenRouter", "Mistral", "Nebius", "NVIDIA"],
    "strategy": ["Nebius", "NVIDIA", "Mistral", "OpenRouter"],
    "image": ["NVIDIA", "Nebius", "Mistral", "OpenRouter"],
    "comment": ["Mistral", "OpenRouter", "Nebius", "NVIDIA"],
    "supervisor": ["OpenRouter", "Mistral", "Nebius", "NVIDIA"],
    "chat": ["NVIDIA", "Nebius", "Mistral", "OpenRouter"],
}


# Providers explicitly in cooldown (quota reset expected). Logged at startup so
# the main agent / operator knows to wait rather than troubleshoot.
COOLDOWN_PROVIDERS = {"Cloudflare": "daily neurons quota — resets 00:00 UTC",
                      "HuggingFace": "monthly inference credits — wait for billing reset"}
DEAD_PROVIDERS = {"Cerebras": "402 payment required",
                  "Moonshot": "account suspended (insufficient balance)",
                  "Google": "429 quota exhausted",
                  "Qwen": "QWEN_API_KEY not set / 404 endpoint"}


class CascadingLLMWrapper:
    """Wrapper that automatically cascades through all available LLM providers on failure."""
    
    def __init__(self, purpose: str = "general", structured_output_schema=None):
        """Initialize the cascading LLM wrapper.
        
        Args:
            purpose: Purpose of the LLM usage (affects token limits)
            structured_output_schema: Optional schema for structured outputs
        """
        self.purpose = purpose
        self.structured_output_schema = structured_output_schema
        self.last_working_provider = None
        self.provider_names = []
        
    def _get_all_providers(self):
        """Get list of all available LLM providers in priority order.

        Gating logic:
          - DEAD_PROVIDERS are blocked unless their *_ENABLE=true flag is set.
          - COOLDOWN_PROVIDERS (Cloudflare, HuggingFace) are blocked unless *_ENABLE=true.
          - LLM_DISABLED_PROVIDERS env (comma list) forces-block any provider name.
          - Purpose preference reorders the cascade so each task hits a different
            primary first, spreading rate-limit pressure.
        """
        init_map = {
            "Cloudflare": self._init_cloudflare,
            "Nebius": self._init_nebius,
            "Cerebras": self._init_cerebras,
            "NVIDIA": self._init_nvidia,
            "Moonshot": self._init_moonshot,
            "HuggingFace": self._init_huggingface,
            "Google": self._init_google,
            "Qwen": self._init_qwen,
            "Mistral": self._init_mistral,
            "OpenRouter": self._init_openrouter,
        }

        disabled_env = {s.strip() for s in os.getenv("LLM_DISABLED_PROVIDERS", "").split(",") if s.strip()}
        enable_flags = {
            "Cloudflare": os.getenv("CLOUDFLARE_ENABLE", "false").lower() in ("1", "true", "yes"),
            "HuggingFace": os.getenv("HF_ENABLE", "false").lower() in ("1", "true", "yes"),
            "Cerebras": os.getenv("CEREBRAS_ENABLE", "false").lower() in ("1", "true", "yes"),
            "Moonshot": os.getenv("MOONSHOT_ENABLE", "false").lower() in ("1", "true", "yes"),
            "Google": os.getenv("GOOGLE_ENABLE", "false").lower() in ("1", "true", "yes"),
            "Qwen": os.getenv("QWEN_ENABLE", "false").lower() in ("1", "true", "yes"),
        }

        providers = []
        skipped: dict[str, str] = {}
        for name, env_key, _, _default_model in PROVIDER_REGISTRY:
            reason: str | None = None
            if name in disabled_env:
                reason = "disabled via LLM_DISABLED_PROVIDERS"
            elif not _effective_env_value(env_key):
                reason = f"missing env key {env_key}"
            elif name == "Cloudflare" and not os.getenv("CLOUDFLARE_ACCOUNT_ID"):
                reason = "missing CLOUDFLARE_ACCOUNT_ID"
            elif name in DEAD_PROVIDERS and not enable_flags.get(name, False):
                reason = f"blocked (dead) — set {name.upper()}_ENABLE=true to override"
            elif name in COOLDOWN_PROVIDERS and not enable_flags.get(name, False):
                reason = f"blocked (cooldown) — set {name.upper()}_ENABLE=true to override"
            else:
                init = init_map.get(name)
                if init is None:
                    reason = "no init function"
                else:
                    providers.append((name, init))

            if reason:
                skipped[name] = reason

        if skipped:
            logger.debug("LLM providers skipped: %s", skipped)

        # Reorder by per-purpose preference (preferred primaries first, rest follow).
        purpose_key = next((k for k in PURPOSE_PROVIDER_PREFERENCE if k in (self.purpose or "").lower()), None)
        if purpose_key:
            pref = PURPOSE_PROVIDER_PREFERENCE[purpose_key]
            preferred = [p for p in providers if p[0] in pref]
            preferred.sort(key=lambda p: pref.index(p[0]) if p[0] in pref else 99)
            rest = [p for p in providers if p[0] not in pref]
            providers = preferred + rest

        self.provider_names = [name for name, _ in providers]
        if not providers:
            providers.extend(self._legacy_fallback_providers())
            self.provider_names = [name for name, _ in providers]

        logger.info("LLM provider order for purpose '%s': %s", self.purpose, ", ".join(self.provider_names))
        return providers

    def _legacy_fallback_providers(self):
        """Return legacy fallback providers only when no primary providers are configured."""
        fallback_providers = []
        if os.getenv("OPENROUTER_API_KEY"):
            fallback_providers.append(("OpenRouter", self._init_openrouter))
        if os.getenv("MISTRAL_API_KEY"):
            fallback_providers.append(("Mistral", self._init_mistral))
        return fallback_providers
    
    def _init_mistral(self):
        """Initialize Mistral provider."""
        from langchain_mistralai import ChatMistralAI
        mistral_key = os.getenv("MISTRAL_API_KEY")
        mistral_model = os.getenv("LLM_MODEL_MISTRAL", "mistral-large-2512")
        mistral_temp = float(os.getenv("LLM_TEMPERATURE", "0.25"))
        
        # Add configurable max_tokens for cost/performance optimization
        mistral_max_tokens = int(os.getenv("MISTRAL_MAX_TOKENS", "4096"))  # Reduced from unlimited
        
        # For blog generation, use even more conservative limits
        if "blog" in self.purpose.lower():
            mistral_max_tokens = int(os.getenv("BLOG_MAX_TOKENS", "3000"))  # 3000 tokens ≈ 2000 words (plenty for blogs)
        
        # NOTE: Mistral API no longer accepts timeout/request_timeout parameters (as of 2026)
        llm = ChatMistralAI(
            model=mistral_model,
            temperature=mistral_temp,
            mistral_api_key=mistral_key,
            max_tokens=mistral_max_tokens
        )
        if self.structured_output_schema:
            return llm.with_structured_output(self.structured_output_schema)
        return llm
    
    def _init_openrouter(self):
        """Initialize OpenRouter provider."""
        from langchain_openai import ChatOpenAI
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        openrouter_model = os.getenv("LLM_MODEL_OPENROUTER", "openrouter/free")
        openrouter_temp = float(os.getenv("LLM_TEMPERATURE", "0.25"))
        return ChatOpenAI(
            model=openrouter_model,
            temperature=openrouter_temp,
            openai_api_key=openrouter_key,
            openai_api_base="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://fdwa.site",
                "X-Title": "FDWA Content Agent"
            }
        )
    
    def _init_huggingface(self):
        """Initialize Hugging Face provider."""
        from huggingface_hub import InferenceClient
        hf_token = os.getenv("HF_TOKEN")
        hf_provider = os.getenv("HF_INFERENCE_PROVIDER", "sambanova")
        hf_model = os.getenv("LLM_MODEL_HF", "meta-llama/Meta-Llama-3.1-8B-Instruct")
        hf_temp = float(os.getenv("LLM_TEMPERATURE", "0.7"))

        class HFChatWrapper:
            """Wrapper to use InferenceClient with .invoke() interface for compatibility."""
            def __init__(self, model, token, provider="sambanova", temperature=0.7):
                self.model = model
                self.provider = provider
                self.client = InferenceClient(
                    provider=provider,
                    api_key=token
                )
                self.temperature = temperature

            def invoke(self, prompt_text):
                try:
                    _, msgs = _normalize_prompt(prompt_text)
                    if not any(m["role"] == "system" for m in msgs):
                        msgs = [{"role": "system", "content": "You are a technical writer. Always respond with valid JSON only."}] + msgs
                    completion = self.client.chat_completion(
                        model=self.model,
                        messages=msgs,
                        temperature=self.temperature,
                        max_tokens=8192,
                        response_format={"type": "json_object"}
                    )
                    
                    content = completion.choices[0].message.content
                    if not content or not content.strip():
                        raise RuntimeError("Hugging Face returned empty content")
                    
                    class _R:
                        def __init__(self, c):
                            self.content = c
                    
                    return _R(content)
                    
                except Exception as e:
                    error_msg = str(e)
                    if "401" in error_msg or "Unauthorized" in error_msg:
                        raise RuntimeError("Hugging Face Inference API: Unauthorized (HTTP 401)") from e
                    if "429" in error_msg or "rate" in error_msg.lower():
                        raise RuntimeError("Hugging Face Inference API: Rate limited (HTTP 429)") from e
                    raise RuntimeError(f"Hugging Face Inference API request failed: {e}") from e

        return HFChatWrapper(hf_model, hf_token, hf_provider, hf_temp)
    def _init_cloudflare(self):
        """Initialize Cloudflare Workers AI text provider."""
        import requests

        account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        api_key = os.getenv("CLOUDFLARE_AI_API_KEY")
        model = os.getenv("CLOUDFLARE_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
        temp = float(os.getenv("LLM_TEMPERATURE", "0.25"))
        base_url = os.getenv("CLOUDFLARE_AI_BASE_URL", "https://api.cloudflare.com/client/v4")

        class CloudflareWrapper:
            def __init__(self, account_id, api_key, model, base_url, temperature=0.25):
                self.account_id = account_id
                self.api_key = api_key
                self.model = model
                self.base_url = base_url.rstrip("/")
                self.temperature = temperature

            def invoke(self, prompt_text):
                plain, _ = _normalize_prompt(prompt_text)
                url = f"{self.base_url}/accounts/{self.account_id}/ai/run/{self.model}"
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "prompt": plain,
                    "input": plain,
                    "temperature": self.temperature,
                }
                r = requests.post(url, headers=headers, json=payload, timeout=120)
                if r.status_code != 200:
                    raise RuntimeError(f"Cloudflare AI error: {r.status_code} - {r.text[:300]}")
                data = r.json()
                result = data.get("result") or data
                output = None

                def _extract_text(item):
                    if isinstance(item, dict):
                        if "text" in item:
                            return item.get("text")
                        if "markdown" in item:
                            return item.get("markdown")
                        if "content" in item:
                            return _extract_text(item.get("content"))
                    if isinstance(item, list):
                        for element in item:
                            parsed = _extract_text(element)
                            if parsed:
                                return parsed
                    return None

                if isinstance(result, dict):
                    output = _extract_text(result.get("output") or result.get("content") or result.get("response"))
                    if not output and isinstance(result.get("output"), list):
                        for block in result.get("output", []):
                            output = _extract_text(block)
                            if output:
                                break
                    if not output and isinstance(result.get("response"), str):
                        output = result.get("response")
                if not output:
                    output = data.get("text") or data.get("output") or data.get("response")
                if not output:
                    raise RuntimeError(f"Cloudflare AI returned empty output: {data}")
                class R:
                    def __init__(self, c):
                        self.content = c
                return R(output)

        return CloudflareWrapper(account_id, api_key, model, base_url, temp)

    def _init_openai_compatible_provider(self, env_api_key: str, env_base: str, env_model: str, default_base: str, default_model: str, name: str):
        import requests
        api_key = _effective_env_value(env_api_key)
        if not api_key:
            raise RuntimeError(f"{name} API key not set")
        base_url = os.getenv(env_base, default_base)
        model = os.getenv(env_model, default_model)
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.25"))

        class HTTPProviderWrapper:
            def __init__(self, api_key, base_url, model, temperature):
                self.api_key = api_key
                self.base_url = base_url.rstrip("/")
                self.model = model
                self.temperature = temperature

            def invoke(self, prompt_text):
                _, msgs = _normalize_prompt(prompt_text)
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self.model,
                    "messages": msgs,
                    "temperature": self.temperature,
                }
                r = requests.post(self.base_url, json=payload, headers=headers, timeout=120)
                if r.status_code != 200:
                    raise RuntimeError(f"{name} error: {r.status_code} - {r.text[:300]}")
                data = r.json()
                choices = data.get("choices") or []
                if not choices:
                    raise RuntimeError(f"{name} returned no choices")
                first = choices[0]
                text = None
                if isinstance(first, dict):
                    text = (first.get("message") or {}).get("content") if first.get("message") else first.get("text")
                if not text:
                    raise RuntimeError(f"{name} returned empty text")
                class R:
                    def __init__(self, c):
                        self.content = c
                return R(text)

        return HTTPProviderWrapper(api_key, base_url, model, temperature)

    def _init_nebius(self):
        return self._init_openai_compatible_provider(
            "NEBIUS_API_KEY",
            "NEBIUS_API_BASE",
            "LLM_MODEL_NEBIUS",
            "https://api.studio.nebius.com/v1/chat/completions",
            "meta-llama/Llama-3.3-70B-Instruct",
            "Nebius",
        )

    def _init_cerebras(self):
        return self._init_openai_compatible_provider(
            "CEREBRAS_API_KEY",
            "CEREBRAS_API_BASE",
            "LLM_MODEL_CEREBRAS",
            "https://api.cerebras.ai/v1/chat/completions",
            "llama3.1-8b",
            "Cerebras",
        )

    def _init_moonshot(self):
        return self._init_openai_compatible_provider(
            "MOONSHOT_API_KEY",
            "MOONSHOT_API_BASE",
            "LLM_MODEL_MOONSHOT",
            "https://api.moonshot.ai/v1/chat/completions",
            "moonshot-v1-8k",
            "Moonshot",
        )

    def _init_nvidia(self):
        return self._init_openai_compatible_provider(
            "NVIDIA_API_KEY",
            "NVIDIA_API_BASE",
            "LLM_MODEL_NVIDIA",
            "https://integrate.api.nvidia.com/v1/chat/completions",
            "meta/llama-3.3-70b-instruct",
            "NVIDIA",
        )

    def _init_qwen(self):
        """Initialize Qwen provider (lightweight wrapper).

        This uses a simple HTTP wrapper so the provider is optional and
        failures will be caught by the cascading logic.
        """
        import requests
        qwen_key = os.getenv("QWEN_API_KEY")
        qwen_model = os.getenv("LLM_MODEL_QWEN", "qwen-2.1-mini")
        qwen_base = os.getenv("QWEN_API_BASE", "https://api.qwen.ai/v1/chat/completions")
        qwen_temp = float(os.getenv("LLM_TEMPERATURE", "0.25"))

        class QwenWrapper:
            def __init__(self, api_key, model, base, temperature=0.25):
                self.api_key = api_key
                self.model = model
                self.base = base
                self.temperature = temperature

            def invoke(self, prompt_text):
                try:
                    _, msgs = _normalize_prompt(prompt_text)
                    payload = {
                        "model": self.model,
                        "messages": msgs,
                        "temperature": self.temperature,
                    }
                    headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
                    r = requests.post(self.base, json=payload, headers=headers, timeout=120)
                    if r.status_code != 200:
                        raise RuntimeError(f"Qwen API error: {r.status_code} - {r.text[:200]}")
                    data = r.json()
                    # Expecting standard OpenAI-like response structure
                    content = None
                    if isinstance(data, dict):
                        choices = data.get("choices") or data.get("result") or []
                        if isinstance(choices, list) and choices:
                            first = choices[0]
                            content = (first.get("message") or first.get("data") or {}).get("content") if isinstance(first, dict) else None
                    if not content:
                        # try fallback paths
                        content = data.get("text") if isinstance(data, dict) else str(data)
                    class R:
                        def __init__(self, c):
                            self.content = c
                    return R(content)
                except Exception as e:
                    raise RuntimeError(f"Qwen invoke failed: {e}") from e

        return QwenWrapper(qwen_key, qwen_model, qwen_base, qwen_temp)
    
    def _init_google(self):
        """Initialize Google Gemini provider."""
        from langchain_google_genai import GoogleGenerativeAI
        ga_key = _effective_env_value("GOOGLE_AI_API_KEY")
        llm_model = os.getenv("LLM_MODEL_GOOGLE", "gemini-2.0-flash")
        llm_temp = float(os.getenv("LLM_TEMPERATURE", "0.25"))
        return GoogleGenerativeAI(
            model=llm_model,
            temperature=llm_temp,
            google_api_key=ga_key
        )
    
    def invoke(self, prompt: Any):
        """Invoke LLM with automatic provider fallback."""
        providers = self._get_all_providers()
        
        if not providers:
            raise RuntimeError(f"No LLM providers configured for: {self.purpose}")
        
        logger.info("🔄 Cascading LLM for %s - Available: %s", self.purpose, ", ".join(self.provider_names))

        # Optionally bias toward the last successful provider (can be disabled)
        use_bias = os.getenv("LLM_USE_LAST_PROVIDER_BIAS", "true").lower() in ("1", "true", "yes")
        if self.last_working_provider and use_bias:
            # find the provider tuple matching the last working provider and move it to the head
            found = None
            for p in providers:
                if p[0] == self.last_working_provider:
                    found = p
                    break
            if found:
                providers = [found] + [p for p in providers if p[0] != self.last_working_provider]
            else:
                logger.debug("Last working provider '%s' not available for purpose '%s'", self.last_working_provider, self.purpose)
        
        last_error = None
        for provider_name, init_func in providers:
            try:
                logger.info(f"🔹 Trying provider: {provider_name}")
                llm = init_func()
                response = llm.invoke(prompt)
                logger.info(f"✅ Success with {provider_name}")
                self.last_working_provider = provider_name
                return response
            except Exception as e:
                error_short = str(e)[:150]
                logger.warning(f"❌ {provider_name} failed: {error_short}")
                # Print full error for debugging
                last_error = e
                continue
        
        # All providers failed
        logger.error(f"❌ All LLM providers failed for {self.purpose}")
        raise RuntimeError(f"All {len(providers)} LLM providers failed. Last error: {last_error}")


def get_llm(purpose: str = "general", structured_output_schema=None):
    """Get a cascading LLM that automatically tries all providers on failure.
    
    This returns a wrapper that automatically falls back through the provider chain:
    Qwen → Cloudflare → Nebius → Cerebras → Moonshot → NVIDIA → Google Gemini → HuggingFace → OpenRouter → Mistral
    
    Args:
        purpose: Description of what the LLM will be used for (for logging)
        structured_output_schema: Optional Pydantic model for structured output
        
    Returns:
        CascadingLLMWrapper instance that tries all providers sequentially
        
    Raises:
        RuntimeError: If no LLM providers are configured
        
    Example:
        ```python
        from src.agent.llm_provider import get_llm
        
        llm = get_llm(purpose="content generation")
        response = llm.invoke("Write a tweet about AI")
        print(response.content)
        ```
    """
    wrapper = CascadingLLMWrapper(purpose, structured_output_schema)
    
    # Verify at least one provider is configured
    providers = wrapper._get_all_providers()
    if not providers:
        logger.error("❌ No LLM providers configured")
        raise RuntimeError("No LLM providers configured. Set at least one API key: QWEN_API_KEY, CLOUDFLARE_AI_API_KEY, NEBIUS_API_KEY, CEREBRAS_API_KEY, MOONSHOT_API_KEY, NVIDIA_API_KEY, GOOGLE_AI_API_KEY, HF_TOKEN")
    
    logger.info(f"✓ Cascading LLM initialized for {purpose} with {len(providers)} providers: {', '.join([p[0] for p in providers])}")
    cooldown_active = [n for n in COOLDOWN_PROVIDERS if n not in [p[0] for p in providers]]
    dead_blocked = [n for n in DEAD_PROVIDERS if n not in [p[0] for p in providers]]
    if cooldown_active:
        logger.info("🧊 LLMs in cooldown (waiting for quota reset): %s", ", ".join(f"{n} ({COOLDOWN_PROVIDERS[n]})" for n in cooldown_active))
    if dead_blocked:
        logger.info("⛔ LLMs blocked as dead: %s", ", ".join(f"{n} ({DEAD_PROVIDERS[n]})" for n in dead_blocked))
    return wrapper


def get_llm_strict(purpose: str = "general", structured_output_schema=None):
    """Get a cascading LLM provider, raising an error if none are configured.
    
    This is an alias for get_llm() since the cascading wrapper already raises
    an error if no providers are configured.
    
    Args:
        purpose: Description of what the LLM will be used for (for logging)
        structured_output_schema: Optional Pydantic model for structured output
        
    Returns:
        CascadingLLMWrapper instance
        
    Raises:
        RuntimeError: If no LLM providers are configured
    """
    return get_llm(purpose, structured_output_schema)


def list_configured_llm_providers() -> List[Dict[str, str]]:
    """List all LLM providers configured by environment variables."""
    providers: List[Dict[str, str]] = []
    for name, env_key, model_env, default_model in PROVIDER_REGISTRY:
        raw_value = _effective_env_value(env_key)
        if not raw_value:
            continue
        providers.append({
            "name": name,
            "env": env_key,
            "model": os.getenv(model_env, default_model) if model_env else default_model,
        })
    return providers
