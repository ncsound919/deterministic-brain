"""Unified Local Model Service.

Single entry point for ALL local inference across the deterministic brain.

Auto-detects and prioritises local backends:
  1. Ollama      — http://127.0.0.1:11434  (OpenAI-compatible /v1 API)   [primary]
  2. llama-server — llama.cpp OpenAI-compatible server (default :8082)   [secondary]
  3. llama.cpp   — in-process GGUF via llama-cpp-python (CPU)            [last resort]

Every backend speaks the OpenAI-compatible chat-completions contract, so the
service exposes one backend-agnostic API:

    status()                → per-backend health + installed models
    list_models()           → all discovered local models
    is_available()          → any backend up with at least one model
    chat(system, user)      → assistant reply
    complete(prompt)        → raw completion
    generate_text(prompt)   → plain text generation
    generate_json(prompt)   → structured JSON (with repair + retry)
    complete_with_cot(...)  → (scratchpad, answer)
    ensure_model(name)      → pull/install a missing Ollama model

Deterministic by default: temperature 0.1, seed 42, top_k 1, repeat_penalty 1.1.
Never raises on backend failure — returns "" or {} so the pipeline never stalls.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import requests
    _REQUESTS_OK = True
except ImportError:  # pragma: no cover
    _REQUESTS_OK = False
    requests = None  # type: ignore

# ---------------------------------------------------------------------------
# Defaults & env-driven configuration
# ---------------------------------------------------------------------------

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_LLAMA_SERVER_URL = "http://127.0.0.1:8082"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_SEED = 42
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TIMEOUT = 120

# Ordered preference when no explicit LOCAL_MODEL_NAME is set.
# Names are matched by case-insensitive substring against installed models.
# 2026-08-24 roster: qwen3.5:4b is the mid/vision/reasoning workhorse,
# phi4-mini the terse backup, medgemma:4b the biomed specialist.
DEFAULT_MODEL_PREFERENCE: List[str] = [
    os.getenv("LOCAL_MODEL_NAME", ""),
    os.getenv("OLLAMA_MODEL", ""),
    "qwen3.5",
    "phi4-mini",
    "medgemma",
    "qwen3",
]
# Filter empty preference entries lazily at runtime.
DEFAULT_MODEL_PREFERENCE = [m for m in DEFAULT_MODEL_PREFERENCE if m]


def _env(key: str, default: str) -> str:
    return os.getenv(key, os.getenv(key.upper(), default))


# ---------------------------------------------------------------------------
# Backend base
# ---------------------------------------------------------------------------

class LocalModelBackend:
    """Base class for a local inference backend."""

    name = "base"
    base_url = ""

    def __init__(self) -> None:
        self._last_error: str = ""
        self._cache: Dict[str, Any] = {}

    @property
    def last_error(self) -> str:
        return self._last_error

    def _post(self, path: str, payload: Dict[str, Any], timeout: int = DEFAULT_TIMEOUT) -> Optional[Dict[str, Any]]:
        if not _REQUESTS_OK:
            self._last_error = "requests not installed"
            return None
        try:
            resp = requests.post(
                f"{self.base_url}{path}",
                json=payload,
                timeout=timeout,
            )
            if resp.status_code >= 400:
                self._last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                return None
            return resp.json()
        except Exception as e:  # noqa: BLE001 - never crash the brain
            self._last_error = str(e)
            return None

    def _get(self, path: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
        if not _REQUESTS_OK:
            self._last_error = "requests not installed"
            return None
        try:
            resp = requests.get(f"{self.base_url}{path}", timeout=timeout)
            if resp.status_code >= 400:
                self._last_error = f"HTTP {resp.status_code}"
                return None
            return resp.json()
        except Exception as e:  # noqa: BLE001
            self._last_error = str(e)
            return None

    # ---- Overridden by subclasses ----
    def is_available(self) -> bool:
        return False

    def list_models(self) -> List[str]:
        return []

    def chat(self, system: str, user: str, max_tokens: int = DEFAULT_MAX_TOKENS,
             temperature: float = DEFAULT_TEMPERATURE, use_cot: bool = False) -> str:
        raise NotImplementedError

    def complete(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                 temperature: float = DEFAULT_TEMPERATURE) -> str:
        raise NotImplementedError

    def generate_json(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                      temperature: float = DEFAULT_TEMPERATURE,
                      fast: bool = False) -> Dict[str, Any]:
        raise NotImplementedError

    def ensure_model(self, name: str) -> Dict[str, Any]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Ollama backend
# ---------------------------------------------------------------------------

class OllamaBackend(LocalModelBackend):
    """Local inference via Ollama (OpenAI-compatible /v1 API + native /api)."""

    name = "ollama"

    def __init__(self, base_url: str | None = None) -> None:
        super().__init__()
        self.base_url = (base_url or _env("OLLAMA_BASE_URL", _env("GEMMA_BASE_URL", DEFAULT_OLLAMA_URL))).rstrip("/")

    # ---- introspection ----
    def is_available(self) -> bool:
        # TTL cache: a positive probe is cached, but a failed probe is re-checked
        # after OLLAMA_RECHECK_MS so a late-starting / recovered Ollama is picked
        # up instead of being stuck down forever. This is the core resilience
        # path: when the cloud LLM API runs out, the local model must take over.
        now = time.time()
        cached = self._cache.get("available")
        if cached is True:
            return True
        cached_at = self._cache.get("available_at", 0)
        recheck_ms = int(os.getenv("OLLAMA_RECHECK_MS", "3000"))
        if cached is not None and (now - cached_at) * 1000 < recheck_ms:
            return False
        data = self._get("/api/tags", timeout=4)
        ok = bool(data) and bool(data.get("models"))
        self._cache["available"] = ok
        self._cache["available_at"] = now
        return ok

    def list_models(self) -> List[str]:
        data = self._get("/api/tags", timeout=4)
        if not data:
            return []
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]

    def installed_model(self, name: str) -> bool:
        return name in self.list_models()

    # ---- generation ----
    def _chat_payload(self, messages: List[Dict[str, str]], max_tokens: int,
                      temperature: float, seed: int, json_mode: bool = False,
                      fast: bool = False, native: bool = False,
                      model_override: str = "") -> Dict[str, Any]:
        keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "5m")
        if native:
            # The native /api/chat endpoint requires a duration unit ("-1m"
            # = keep loaded indefinitely); bare "-1" 400s there.
            if keep_alive == "-1":
                keep_alive = "-1m"
            elif keep_alive.isdigit():
                keep_alive = f"{keep_alive}m"
        payload: Dict[str, Any] = {
            "model": model_override or (self.fast_model_name() if fast else self.model_name()),
            "messages": messages,
            "stream": False,
            "think": False,
            # Bounded keep_alive (default 5m) keeps model + KV cache warm
            # across back-to-back calls while guaranteeing RAM is returned
            # after idle — an unbounded pin starved this host when a large
            # vision model stayed resident on CPU-only inference.
            "keep_alive": keep_alive,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "seed": seed,
                "top_k": 1,
                "top_p": 1.0,
                "repeat_penalty": 1.1,
            },
        }
        ctx = os.getenv("OLLAMA_NUM_CTX", "").strip()
        if ctx.isdigit():
            payload["options"]["num_ctx"] = int(ctx)
        if json_mode:
            payload["format"] = "json"
        return payload

    def model_name(self) -> str:
        """Best installed model, per env override then preference order."""
        override = _env("LOCAL_MODEL_NAME", _env("OLLAMA_MODEL", ""))
        installed = self.list_models()
        if not installed:
            return override or "qwen3:4b"
        if override:
            for m in installed:
                if m == override or m.endswith(f":{override}"):
                    return m
        for pref in DEFAULT_MODEL_PREFERENCE:
            if not pref:
                continue
            for m in installed:
                if pref.lower() in m.lower():
                    return m
        return installed[0]

    def vision_model_name(self) -> str:
        """Best installed vision-capable model (gemma4 line), or the default."""
        override = _env("LOCAL_MODEL_VISION", "").strip()
        installed = self.list_models()
        if override and installed:
            for m in installed:
                if m == override or m.endswith(f":{override}"):
                    return m
        # qwen3.5:4b is multimodal (image+video) and beat the gemma-4 line
        # on this host; medgemma:4b carries a SigLIP vision tower as backup.
        for pref in ("qwen3.5", "medgemma", "gemma-4", "gemma3", "llava", "qwen2.5-vl"):
            for m in installed:
                if pref.lower() in m.lower():
                    return m
        return self.model_name()

    def supports_vision(self) -> bool:
        """True when the active model is vision-capable (reports 'vision')."""
        try:
            data = self._get("/api/tags", timeout=4)
            for m in (data or {}).get("models", []):
                if m.get("name") == self.vision_model_name():
                    caps = m.get("capabilities") or []
                    return "vision" in caps
        except Exception:  # noqa: BLE001
            pass
        name = self.vision_model_name().lower()
        return any(tag in name for tag in ("gemma-4", "gemma3", "qwen3.5", "medgemma", "vl", "llava"))

    def biomed_model_name(self) -> str:
        """Biomed/clinical specialist (medgemma), falling back to the default."""
        for m in self.list_models():
            if "medgemma" in m.lower():
                return m
        return self.model_name()

    def ocr_model_name(self) -> Optional[str]:
        """Document-OCR specialist, or None when not installed."""
        for m in self.list_models():
            if "deepseek-ocr" in m.lower():
                return m
        return None

    def chat_with_model(self, model: str, system: str, user: str,
                        max_tokens: int = DEFAULT_MAX_TOKENS,
                        temperature: float = DEFAULT_TEMPERATURE) -> str:
        """Chat against an explicitly named installed model (domain lanes)."""
        b = self._first_available()
        if not b or not model:
            return ""
        return b.chat(model=model, system=system, user=user,
                      max_tokens=max_tokens, temperature=temperature)

    def chat_with_image(self, prompt: str, image_path: str, max_tokens: int = 512,
                        temperature: float = DEFAULT_TEMPERATURE) -> str:
        """Vision chat: describe/analyse an image via a local vision model.

        Uses the native /api/chat endpoint with a base64 image part (the
        OpenAI-compat endpoint on Ollama also accepts data: URLs, but the
        native path is the most reliable for GGUF vision models).
        """
        import base64
        try:
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
        except OSError as e:
            self._last_error = str(e)
            return ""
        suffix = Path(image_path).suffix.lower().lstrip(".") or "png"
        mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "gif": "gif"}.get(suffix, "png")
        messages = [{
            "role": "user",
            "content": prompt,
            "images": [b64],
        }]
        payload = self._chat_payload(messages, max_tokens, temperature, DEFAULT_SEED, native=True)
        payload["model"] = self.vision_model_name()
        data = self._post("/api/chat", payload)
        if not data:
            return ""
        return (data.get("message", {}).get("content") or "").strip()

    def call_tools(self, prompt: str, tools: List[Dict[str, Any]], max_tokens: int = 256,
                   temperature: float = DEFAULT_TEMPERATURE, fast: bool = False) -> Dict[str, Any]:
        """Tool calling via the native /api/chat endpoint.

        Returns {"content": str, "tool_calls": [...]} so callers can loop:
        execute the tool, append the result, call again. Retries transient
        transport failures with backoff (robust to Ollama's busy/loading
        windows on shared hardware).
        """
        messages = [{"role": "user", "content": prompt}]
        payload = self._chat_payload(messages, max_tokens, temperature, DEFAULT_SEED, native=True, fast=fast)
        payload["tools"] = tools
        last_err = ""
        for attempt in range(3):
            data = self._post("/api/chat", payload)
            if data:
                msg = data.get("message", {}) or {}
                return {
                    "content": (msg.get("content") or "").strip(),
                    "tool_calls": msg.get("tool_calls") or [],
                }
            last_err = self.last_error
            # transient/loading — back off, then retry
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
        self._last_error = last_err
        return {}

    def fast_model_name(self) -> str:
        """A lighter model for interactive calls, when one is installed.

        Set LOCAL_MODEL_FAST to pin it (e.g. 'qwen3:0.6b' or 'gemma3:1b').
        Falls back to the default model when no fast model is configured or
        installed, so it is always safe to call.
        """
        fast = _env("LOCAL_MODEL_FAST", "").strip()
        installed = self.list_models()
        if fast and installed:
            for m in installed:
                if m == fast or m.endswith(f":{fast}"):
                    return m
        # Known light models to prefer if present.
        for pref in ("qwen3:0.6b", "qwen3:1.7b", "gemma3:1b", "gemma3:4b"):
            for m in installed:
                if pref.lower() in m.lower():
                    return m
        return self.model_name()

    def chat(self, system: str, user: str, max_tokens: int = DEFAULT_MAX_TOKENS,
             temperature: float = DEFAULT_TEMPERATURE, use_cot: bool = False,
             fast: bool = False, model: str = "") -> str:
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        payload = self._chat_payload(messages, max_tokens, temperature, DEFAULT_SEED,
                                     fast=fast, model_override=model)
        data = self._post("/v1/chat/completions", payload)
        if not data:
            return ""
        msg = data.get("choices", [{}])[0].get("message", {})
        content = (msg.get("content") or "").strip()
        if not content and use_cot:
            # some thinking models put the answer inside reasoning
            reasoning = (msg.get("reasoning") or "").strip()
            if reasoning:
                return f"<thinking>\n{reasoning}\n</thinking>\n\n"
        return content

    def _native_chat_json(self, system: str, user: str, max_tokens: int,
                          temperature: float, fast: bool = False) -> Dict[str, Any]:
        """Native /api/chat with format=json → guaranteed well-formed JSON.

        This is the reliable path for structured output on Ollama; the
        OpenAI-compat endpoint has no JSON-grammar guarantee.
        """
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        payload = self._chat_payload(messages, max_tokens, temperature, DEFAULT_SEED,
                                     json_mode=True, native=True, fast=fast)
        data = self._post("/api/chat", payload)
        if not data:
            return {}
        return _extract_dict(data.get("message", {}).get("content", ""))

    def complete(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                 temperature: float = DEFAULT_TEMPERATURE) -> str:
        return self.chat("", prompt, max_tokens=max_tokens, temperature=temperature)

    def generate_json(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                      temperature: float = DEFAULT_TEMPERATURE,
                      fast: bool = False) -> Dict[str, Any]:
        """Structured JSON via native Ollama JSON mode, with parse repair."""
        system = ("You are a deterministic JSON generator. Reply with ONLY valid JSON. "
                  "No prose, no markdown fences, no explanation.")
        # Primary: native /api/chat with format=json (guaranteed parseable).
        result = self._native_chat_json(system, prompt, max_tokens=max_tokens,
                                        temperature=temperature, fast=fast)
        if result:
            return result
        # Fallback: OpenAI-compat path + extraction/repair.
        content = self.chat(system, prompt, max_tokens=max_tokens, temperature=temperature, fast=fast)
        parsed = _extract_dict(content)
        if parsed is not None:
            return parsed
        return {}

    def ensure_model(self, name: str) -> Dict[str, Any]:
        """Pull a model via Ollama's native /api/pull."""
        data = self._post("/api/pull", {"model": name, "stream": False}, timeout=900)
        if data is None:
            return {"ok": False, "error": self.last_error, "model": name}
        self._cache.pop("available", None)
        self._cache.pop("models", None)
        return {"ok": True, "model": name, "status": data.get("status")}

    def warm(self) -> bool:
        """Preload the model so the first real call doesn't pay load time.

        Sends an empty chat (Ollama loads the model into memory without
        generating). Keeps the model resident via keep_alive=-1.
        """
        try:
            data = self._post(
                "/api/chat",
                {"model": self.model_name(), "messages": [], "stream": False},
                timeout=300,
            )
            return data is not None
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------------------
# llama-server (llama.cpp) backend — OpenAI-compatible
# ---------------------------------------------------------------------------

