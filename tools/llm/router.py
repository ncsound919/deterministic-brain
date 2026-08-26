"""
LLM Router — dispatches generation requests to the right backbone.

Priority order:
  1. Unified local model service (Ollama → llama-server → llama.cpp in-process)
  2. opencode Go tier (funded LLM budget) via LiteLLM gateway :4100 → direct zen/go
  3. OpenRouter (if OPENROUTER_API_KEY is set)
  4. Local llama.cpp via QwenCoderService (if QWEN_MODEL_PATH is set)
  5. Deterministic stub fallback

All callers should import from here rather than hitting individual
client modules directly.  This keeps the lane code clean and makes
backbone swaps a config-only change.

Local-first: the unified `tools.local_model` service auto-detects which local
backend is actually running with a model installed, so calls succeed offline
without any API keys. When local is unavailable, calls fall to the funded
opencode Go tier (never the premium OpenRouter defaults) before other remotes.
"""
from __future__ import annotations
import os

from tools.llm.openrouter_client import get_client as get_or
from tools.llm.opencode_client   import get_opencode
from tools.llm.qwen_coder        import get_service as get_qwen
from tools.local_gemma           import get_gemma, LocalGemmaClient
from tools.local_model           import get_local_model
from tools.llm.gotier_client     import get_gotier


def _llm_disabled() -> bool:
    """Kill-switch: BRAIN_DISABLE_LLM=1 forces the deterministic stub path.

    Mirrors ENABLE_ULTRAPLAN: deterministic core by default, LLM routing
    opt-in. Tests set this so suites never depend on live inference speed.
    """
    return os.getenv("BRAIN_DISABLE_LLM", "").lower() in ("1", "true", "yes")


def _local_available() -> bool:
    """True when a real local backend is up with at least one model."""
    try:
        return get_local_model().is_available()
    except Exception:
        return False


def generate_code(
    task: str,
    context_snippets: list[str] | None = None,
    repair_errors: list[str] | None = None,
    repair_tests:  list[str] | None = None,
    repair_attempt: int = 0,
) -> str:
    """
    Generate (or repair) Python code.
    Uses Local model > Go tier > Gemma > OpenCode > Qwen > stub.
    """
    prompt = task
    if context_snippets:
        prompt = f"Context:\n" + "\n".join(f"- {s}" for s in context_snippets) + f"\n\nTask: {task}"
    if repair_errors:
        prompt += f"\n\nErrors to fix:\n" + "\n".join(f"- {e}" for e in repair_errors)
        if repair_tests:
            prompt += f"\n\nTests that must pass:\n" + "\n".join(f"- {t}" for t in repair_tests)

    if _llm_disabled():
        return get_qwen().generate_code(task)  # deterministic stub

    local = get_local_model()
    if local.is_available():
        sys_prompt = (
            "You are an expert software engineer. Write clean, production-quality Python code. "
            "Return ONLY the raw Python code, no markdown fences."
        )
        result = local.chat(sys_prompt, prompt, max_tokens=256, temperature=0.1)
        if result:
            return result

    # 1b. Funded opencode Go tier for codegen (LiteLLM :4100 → direct zen/go).
    gotier = get_gotier()
    if gotier.available:
        sys_prompt = (
            "You are an expert software engineer. Write clean, production-quality Python code. "
            "Return ONLY the raw Python code, no markdown fences."
        )
        result = gotier.chat(sys_prompt, prompt, max_tokens=256, temperature=0.1)
        if result:
            return result

    gemma = get_gemma()
    if gemma.is_available():
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
    Uses Local model > OpenRouter > Qwen > stub.
    """
    if _llm_disabled():
        result = get_qwen().generate_text(prompt)
        return ('', result) if use_cot else result

    # 1. Unified local model service first (real model detection, no keys needed)
    local = get_local_model()
    if local.is_available():
        if use_cot:
            return local.complete_with_cot(system or "", prompt, max_tokens=max_tokens)
        result = local.generate_text(prompt, system=system, max_tokens=max_tokens)
        if result:
            return result

    # 1b. Funded opencode Go tier (LiteLLM :4100 → direct zen/go) before any
    #     premium OpenRouter model — the fleet's funded LLM budget.
    gotier = get_gotier()
    if gotier.available:
        if use_cot:
            result = gotier.complete_with_cot(system or "", prompt, max_tokens=max_tokens)
        else:
            result = gotier.generate_text(prompt, system=system, max_tokens=max_tokens)
        if result:
            return result

    # 2. Local Gemma via Ollama (legacy direct client)
    gemma = get_gemma()
    if gemma.is_available():
        full_prompt = (f"{system}\n\n{prompt}" if system else prompt)
        result = gemma.complete(full_prompt, n_predict=min(max_tokens, 256), temperature=0.1)
        if result:
            if use_cot:
                return '', result
            return result

    # 3. OpenRouter fallback
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

    # 4. Qwen fallback
    qwen = get_qwen()
    result = qwen.generate_text(prompt)
    if use_cot:
        return '', result
    return result


def generate_json(
    prompt: str,
    lane: str = 'default',
    system: str | None = None,
    max_tokens: int = 2048,
) -> dict:
    """
    Structured JSON generation — best-effort dict return.

    Uses the unified local model service (JSON repair + retry built in),
    then falls back to OpenRouter, then a stub dict.
    """
    if _llm_disabled():
        return {}

    local = get_local_model()
    if local.is_available():
        result = local.generate_json(prompt, max_tokens=max_tokens)
        if result:
            return result

    gotier = get_gotier()
    if gotier.available:
        result = gotier.generate_json(prompt, max_tokens=max_tokens)
        if result:
            return result

    or_client = get_or()
    if or_client.available:
        sys_msg = system or (
            "You are a deterministic JSON generator. Reply with ONLY valid JSON. "
            "No prose, no markdown fences."
        )
        raw = or_client.chat(system=sys_msg, user=prompt, lane=lane, max_tokens=max_tokens)
        try:
            import json as _json
            text = raw.strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json"):
                    text = text[4:].strip()
            parsed = _json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    return {}


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
