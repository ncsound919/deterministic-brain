from __future__ import annotations
"""
LLM Router — dispatches generation requests to the right backbone.

Priority order:
  1. OpenRouter (if OPENROUTER_API_KEY is set)
  2. Local llama.cpp via QwenCoderService (if QWEN_MODEL_PATH is set)
  3. Deterministic stub fallback

All callers should import from here rather than hitting individual
client modules directly.  This keeps the lane code clean and makes
backbone swaps a config-only change.
"""
from __future__ import annotations
from tools.llm.openrouter_client import get_client as get_or
from tools.llm.opencode_client   import get_opencode
from tools.llm.qwen_coder        import get_service as get_qwen


def generate_code(
    task: str,
    context_snippets: list[str] | None = None,
    repair_errors: list[str] | None = None,
    repair_tests:  list[str] | None = None,
    repair_attempt: int = 0,
) -> str:
    """
    Generate (or repair) Python code.
    Uses OpenCode > Qwen > stub, in that priority order.
    """
    oc = get_opencode()
    if oc.available:
        if repair_errors:
            return oc.repair_code(
                task,
                errors=repair_errors,
                tests=repair_tests or [],
                attempt=repair_attempt,
            )
        return oc.generate_code(task, context_snippets=context_snippets)

    qwen = get_qwen()
    if qwen.available:
        return qwen.generate_code(task, context_snippets=context_snippets or [])

    return qwen.generate_code(task)  # returns deterministic stub


def generate_text(
    prompt: str,
    lane: str = 'default',
    system: str | None = None,
    max_tokens: int = 2048,
    use_cot: bool = False,
) -> str | tuple[str, str]:
    """
    General text generation.
    Returns str normally, or (scratchpad, answer) when use_cot=True.
    Uses OpenRouter > Qwen > stub.
    """
    or_client = get_or()
    if or_client.available:
        if use_cot and system:
            return or_client.complete_with_cot(
                system=system,
                user=prompt,
                lane=lane,
                max_tokens=max_tokens,
            )
        if system:
            return or_client.chat(system=system, user=prompt, lane=lane, max_tokens=max_tokens)
        return or_client.generate_text(prompt, lane=lane, max_tokens=max_tokens)

    qwen = get_qwen()
    result = qwen.generate_text(prompt)
    if use_cot:
        return '', result
    return result


def chat(
    system: str,
    user: str,
    lane: str = 'default',
    max_tokens: int = 2048,
) -> str:
    """Convenience: system + user message, returns assistant reply."""
    result = generate_text(user, lane=lane, system=system, max_tokens=max_tokens)
    if isinstance(result, tuple):
        return result[1]
    return result