class LlamaServerBackend(LocalModelBackend):
    """Local inference via llama.cpp llama-server (OpenAI-compatible /v1 API)."""

    name = "llama-server"

    def __init__(self, base_url: str | None = None) -> None:
        super().__init__()
        self.base_url = (base_url or _env("LLAMA_SERVER_URL", _env("LOCAL_MODEL_URL", DEFAULT_LLAMA_SERVER_URL))).rstrip("/")

    def is_available(self) -> bool:
        if self._cache.get("available") is not None:
            return self._cache["available"]
        data = self._get("/v1/models", timeout=4)
        ok = bool(data) and bool(data.get("data") or data.get("models"))
        self._cache["available"] = ok
        return ok

    def list_models(self) -> List[str]:
        data = self._get("/v1/models", timeout=4)
        if not data:
            return []
        rows = data.get("data") or data.get("models") or []
        out = []
        for m in rows:
            if isinstance(m, dict):
                out.append(m.get("id") or m.get("name") or "")
            else:
                out.append(str(m))
        return [m for m in out if m]

    def model_name(self) -> str:
        override = _env("LOCAL_MODEL_NAME", "")
        installed = self.list_models()
        if override and override in installed:
            return override
        for pref in DEFAULT_MODEL_PREFERENCE:
            if not pref:
                continue
            for m in installed:
                if pref.lower() in m.lower():
                    return m
        return installed[0] if installed else "qwen3.5:4b"

    def chat(self, system: str, user: str, max_tokens: int = DEFAULT_MAX_TOKENS,
             temperature: float = DEFAULT_TEMPERATURE, use_cot: bool = False) -> str:
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        payload = {
            "model": self.model_name(),
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_k": 1,
            "top_p": 1.0,
            "repeat_penalty": 1.1,
            "seed": DEFAULT_SEED,
            "stream": False,
        }
        data = self._post("/v1/chat/completions", payload)
        if not data:
            return ""
        return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()

    def complete(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                 temperature: float = DEFAULT_TEMPERATURE) -> str:
        return self.chat("", prompt, max_tokens=max_tokens, temperature=temperature)

    def generate_json(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                      temperature: float = DEFAULT_TEMPERATURE) -> Dict[str, Any]:
        system = ("You are a deterministic JSON generator. Reply with ONLY valid JSON. "
                  "No prose, no markdown fences, no explanation.")
        content = self.chat(system, prompt, max_tokens=max_tokens, temperature=temperature)
        parsed = _extract_dict(content)
        if parsed is not None:
            return parsed
        return {}

    def ensure_model(self, name: str) -> Dict[str, Any]:
        return {"ok": False, "error": "llama-server cannot auto-pull models; use ollama pull", "model": name}


