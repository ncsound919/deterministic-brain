from __future__ import annotations
"""
OpenRouter client — unified access to all frontier models via a single API key.

Uses the OpenAI-compatible SDK since OpenRouter exposes an OpenAI-compatible
endpoint at https://openrouter.ai/api/v1
"""
import os
from typing import Any

try:
    from openai import OpenAI
    _OAI_OK = True
except ImportError:
    _OAI_OK = False

_API_KEY: str = os.getenv('OPENROUTER_API_KEY', '')
_BASE_URL: str = 'https://openrouter.ai/api/v1'
_SITE_URL: str = os.getenv('OPENROUTER_SITE_URL', 'https://github.com/ncsound919/deterministic-brain')
_SITE_NAME: str = os.getenv('OPENROUTER_SITE_NAME', 'deterministic-brain')
_DEFAULT_MAX_TOKENS: int = int(os.getenv('LLM_MAX_TOKENS', '2048'))
_SEED: int = int(os.getenv('LLM_SEED', '42'))

# ---------------------------------------------------------------------------
# Per-lane model routing
# ---------------------------------------------------------------------------
# These can all be overridden via environment variables.
LANE_MODELS: dict[str, str] = {
    'coding':         os.getenv('MODEL_CODING',         'openai/o3'),
    'business_logic': os.getenv('MODEL_BUSINESS_LOGIC', 'anthropic/claude-opus-4'),
    'agent_brain':    os.getenv('MODEL_AGENT_BRAIN',    'anthropic/claude-sonnet-4-5'),
    'tool_calling':   os.getenv('MODEL_TOOL_CALLING',   'meta-llama/llama-3.3-70b-instruct'),
    'cross_domain':   os.getenv('MODEL_CROSS_DOMAIN',   'google/gemini-2.5-pro'),
    'default':        os.getenv('MODEL_DEFAULT',        'openai/gpt-4o'),
}


class OpenRouterClient:
    """Thin wrapper around OpenRouter's OpenAI-compatible API."""

    def __init__(self) -> None:
        self._client: Any | None = None
        if _OAI_OK and _API_KEY:
            self._client = OpenAI(
                api_key=_API_KEY,
                base_url=_BASE_URL,
                default_headers={
                    'HTTP-Referer': _SITE_URL,
                    'X-Title': _SITE_NAME,
                },
            )

    @property
    def available(self) -> bool:
        return self._client is not None

    def complete(
        self,
        messages: list[dict],
        lane: str = 'default',
        model: str | None = None,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        temperature: float = 0.0,
        stream: bool = False,
    ) -> str:
        """
        Send a chat completion request.

        Args:
            messages:   OpenAI-format message list.
            lane:       Used to pick the per-lane model unless model is given.
            model:      Override the model directly.
            max_tokens: Max tokens in the response.
            temperature: 0.0 = fully deterministic.
            stream:     Return streamed text (joined) if True.

        Returns:
            The assistant reply as a plain string.
        """
        if not self.available:
            return self._stub(messages)

        chosen_model = model or LANE_MODELS.get(lane, LANE_MODELS['default'])

        kwargs: dict[str, Any] = dict(
            model=chosen_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            seed=_SEED,
            stream=stream,
        )

        if stream:
            parts = []
            for chunk in self._client.chat.completions.create(**kwargs):
                delta = chunk.choices[0].delta.content or ''
                parts.append(delta)
            return ''.join(parts)

        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ''

    def complete_with_cot(
        self,
        system: str,
        user: str,
        lane: str = 'default',
        model: str | None = None,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> tuple[str, str]:
        """
        Two-turn chain-of-thought completion.

        First asks the model to reason step-by-step, then asks it to
        produce a final clean answer.  Returns (scratchpad, final_answer).
        """
        cot_messages = [
            {'role': 'system', 'content': system},
            {'role': 'user',   'content': user},
            {'role': 'user',   'content': 'First, reason step by step inside <thinking> tags. Then provide your final answer after </thinking>.'},
        ]
        raw = self.complete(cot_messages, lane=lane, model=model, max_tokens=max_tokens)

        # Split scratchpad from final answer
        if '<thinking>' in raw and '</thinking>' in raw:
            start = raw.index('<thinking>') + len('<thinking>')
            end   = raw.index('</thinking>')
            scratchpad  = raw[start:end].strip()
            final_answer = raw[end + len('</thinking>'):].strip()
        else:
            scratchpad   = ''
            final_answer = raw.strip()

        return scratchpad, final_answer

    # ------------------------------------------------------------------
    # Convenience wrappers
    # ------------------------------------------------------------------

    def generate_text(self, prompt: str, lane: str = 'default', max_tokens: int = _DEFAULT_MAX_TOKENS) -> str:
        messages = [{'role': 'user', 'content': prompt}]
        return self.complete(messages, lane=lane, max_tokens=max_tokens)

    def chat(self, system: str, user: str, lane: str = 'default', max_tokens: int = _DEFAULT_MAX_TOKENS) -> str:
        messages = [
            {'role': 'system', 'content': system},
            {'role': 'user',   'content': user},
        ]
        return self.complete(messages, lane=lane, max_tokens=max_tokens)

    # ------------------------------------------------------------------
    # Stub fallback when API key is missing
    # ------------------------------------------------------------------

    @staticmethod
    def _stub(messages: list[dict]) -> str:
        last = messages[-1].get('content', '') if messages else ''
        return f'[OpenRouter stub — set OPENROUTER_API_KEY] {str(last)[:120]}'


# Module-level singleton
_client: OpenRouterClient | None = None


def get_client() -> OpenRouterClient:
    global _client
    if _client is None:
        _client = OpenRouterClient()
    return _client
