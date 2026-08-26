"""GoTier client — funded opencode Go tier for the deterministic brain.

Per fleet OPS: the fleet ALWAYS uses the opencode Go tier (deepseek-v4-flash,
0731) as the funded LLM budget. This client routes brain LLM calls there:

  1. LiteLLM gateway  http://localhost:4100/v1/chat/completions  (model `opencode`)
  2. Direct Go tier   https://opencode.ai/zen/go/v1/chat/completions (deepseek-v4-flash)

Both speak the OpenAI chat-completions contract. Deterministic by default:
temperature 0.1, seed 42. Fail-soft — returns "" / {} on any error so the
pipeline never stalls on a wallet/balance/network problem.

Intentionally NOT in tools/llm/router.py's local-first priority as a *first*
choice: local inference is free, the Go tier is the funded budget, so local
wins when a capable model is present and Go tier covers the gap.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from tools.vault_aware_api import get_key

logger = logging.getLogger(__name__)

try:
    import requests
    _REQUESTS_OK = True
except ImportError:  # pragma: no cover
    _REQUESTS_OK = False
    requests = None  # type: ignore

# --- Env-driven config -------------------------------------------------------
LITELLM_GATEWAY_URL = os.getenv(
    "LITELLM_GATEWAY_URL", os.getenv("LITELLM_URL", "http://localhost:4100")
).rstrip("/")
LITELLM_MODEL = os.getenv("LITELLM_MODEL", "opencode")
DIRECT_GO_URL = os.getenv(
    "OPENCODE_GO_URL", "https://opencode.ai/zen/go/v1/chat/completions"
)
DIRECT_GO_MODEL = os.getenv("OPENCODE_GO_MODEL", "deepseek-v4-flash")
DEFAULT_TEMPERATURE = 0.1
DEFAULT_SEED = 42
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TIMEOUT = 60


def _resolve_key() -> str:
    """OpenCode Go key: env OPENCODE_API_KEY → LITELLM_API_KEY → vault."""
    for env in ("OPENCODE_API_KEY", "LITELLM_API_KEY"):
        v = os.getenv(env, "")
        if v:
            return v
    return get_key(
        vault_category="opencode", vault_key="api_key", env_var="OPENCODE_API_KEY"
    )


class GoTierClient:
    """Funded opencode Go tier via LiteLLM gateway, then direct zen/go.

    Attributes:
        litellm_url: LiteLLM gateway base URL (default localhost:4100).
        litellm_model: Model name the gateway expects (default 'opencode').
        direct_url: Direct Go-tier chat-completions URL.
        direct_model: Model name for direct calls (default 'deepseek-v4-flash').
    """

    name = "gotier"

    def __init__(
        self,
        litellm_url: str = LITELLM_GATEWAY_URL,
        litellm_model: str = LITELLM_MODEL,
        direct_url: str = DIRECT_GO_URL,
        direct_model: str = DIRECT_GO_MODEL,
    ) -> None:
        self.litellm_url = litellm_url
        self.litellm_model = litellm_model
        self.direct_url = direct_url
        self.direct_model = direct_model
        self.api_key = _resolve_key()
        self._gateway_up: Optional[bool] = None

    # ------------------------------------------------------------------ intro

    @property
    def available(self) -> bool:
        """True when the Go tier is usable: key present or gateway reachable.

        The gateway may run keyless in the fleet (LiteLLM routes by model name),
        so a live gateway without an explicit key still counts as available.
        Cached per-process to keep availability checks cheap.
        """
        if self.api_key:
            return True
        if self._gateway_up is not None:
            return self._gateway_up
        self._gateway_up = self._probe_gateway()
        return bool(self._gateway_up)

    def _probe_gateway(self) -> bool:
        if not _REQUESTS_OK:
            return False
        try:
            resp = requests.get(f"{self.litellm_url}/v1/models", timeout=3)
            return resp.status_code < 500
        except Exception:
            return False

    # -------------------------------------------------------------- transport

    def _post(
        self, base_url: str, model: str, messages: List[Dict[str, str]],
        max_tokens: int, temperature: float,
    ) -> Optional[Dict[str, Any]]:
        if not _REQUESTS_OK:
            logger.warning("[gotier] requests not installed")
            return None
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "seed": DEFAULT_SEED,
            "stream": False,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            resp = requests.post(
                f"{base_url}", json=payload, headers=headers, timeout=DEFAULT_TIMEOUT
            )
            if resp.status_code >= 400:
                logger.warning("[gotier] HTTP %s: %s", resp.status_code, resp.text[:200])
                return None
            return resp.json()
        except Exception as e:  # noqa: BLE001
            logger.warning("[gotier] request failed: %s", e)
            return None

    def _complete(
        self, messages: List[Dict[str, str]], max_tokens: int, temperature: float
    ) -> str:
        """LiteLLM gateway first, then direct Go tier. Fail-soft → ''."""
        # 1. LiteLLM gateway (healthy primary per OPS).
        data = self._post(
            f"{self.litellm_url}/v1/chat/completions", self.litellm_model,
            messages, max_tokens, temperature,
        )
        if data:
            content = self._extract_content(data)
            if content:
                return content
        # 2. Direct Go tier.
        data = self._post(self.direct_url, self.direct_model,
                          messages, max_tokens, temperature)
        if data:
            return self._extract_content(data) or ""
        return ""

    @staticmethod
    def _extract_content(data: Dict[str, Any]) -> str:
        try:
            return (data.get("choices", [{}])[0]
                    .get("message", {}).get("content") or "").strip()
        except Exception:
            return ""

    # ------------------------------------------------------------------ api

    def chat(self, system: str, user: str, max_tokens: int = DEFAULT_MAX_TOKENS,
             temperature: float = DEFAULT_TEMPERATURE, use_cot: bool = False) -> str:
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        content = self._complete(messages, max_tokens, temperature)
        if not content and use_cot:
            # Some reasoning models put the answer inside the reasoning field.
            data = self._post(
                f"{self.litellm_url}/v1/chat/completions", self.litellm_model,
                messages, max_tokens, temperature,
            )
            if data:
                reasoning = (data.get("choices", [{}])[0]
                             .get("message", {}).get("reasoning") or "").strip()
                if reasoning:
                    return f"<thinking>\n{reasoning}\n</thinking>\n\n"
        return content

    def complete(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                 temperature: float = DEFAULT_TEMPERATURE) -> str:
        return self.chat("", prompt, max_tokens=max_tokens, temperature=temperature)

    def generate_text(self, prompt: str, system: Optional[str] = None,
                      max_tokens: int = DEFAULT_MAX_TOKENS,
                      temperature: float = DEFAULT_TEMPERATURE) -> str:
        if system:
            return self.chat(system, prompt, max_tokens=max_tokens, temperature=temperature)
        return self.complete(prompt, max_tokens=max_tokens, temperature=temperature)

    def generate_json(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                      temperature: float = DEFAULT_TEMPERATURE) -> Dict[str, Any]:
        system = ("You are a deterministic JSON generator. Reply with ONLY valid JSON. "
                  "No prose, no markdown fences, no explanation.")
        content = self.chat(system, prompt, max_tokens=max_tokens, temperature=temperature)
        from tools.local_model import _extract_dict
        parsed = _extract_dict(content)
        if parsed is not None:
            return parsed
        return {}

    def complete_with_cot(self, system: str, user: str,
                          max_tokens: int = DEFAULT_MAX_TOKENS) -> tuple[str, str]:
        """Chain-of-thought: reason in <thinking>, then final answer."""
        raw = self.chat(system, user, max_tokens=max_tokens, use_cot=True)
        if not raw:
            return "", ""
        if "<thinking>" in raw and "</thinking>" in raw:
            start = raw.index("<thinking>") + len("<thinking>")
            end = raw.index("</thinking>")
            scratchpad = raw[start:end].strip()
            answer = raw[end + len("</thinking>"):].strip()
            return scratchpad, answer
        return "", raw.strip()


# Module-level singleton
_client: Optional[GoTierClient] = None


def get_gotier() -> GoTierClient:
    global _client
    if _client is None:
        _client = GoTierClient()
    return _client


def reset_gotier() -> None:
    global _client
    _client = None