# ---------------------------------------------------------------------------
# llama.cpp in-process backend (wraps tools.llm.qwen_coder)
# ---------------------------------------------------------------------------

class LlamaCppInProcessBackend(LocalModelBackend):
    """In-process GGUF inference via llama-cpp-python (CPU, deterministic)."""

    name = "llama-cpp"

    def __init__(self, model_path: str | None = None) -> None:
        super().__init__()
        self._model_path = model_path or _env("QWEN_MODEL_PATH", "")
        self._service = None
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        if self._available is None:
            if not self._model_path or not os.path.isfile(self._model_path):
                self._available = False
            else:
                try:
                    from tools.llm.qwen_coder import get_service
                    self._service = get_service()
                    self._available = bool(self._service.available)
                except Exception:  # noqa: BLE001
                    self._available = False
        return bool(self._available)

    def list_models(self) -> List[str]:
        if self.is_available() and self._model_path:
            return [os.path.basename(self._model_path)]
        return []

    def chat(self, system: str, user: str, max_tokens: int = DEFAULT_MAX_TOKENS,
             temperature: float = DEFAULT_TEMPERATURE, use_cot: bool = False) -> str:
        if not self.is_available():
            return ""
        prompt = f"{system}\n\n{user}" if system else user
        try:
            return self._service.generate_text(prompt, max_tokens=max_tokens)
        except Exception as e:  # noqa: BLE001
            self._last_error = str(e)
            return ""

    def complete(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                 temperature: float = DEFAULT_TEMPERATURE) -> str:
        return self.chat("", prompt, max_tokens=max_tokens, temperature=temperature)

    def generate_json(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                      temperature: float = DEFAULT_TEMPERATURE) -> Dict[str, Any]:
        system = ("You are a deterministic JSON generator. Reply with ONLY valid JSON. "
                  "No prose, no markdown fences, no explanation.")
        content = self.chat(system, prompt, max_tokens=max_tokens, temperature=temperature)
        parsed = _extract_dict(content)
        if parsed is not None:
            return parsed
        return {}

    def ensure_model(self, name: str) -> Dict[str, Any]:
        return {"ok": False, "error": "llama-cpp is in-process; set QWEN_MODEL_PATH to a GGUF", "model": name}


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _parse_json(text: str) -> Optional[Dict[str, Any]]:
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def _extract_dict(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort dict extraction: direct parse, then fenced/braced span.

    Handles common local-model failure modes: markdown fences, prose
    before/after, and truncated JSON (unclosed braces) by closing the
    brace span and re-parsing.
    """
    if not text:
        return None
    parsed = _parse_json(text)
    if parsed is not None:
        return parsed
    cleaned = _extract_json_block(text)
    if cleaned:
        parsed = _parse_json(cleaned)
        if parsed is not None:
            return parsed
        # Repair truncated JSON: append missing closing braces / quotes.
        repaired = _repair_truncated_json(cleaned)
        if repaired:
            parsed = _parse_json(repaired)
            if parsed is not None:
                return parsed
    return None


def _repair_truncated_json(text: str) -> Optional[str]:
    """Try to close a truncated JSON object (missing trailing braces)."""
    if not text or "{" not in text:
        return None
    for attempt in range(1, 6):
        candidate = text + "}" * attempt
        parsed = _parse_json(candidate)
        if parsed is not None:
            return candidate
    return None


def _extract_json_block(text: str) -> str:
    """Strip markdown fences and pull out the first {...} span."""
    # Remove code fences (```json ... ```)
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        text = m.group(1)
    start = text.find("{")
    if start < 0:
        return ""
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]


# ---------------------------------------------------------------------------
# Unified service
# ---------------------------------------------------------------------------

class LocalModelService:
    """Unified facade over all local inference backends."""

    def __init__(self) -> None:
        self.backends: List[LocalModelBackend] = []
        self._detect()

    def _detect(self) -> None:
        backends: List[LocalModelBackend] = []
        backends.append(OllamaBackend())
        backends.append(LlamaServerBackend())
        backends.append(LlamaCppInProcessBackend())
        self.backends = backends

    def reset(self) -> None:
        self._detect()

    # ---- introspection ----
    def is_available(self) -> bool:
        return any(b.is_available() for b in self.backends)

    def active_backend(self) -> Optional[LocalModelBackend]:
        for b in self.backends:
            if b.is_available():
                return b
        return None

    def list_models(self) -> List[str]:
        out: List[str] = []
        for b in self.backends:
            if b.is_available():
                out.extend(b.list_models())
        # de-dup preserving order
        seen = set()
        return [m for m in out if not (m in seen or seen.add(m))]

    def status(self) -> Dict[str, Any]:
        detail: Dict[str, Any] = {}
        for b in self.backends:
            avail = b.is_available()
            detail[b.name] = {
                "available": avail,
                "models": b.list_models() if avail else [],
                "error": b.last_error if not avail else "",
            }
        active = self.active_backend()
        return {
            "available": bool(active),
            "backend": active.name if active else None,
            "model": active.model_name() if active else None,
            "backends": detail,
        }

    # ---- generation (auto-route to first available backend) ----
    def _first_available(self) -> Optional[LocalModelBackend]:
        return self.active_backend()

    def chat(self, system: str, user: str, max_tokens: int = DEFAULT_MAX_TOKENS,
             temperature: float = DEFAULT_TEMPERATURE, use_cot: bool = False,
             fast: bool = False) -> str:
        b = self._first_available()
        if not b:
            return ""
        return b.chat(system, user, max_tokens=max_tokens, temperature=temperature, use_cot=use_cot, fast=fast)

    def complete(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                 temperature: float = DEFAULT_TEMPERATURE) -> str:
        b = self._first_available()
        if not b:
            return ""
        return b.complete(prompt, max_tokens=max_tokens, temperature=temperature)

    def biomed_model_name(self) -> str:
        """Biomed/clinical specialist (medgemma), falling back to the default."""
        b = self._first_available()
        if b and hasattr(b, "biomed_model_name"):
            return b.biomed_model_name()
        return ""

    def ocr_model_name(self) -> Optional[str]:
        """Document-OCR specialist, or None when not installed."""
        b = self._first_available()
        if b and hasattr(b, "ocr_model_name"):
            return b.ocr_model_name()
        return None

    def chat_with_model(self, model: str, system: str, user: str,
                        max_tokens: int = DEFAULT_MAX_TOKENS,
                        temperature: float = DEFAULT_TEMPERATURE) -> str:
        """Chat against an explicitly named installed model (domain lanes)."""
        b = self._first_available()
        if not b or not model:
            return ""
        return b.chat(model=model, system=system, user=user,
                      max_tokens=max_tokens, temperature=temperature)

    def generate_text(self, prompt: str, system: str | None = None,
                      max_tokens: int = DEFAULT_MAX_TOKENS,
                      temperature: float = DEFAULT_TEMPERATURE) -> str:
        b = self._first_available()
        if not b:
            return ""
        if system:
            return b.chat(system, prompt, max_tokens=max_tokens, temperature=temperature)
        return b.complete(prompt, max_tokens=max_tokens, temperature=temperature)

    def generate_json(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                      temperature: float = DEFAULT_TEMPERATURE,
                      fast: bool = False) -> Dict[str, Any]:
        b = self._first_available()
        if not b:
            return {}
        return b.generate_json(prompt, max_tokens=max_tokens, temperature=temperature, fast=fast)

    def complete_with_cot(self, system: str, user: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> Tuple[str, str]:
        """Chain-of-thought: ask for a scratchpad, then a final answer.

        Returns (scratchpad, answer). Falls back to ('' , answer) if the
        backend has no separate reasoning channel.
        """
        b = self._first_available()
        if not b:
            return "", ""
        cot_prompt = (
            f"{user}\n\nFirst, reason step by step inside <thinking> tags. "
            "Then provide your final answer after </thinking>."
        )
        raw = b.chat(system, cot_prompt, max_tokens=max_tokens, temperature=DEFAULT_TEMPERATURE, use_cot=True)
        if not raw:
            return "", ""
        if "<thinking>" in raw and "</thinking>" in raw:
            start = raw.index("<thinking>") + len("<thinking>")
            end = raw.index("</thinking>")
            scratchpad = raw[start:end].strip()
            answer = raw[end + len("</thinking>"):].strip()
            return scratchpad, answer
        return "", raw.strip()

    def supports_vision(self) -> bool:
        b = self._first_available()
        return bool(b and hasattr(b, "supports_vision") and b.supports_vision())

    def chat_with_image(self, prompt: str, image_path: str, max_tokens: int = 512,
                        temperature: float = DEFAULT_TEMPERATURE) -> str:
        """Vision: analyse an image with the local vision model."""
        b = self._first_available()
        if not b or not hasattr(b, "chat_with_image"):
            return ""
        return b.chat_with_image(prompt, image_path, max_tokens=max_tokens, temperature=temperature)

    def call_tools(self, prompt: str, tools: List[Dict[str, Any]], max_tokens: int = 256,
                   temperature: float = DEFAULT_TEMPERATURE, fast: bool = False) -> Dict[str, Any]:
        """Tool calling via the local model (native Ollama path)."""
        b = self._first_available()
        if not b or not hasattr(b, "call_tools"):
            return {}
        return b.call_tools(prompt, tools, max_tokens=max_tokens, temperature=temperature, fast=fast)

    def ensure_model(self, name: str | None = None) -> Dict[str, Any]:
        """Pull a model into Ollama. Picks a default if none given."""
        if not name:
            name = _env("LOCAL_MODEL_NAME", _env("OLLAMA_MODEL", "qwen3:4b"))
        for b in self.backends:
            if b.name == "ollama" and b.is_available():
                return b.ensure_model(name)
        return {"ok": False, "error": "ollama not running", "model": name}

    def warm(self) -> bool:
        """Preload the active backend's model so the first call is fast."""
        b = self._first_available()
        if not b or not hasattr(b, "warm"):
            return False
        return bool(b.warm())


# Module-level singleton
_service: LocalModelService | None = None


def get_local_model() -> LocalModelService:
    global _service
    if _service is None:
        _service = LocalModelService()
    return _service


def reset_local_model() -> None:
    global _service
    _service = None
