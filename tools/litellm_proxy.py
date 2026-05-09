"""LiteLLM Unified LLM Proxy — single interface to all your LLM providers.

Routes to: OpenRouter, Anthropic Claude, DeepSeek, Gemini, XAI/Grok, Ollama.
Automatic fallback: if one provider fails, tries the next.
Cost tracking, rate limiting, model selection all in one place.

All API keys read from the credential vault. No keys in code.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from tools.vault_aware_api import get_key

logger = logging.getLogger(__name__)

try:
    import litellm
    litellm.suppress_debug_info = True
    _LITELLM_OK = True
except ImportError:
    _LITELLM_OK = False


# ── Model registry ──────────────────────────────────────────────────────

LITELLM_MODELS = {
    # Provider → model mapping with vault key resolution
    "openrouter": {
        "coding": "openrouter/openai/o3",
        "reasoning": "openrouter/anthropic/claude-opus-4",
        "general": "openrouter/openai/gpt-4o",
        "fast": "openrouter/meta-llama/llama-3.3-70b-instruct",
    },
    "anthropic": {
        "pro": "claude-opus-4-20250514",
        "balanced": "claude-sonnet-4-20250514",
        "fast": "claude-3-5-haiku-20241022",
    },
    "deepseek": {
        "pro": "deepseek/deepseek-chat",
        "reasoning": "deepseek/deepseek-reasoner",
    },
    "gemini": {
        "pro": "gemini/gemini-2.5-pro",
        "flash": "gemini/gemini-2.0-flash",
    },
    "xai": {
        "pro": "xai/grok-2",
        "fast": "xai/grok-2",
    },
    "ollama": {
        "local": "ollama/gemma3:4b",
        "fast": "ollama/gemma3:4b",
    },
}

PROVIDER_PRIORITY = ["openrouter", "anthropic", "deepseek", "gemini", "xai", "ollama"]


class LiteLLMRouter:
    """Unified LLM access with automatic provider fallback.

    Usage:
        router = LiteLLMRouter()
        result = router.complete("Write a Python function to sort a list")
        # Automatically picks best available provider, falls back if needed.
    """

    def __init__(self, default_tier: str = "general"):
        self._default_tier = default_tier
        self._api_keys: Dict[str, str] = {}
        self._load_keys()

    def _load_keys(self):
        vault_map = {
            "openrouter": ("openrouter", "api_key", "OPENROUTER_API_KEY"),
            "anthropic": ("anthropic", "api_key", "ANTHROPIC_API_KEY"),
            "deepseek": ("deepseek", "api_key", "DEEPSEEK_API_KEY"),
            "gemini": ("gemini", "api_key", "GEMINI_API_KEY"),
            "xai": ("xai", "api_key", "XAI_API_KEY"),
        }
        for provider, (cat, key, env) in vault_map.items():
            val = get_key(vault_category=cat, vault_key=key, env_var=env)
            if val:
                self._api_keys[provider] = val
                os_module = __import__("os")
                os_module.environ[f"{provider.upper()}_API_KEY"] = val

        # Special: OpenRouter needs base URL
        if self._api_keys.get("openrouter"):
            import os
            os.environ["OPENROUTER_API_KEY"] = self._api_keys["openrouter"]
            os.environ["OPENROUTER_BASE_URL"] = "https://openrouter.ai/api/v1"

    def _get_model(self, provider: str, tier: str) -> Optional[str]:
        models = LITELLM_MODELS.get(provider, {})
        return models.get(tier) or models.get("general") or models.get("fast")

    def available_providers(self) -> List[str]:
        return [p for p in PROVIDER_PRIORITY if self._api_keys.get(p)]

    def complete(self, prompt: str, tier: str = "",
                 max_tokens: int = 1024, temperature: float = 0.7,
                 system: str = "") -> Dict:
        """Send a prompt to the best available LLM with automatic fallback.

        Tier priority: coding > reasoning > general > fast > local
        Falls back through providers if the primary fails.
        """
        if not _LITELLM_OK:
            return {"ok": False, "error": "litellm not installed. pip install litellm"}

        tier = tier or self._default_tier
        providers = self.available_providers()

        if not providers:
            return {"ok": False, "error": "No LLM providers configured"}

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        errors = []

        # Try primary provider first, then fall back
        for provider in providers:
            model = self._get_model(provider, tier)
            if not model:
                continue

            try:
                response = litellm.completion(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=60,
                )
                text = response.choices[0].message.content
                return {
                    "ok": True,
                    "text": text,
                    "model": model,
                    "provider": provider,
                    "tier": tier,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    },
                }
            except Exception as e:
                errors.append(f"{provider}/{model}: {e}")
                continue

        # All providers failed — try local Ollama as last resort
        try:
            from tools.ollama_client import get_ollama
            ollama_client = get_ollama()
            if ollama_client._check():
                result = ollama_client.chat(prompt, system=system)
                if result.get("ok"):
                    result["provider"] = "ollama"
                    result["tier"] = "local"
                    result["fallback"] = True
                    return result
        except Exception:
            pass

        return {"ok": False, "error": f"All providers failed: {'; '.join(errors)}"}

    def chat(self, messages: List[Dict], tier: str = "general",
             max_tokens: int = 1024, temperature: float = 0.7) -> Dict:
        """Multi-turn chat with automatic fallback."""
        if not _LITELLM_OK:
            return {"ok": False, "error": "litellm not installed"}

        providers = self.available_providers()
        if not providers:
            return {"ok": False, "error": "No LLM providers configured"}

        for provider in providers:
            model = self._get_model(provider, tier)
            if not model:
                continue
            try:
                response = litellm.completion(
                    model=model, messages=messages,
                    max_tokens=max_tokens, temperature=temperature,
                    timeout=60,
                )
                return {
                    "ok": True,
                    "text": response.choices[0].message.content,
                    "model": model, "provider": provider,
                }
            except Exception:
                continue

        return {"ok": False, "error": "All providers failed"}

    def stream(self, prompt: str, tier: str = "general",
               system: str = ""):
        """Stream tokens from the best available provider."""
        if not _LITELLM_OK:
            yield {"ok": False, "error": "litellm not installed"}
            return

        providers = self.available_providers()
        if not providers:
            yield {"ok": False, "error": "No LLM providers configured"}
            return

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        for provider in providers:
            model = self._get_model(provider, tier)
            if not model:
                continue
            try:
                response = litellm.completion(
                    model=model, messages=messages,
                    stream=True, timeout=60,
                )
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        yield {"ok": True, "chunk": chunk.choices[0].delta.content}
                return
            except Exception:
                continue

        yield {"ok": False, "error": "All providers failed"}

    def status(self) -> Dict:
        return {
            "litellm_installed": _LITELLM_OK,
            "providers": self.available_providers(),
            "total_providers": len(self._api_keys),
            "models_by_tier": {
                tier: [
                    m_name
                    for p in PROVIDER_PRIORITY
                    for t, m_name in LITELLM_MODELS.get(p, {}).items()
                    if t == tier
                ]
                for tier in ["coding", "reasoning", "general", "fast"]
            },
        }
