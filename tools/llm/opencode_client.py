from __future__ import annotations
"""
OpenCode client — specialised coding backbone routed through OpenRouter.

OpenCode (opencode/opencode) is a state-of-the-art open coding model.
This module wraps it with coding-specific prompt templates and a
self-repair loop that feeds test failures back into the model.
"""
import os
from tools.llm.openrouter_client import get_client, LANE_MODELS

_MODEL: str = os.getenv('MODEL_OPENCODE', 'openai/o3')  # override with opencode/opencode when available on OpenRouter
_MAX_TOKENS: int = int(os.getenv('LLM_MAX_TOKENS', '2048'))


_SYSTEM_PROMPT = """You are OpenCode, an expert software engineer.
Write clean, production-quality Python code.
Rules:
- Always include a function signature with type hints.
- Include a docstring.
- Handle edge cases.
- Do NOT include explanation prose outside the code block.
Return ONLY the raw Python code, no markdown fences."""


class OpenCodeClient:
    """Coding-specialist LLM backed by OpenCode via OpenRouter."""

    def __init__(self) -> None:
        self._or = get_client()
        self._model = _MODEL

    @property
    def available(self) -> bool:
        return self._or.available

    def generate_code(
        self,
        task: str,
        context_snippets: list[str] | None = None,
        max_tokens: int = _MAX_TOKENS,
    ) -> str:
        """Generate Python code for the given task."""
        ctx_block = ''
        if context_snippets:
            ctx_block = 'Relevant context:\n' + '\n'.join(f'  - {s}' for s in context_snippets[:5]) + '\n\n'

        user_msg = f"{ctx_block}Task: {task}\n\nWrite the Python implementation:"

        messages = [
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            {'role': 'user',   'content': user_msg},
        ]
        return self._or.complete(
            messages,
            model=self._model,
            max_tokens=max_tokens,
            temperature=0.0,
        )

    def repair_code(
        self,
        code: str,
        errors: list[str],
        tests: list[str],
        attempt: int = 0,
        max_tokens: int = _MAX_TOKENS,
    ) -> str:
        """Feed test failures back to the model for self-repair."""
        error_block = '\n'.join(errors)
        test_block  = '\n'.join(tests)
        user_msg = (
            f'The following Python code failed its tests (attempt {attempt + 1}):\n\n'
            f'```python\n{code}\n```\n\n'
            f'Errors:\n{error_block}\n\n'
            f'Tests that must pass:\n{test_block}\n\n'
            'Fix the code. Return ONLY the corrected Python code, no markdown fences.'
        )
        messages = [
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            {'role': 'user',   'content': user_msg},
        ]
        return self._or.complete(
            messages,
            model=self._model,
            max_tokens=max_tokens,
            temperature=0.0,
        )

    def generate_text(
        self,
        prompt: str,
        max_tokens: int = _MAX_TOKENS,
    ) -> str:
        """General text generation using the coding model."""
        return self._or.generate_text(prompt, lane='coding', max_tokens=max_tokens)


# Module-level singleton
_client: OpenCodeClient | None = None


def get_opencode() -> OpenCodeClient:
    global _client
    if _client is None:
        _client = OpenCodeClient()
    return _client
