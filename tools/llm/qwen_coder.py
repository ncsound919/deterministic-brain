from __future__ import annotations
"""
Qwen3-Coder / llama.cpp LLM service.

Loads a GGUF model via llama-cpp-python (CPU, deterministic settings).
Falls back to a template-based stub when the model file is not present
so the system runs fully offline without a downloaded model.
"""
import os
from typing import Any

try:
    from llama_cpp import Llama
    _LLAMA_OK = True
except ImportError:
    _LLAMA_OK = False


_MODEL_PATH: str = os.getenv('QWEN_MODEL_PATH', '')
_CTX_SIZE: int = int(os.getenv('LLM_CTX_SIZE', '4096'))
_MAX_TOKENS: int = int(os.getenv('LLM_MAX_TOKENS', '512'))
_SEED: int = int(os.getenv('LLM_SEED', '42'))


class QwenCoderService:
    """Thin wrapper around llama-cpp-python for Qwen3-Coder GGUF models."""

    def __init__(self) -> None:
        self._llm: Any | None = None
        if _LLAMA_OK and _MODEL_PATH and os.path.isfile(_MODEL_PATH):
            self._llm = Llama(
                model_path=_MODEL_PATH,
                n_ctx=_CTX_SIZE,
                n_gpu_layers=0,    # CPU only
                seed=_SEED,        # deterministic
                verbose=False,
            )

    @property
    def available(self) -> bool:
        return self._llm is not None

    def generate_code(
        self,
        task_description: str,
        context_snippets: list[str] | None = None,
        max_tokens: int = _MAX_TOKENS,
    ) -> str:
        """Generate Python code for the given task description.

        Returns a code string.  Uses llama.cpp when available,
        falls back to a deterministic template stub otherwise.
        """
        if self._llm is not None:
            prompt = self._build_code_prompt(task_description, context_snippets or [])
            result = self._llm(
                prompt,
                max_tokens=max_tokens,
                temperature=0.0,     # fully deterministic
                top_k=1,
                top_p=1.0,
                repeat_penalty=1.1,
                stop=['<|endoftext|>', '```\n\n'],
            )
            return result['choices'][0]['text'].strip()
        # Stub fallback
        return self._stub_code(task_description)

    def generate_text(
        self,
        prompt: str,
        max_tokens: int = _MAX_TOKENS,
    ) -> str:
        """General text generation (plans, summaries, etc.)."""
        if self._llm is not None:
            result = self._llm(
                prompt,
                max_tokens=max_tokens,
                temperature=0.0,
                top_k=1,
                top_p=1.0,
            )
            return result['choices'][0]['text'].strip()
        return f'[LLM stub] {prompt[:120]}...'

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_code_prompt(self, task: str, snippets: list[str]) -> str:
        ctx = '\n'.join(f'# Context: {s}' for s in snippets[:3])
        return (
            f'{ctx}\n\n'
            f'# Task: {task}\n'
            '# Write clean, well-typed Python code:\n\n'
            '```python\n'
        )

    def _stub_code(self, task: str) -> str:
        """Return a minimal deterministic skeleton when model is unavailable."""
        fn_name = '_'.join(task.lower().split()[:3]).replace('-', '_')
        fn_name = ''.join(c for c in fn_name if c.isalnum() or c == '_') or 'solution'
        return (
            f'def {fn_name}(*args, **kwargs):\n'
            f'    """Auto-generated stub for: {task[:60]}"""\n'
            f'    # TODO: implement\n'
            f'    raise NotImplementedError("{fn_name} not yet implemented")\n'
        )


# Module-level singleton
_service: QwenCoderService | None = None


def get_service() -> QwenCoderService:
    global _service
    if _service is None:
        _service = QwenCoderService()
    return _service
