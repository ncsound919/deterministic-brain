from __future__ import annotations
"""
LLM Router — dispatches generation requests to the right backbone.

Priority order:
  1. Local Gemma 3n E4B via llama-server (if running at GEMMA_BASE_URL)
  2. OpenRouter (if OPENROUTER_API_KEY is set)
  3. Local llama.cpp via QwenCoderService (if QWEN_MODEL_PATH is set)
  4. Deterministic stub fallback

All callers should import from here rather than hitting individual
client modules directly.  This keeps the lane code clean and makes
backbone swaps a config-only change.
"""
from tools.llm.openrouter_client import get_client as get_or
from tools.llm.opencode_client   import get_opencode
from tools.llm.qwen_coder        import get_service as get_qwen
from tools.local_gemma           import get_gemma, LocalGemmaClient


def generate_code(
    task: str,
    context_snippets: list[str] | None = None,
    repair_errors: list[str] | None = None,
    repair_tests:  list[str] | None = None,
    repair_attempt: int = 0,
) -> str:
    """
    Generate (or repair) Python code.
    Uses Local Gemma > OpenCode > Qwen > stub, in that priority order.
    """
    gemma = get_gemma()
    if gemma.is_available():
        prompt = task
        if context_snippets:
            prompt = f"Context:\n" + "\n".join(f"- {s}" for s in context_snippets) + f"\n\nTask: {task}"
        if repair_errors:
            prompt += f"\n\nErrors to fix:\n" + "\n".join(f"- {e}" for e in repair_errors)
            if repair_tests:
                prompt += f"\n\nTests that must pass:\n" + "\n".join(f"- {t}" for t in repair_tests)
        result = gemma.complete(prompt, n_predict=256, temperature=0.1)
        if result:
            return result

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
    Uses Local Gemma > OpenRouter > Qwen > stub.
    """
    # 1. Try local Gemma first (fastest, free, deterministic)
    gemma = get_gemma()
    if gemma.is_available():
        full_prompt = (f"{system}\n\n{prompt}" if system else prompt)
        result = gemma.complete(full_prompt, n_predict=min(max_tokens, 256), temperature=0.1)
        if result:
            if use_cot:
                return '', result
            return result

    # 2. OpenRouter fallback
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

    # 3. Qwen fallback
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
