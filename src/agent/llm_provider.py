"""Centralized LLM Provider for FDWA AI Agents.

This module provides a unified interface for accessing multiple LLM providers
with automatic fallback logic. All agents can use this to ensure maximum reliability.

Priority Order:
1. Mistral (Primary - highest quality)
2. OpenRouter Free (Backup 1 - free, good quality)
3. APIFreeLLM (Backup 2 - free unlimited, 25 sec rate limit)
4. Hugging Face (Backup 3 - disabled by default to save quota)
5. Google Gemini (Final fallback)
"""

import logging
import os
from typing import Optional, Any

logger = logging.getLogger(__name__)


class CascadingLLMWrapper:
    """Wrapper that automatically cascades through all available LLM providers on failure."""
    
    def __init__(self, purpose: str = "general", structured_output_schema=None):
        self.purpose = purpose
        self.structured_output_schema = structured_output_schema
        self.last_working_provider = None
        self.provider_names = []
        
    def _get_all_providers(self):
        """Get list of all available LLM providers in priority order."""
        providers = []
        
        # 1. Mistral
        if os.getenv("MISTRAL_API_KEY"):
            providers.append(("Mistral", self._init_mistral))
            
        # 2. OpenRouter
        if os.getenv("OPENROUTER_API_KEY"):
            providers.append(("OpenRouter", self._init_openrouter))
            
        # 3. APIFreeLLM
        if os.getenv("APIFREELLM_API_KEY"):
            providers.append(("APIFreeLLM", self._init_apifreellm))
            
        # 4. Hugging Face (if enabled)
        if os.getenv("HF_ENABLE", "false").lower() in ("1", "true", "yes") and os.getenv("HF_TOKEN"):
            providers.append(("HuggingFace", self._init_huggingface))
            
        # 5. Google Gemini
        if os.getenv("GOOGLE_AI_API_KEY"):
            providers.append(("Google", self._init_google))
            
        self.provider_names = [name for name, _ in providers]
        return providers
    
    def _init_mistral(self):
        """Initialize Mistral provider."""
        from langchain_mistralai import ChatMistralAI
        mistral_key = os.getenv("MISTRAL_API_KEY")
        mistral_model = os.getenv("LLM_MODEL_MISTRAL", "mistral-large-2512")
        mistral_temp = float(os.getenv("LLM_TEMPERATURE", "0.25"))
        
        # Add configurable timeout and max_tokens for cost/performance optimization
        mistral_timeout = int(os.getenv("MISTRAL_TIMEOUT", "60"))  # 60 second default (vs 120s before)
        mistral_max_tokens = int(os.getenv("MISTRAL_MAX_TOKENS", "4096"))  # Reduced from unlimited
        
        # For blog generation, use even more conservative limits
        if "blog" in self.purpose.lower():
            mistral_timeout = int(os.getenv("BLOG_MISTRAL_TIMEOUT", "90"))  # 90s for blogs
            mistral_max_tokens = int(os.getenv("BLOG_MAX_TOKENS", "3000"))  # 3000 tokens ≈ 2000 words (plenty for blogs)
        
        llm = ChatMistralAI(
            model=mistral_model,
            temperature=mistral_temp,
            mistral_api_key=mistral_key,
            request_timeout=mistral_timeout,
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
    
    def _init_apifreellm(self):
        """Initialize APIFreeLLM provider."""
        import requests
        apifreellm_key = os.getenv("APIFREELLM_API_KEY")
        apifreellm_temp = float(os.getenv("LLM_TEMPERATURE", "0.25"))

        class APIFreeLLMWrapper:
            """Wrapper for APIFreeLLM.com API with .invoke() interface for compatibility."""
            def __init__(self, api_key, temperature=0.7):
                self.api_key = api_key
                self.temperature = temperature
                self.endpoint = "https://apifreellm.com/api/v1/chat"

            def invoke(self, prompt_text: str):
                try:
                    response = requests.post(
                        self.endpoint,
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {self.api_key}"
                        },
                        json={
                            "message": prompt_text,
                            "model": "apifreellm"
                        },
                        timeout=120
                    )
                    
                    if response.status_code == 429:
                        raise RuntimeError("APIFreeLLM rate limit: wait 25 seconds")
                    if response.status_code == 401:
                        raise RuntimeError("APIFreeLLM: Invalid API key")
                    if response.status_code != 200:
                        raise RuntimeError(f"APIFreeLLM API error: {response.status_code} - {response.text}")
                    
                    data = response.json()
                    if not data.get("success"):
                        raise RuntimeError(f"APIFreeLLM request failed: {data}")
                    
                    content = data.get("response", "")
                    if not content or not content.strip():
                        raise RuntimeError("APIFreeLLM returned empty content")
                    
                    # Return object with .content attribute for compatibility
                    class _R:
                        def __init__(self, c):
                            self.content = c
                    
                    return _R(content)
                    
                except requests.exceptions.RequestException as e:
                    raise RuntimeError(f"APIFreeLLM request failed: {e}") from e

        return APIFreeLLMWrapper(apifreellm_key, apifreellm_temp)
    
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

            def invoke(self, prompt_text: str):
                try:
                    completion = self.client.chat_completion(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You are a technical writer. Always respond with valid JSON only."},
                            {"role": "user", "content": prompt_text}
                        ],
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
    
    def _init_google(self):
        """Initialize Google Gemini provider."""
        from langchain_google_genai import GoogleGenerativeAI
        ga_key = os.getenv("GOOGLE_AI_API_KEY")
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
        
        logger.info(f"🔄 Cascading LLM for {self.purpose} - Available: {', '.join(self.provider_names)}")
        
        # Try last working provider first if we have one
        if self.last_working_provider:
            providers = [(self.last_working_provider, providers[0][1])] + [p for p in providers if p[0] != self.last_working_provider]
        
        last_error = None
        for provider_name, init_func in providers:
            try:
                logger.info(f"🔹 Trying provider: {provider_name}")
                print(f"🔹 Trying provider: {provider_name}")  # Console output for visibility
                llm = init_func()
                response = llm.invoke(prompt)
                logger.info(f"✅ Success with {provider_name}")
                print(f"✅ Success with {provider_name}")  # Console output for visibility
                self.last_working_provider = provider_name
                return response
            except Exception as e:
                error_short = str(e)[:150]
                logger.warning(f"❌ {provider_name} failed: {error_short}")
                # Print full error for debugging
                print(f"   DEBUG - Full error: {type(e).__name__}: {str(e)}")
                last_error = e
                continue
        
        # All providers failed
        logger.error(f"❌ All LLM providers failed for {self.purpose}")
        raise RuntimeError(f"All {len(providers)} LLM providers failed. Last error: {last_error}")


def get_llm(purpose: str = "general", structured_output_schema=None):
    """Get a cascading LLM that automatically tries all providers on failure.
    
    This returns a wrapper that automatically falls back through the provider chain:
    Mistral → OpenRouter → APIFreeLLM → HuggingFace → Google Gemini
    
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
        raise RuntimeError(f"No LLM providers configured. Set at least one API key: MISTRAL_API_KEY, OPENROUTER_API_KEY, APIFREELLM_API_KEY, GOOGLE_AI_API_KEY")
    
    logger.info(f"✓ Cascading LLM initialized for {purpose} with {len(providers)} providers: {', '.join([p[0] for p in providers])}")
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
