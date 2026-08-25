"""Tests for the unified local model service (tools/local_model.py)."""

import json
import pytest

from tools.local_model import (
    _extract_json_block,
    _parse_json,
    LocalModelService,
    OllamaBackend,
    get_local_model,
    reset_local_model,
)


class TestJSONHelpers:
    """Pure JSON extraction/repair helpers."""

    def test_parse_valid_json(self):
        assert _parse_json('{"a": 1}') == {"a": 1}

    def test_parse_invalid_json_returns_none(self):
        assert _parse_json("not json") is None

    def test_parse_non_dict_json_returns_none(self):
        assert _parse_json("[1, 2, 3]") is None

    def test_extract_fenced_json(self):
        text = 'Here you go:\n```json\n{"status": "ok"}\n```\nThanks!'
        assert _extract_json_block(text) == '{"status": "ok"}'

    def test_extract_brace_span(self):
        text = 'prefix {"a": {"b": 2}} suffix'
        assert _extract_json_block(text) == '{"a": {"b": 2}}'

    def test_extract_no_brace_returns_empty(self):
        assert _extract_json_block("no json here") == ""


class FakeBackend:
    """Stand-in backend for service-level tests."""

    name = "fake"
    base_url = ""

    def __init__(self, available=True, models=None, chat_reply="fake reply"):
        self._available = available
        self._models = models or ["fake-model"]
        self._chat_reply = chat_reply
        self._last_error = ""

    def is_available(self):
        return self._available

    def list_models(self):
        return self._models

    def model_name(self):
        return self._models[0] if self._models else ""

    def chat(self, system, user, max_tokens=2048, temperature=0.1, use_cot=False):
        if use_cot:
            return "<thinking>\nthinking...\n</thinking>\n\nanswer"
        return self._chat_reply

    def complete(self, prompt, max_tokens=2048, temperature=0.1):
        return self._chat_reply

    def generate_text(self, prompt, system=None, max_tokens=2048, temperature=0.1):
        return self._chat_reply

    def generate_json(self, prompt, max_tokens=2048, temperature=0.1, fast=False):
        return {"ok": True}

    def ensure_model(self, name):
        return {"ok": True, "model": name}

    @property
    def last_error(self):
        return self._last_error


class TestLocalModelService:
    """Service-level behaviour with a fake backend."""

    def _service(self, backends):
        svc = LocalModelService.__new__(LocalModelService)
        svc.backends = backends
        return svc

    def test_is_available_true_with_live_backend(self):
        svc = self._service([FakeBackend(available=True)])
        assert svc.is_available() is True

    def test_is_available_false_with_dead_backend(self):
        svc = self._service([FakeBackend(available=False)])
        assert svc.is_available() is False

    def test_active_backend_picks_first_live(self):
        dead = FakeBackend(available=False)
        live = FakeBackend(available=True)
        svc = self._service([dead, live])
        assert svc.active_backend() is live

    def test_list_models_dedupes(self):
        a = FakeBackend(available=True, models=["m1", "m2"])
        b = FakeBackend(available=True, models=["m2", "m3"])
        svc = self._service([a, b])
        assert svc.list_models() == ["m1", "m2", "m3"]

    def test_generate_text_delegates_to_backend(self):
        svc = self._service([FakeBackend(chat_reply="hello from local")])
        assert svc.generate_text("prompt") == "hello from local"

    def test_generate_text_empty_when_no_backend(self):
        svc = self._service([FakeBackend(available=False)])
        assert svc.generate_text("prompt") == ""

    def test_generate_json_delegates(self):
        svc = self._service([FakeBackend()])
        assert svc.generate_json("prompt") == {"ok": True}

    def test_complete_with_cot_returns_tuple(self):
        svc = self._service([FakeBackend()])
        scratch, answer = svc.complete_with_cot("sys", "user")
        assert scratch == "thinking..."
        assert answer == "answer"

    def test_status_shape(self):
        svc = self._service([FakeBackend(available=True, models=["m1"])])
        status = svc.status()
        assert status["available"] is True
        assert status["backend"] == "fake"
        assert status["model"] == "m1"
        assert "fake" in status["backends"]


class TestRouterLocalFirst:
    """Router should prefer the unified local model before remote/stub."""

    def test_generate_text_uses_local_when_available(self, monkeypatch):
        from tools.llm import router as llm_router
        captured = {}

        class FakeService:
            def is_available(self):
                return True

            def generate_text(self, prompt, system=None, max_tokens=2048):
                captured["prompt"] = prompt
                return "local answer"

            def complete_with_cot(self, system, user, max_tokens=2048):
                return "thinking", "answer"

            def generate_json(self, prompt, max_tokens=2048, fast=False):
                return {"ok": True}

        monkeypatch.setattr(llm_router, "get_local_model", lambda: FakeService())
        result = llm_router.generate_text("test prompt")
        assert result == "local answer"
        assert captured["prompt"] == "test prompt"

    def test_generate_json_uses_local(self, monkeypatch):
        from tools.llm import router as llm_router

        class FakeService:
            def is_available(self):
                return True

            def generate_json(self, prompt, max_tokens=2048, fast=False):
                return {"status": "ok"}

        monkeypatch.setattr(llm_router, "get_local_model", lambda: FakeService())
        result = llm_router.generate_json("some prompt")
        assert result == {"status": "ok"}

    def test_generate_text_falls_back_to_stub_when_local_down(self, monkeypatch):
        from tools.llm import router as llm_router

        class DeadService:
            def is_available(self):
                return False

        class DeadGemma:
            def is_available(self):
                return False

        class DeadGoTier:
            available = False

        class DeadOpenRouter:
            @property
            def available(self):
                return False

        class DeadQwen:
            @property
            def available(self):
                return False

            def generate_text(self, prompt, max_tokens=2048):
                return f"[LLM stub] {prompt[:120]}..."

        monkeypatch.setattr(llm_router, "get_local_model", lambda: DeadService())
        monkeypatch.setattr(llm_router, "get_gemma", lambda: DeadGemma())
        monkeypatch.setattr(llm_router, "get_gotier", lambda: DeadGoTier())
        monkeypatch.setattr(llm_router, "get_or", lambda: DeadOpenRouter())
        monkeypatch.setattr(llm_router, "get_qwen", lambda: DeadQwen())

        result = llm_router.generate_text("hello world")
        assert isinstance(result, str)
        assert "stub" in result.lower() or len(result) > 0


class TestOllamaBackendUnit:
    """Ollama backend unit tests with mocked HTTP."""

    def test_list_models_parses_tags(self, monkeypatch):
        backend = OllamaBackend(base_url="http://fake:11434")

        class FakeResp:
            status_code = 200

            def json(self):
                return {"models": [{"name": "qwen3:4b"}, {"name": "gemma3:4b"}]}

        monkeypatch.setattr("tools.local_model.requests.get", lambda *a, **k: FakeResp())
        assert backend.list_models() == ["qwen3:4b", "gemma3:4b"]

    def test_is_available_false_when_no_models(self, monkeypatch):
        backend = OllamaBackend(base_url="http://fake:11434")

        class FakeResp:
            status_code = 200

            def json(self):
                return {"models": []}

        monkeypatch.setattr("tools.local_model.requests.get", lambda *a, **k: FakeResp())
        assert backend.is_available() is False

    def test_chat_empty_on_http_error(self, monkeypatch):
        backend = OllamaBackend(base_url="http://fake:11434")

        class FakeResp:
            status_code = 500

            @property
            def text(self):
                return "boom"

        monkeypatch.setattr("tools.local_model.requests.post", lambda *a, **k: FakeResp())
        assert backend.chat("sys", "user") == ""

    def test_model_name_prefers_env_override(self, monkeypatch):
        backend = OllamaBackend(base_url="http://fake:11434")
        monkeypatch.setenv("LOCAL_MODEL_NAME", "qwen3:4b")
        monkeypatch.setattr(
            backend, "list_models", lambda: ["gemma3:4b", "qwen3:4b", "other"]
        )
        assert backend.model_name() == "qwen3:4b"


class TestOllamaVisionAndTools:
    """Vision + tool-calling paths on the Ollama backend (mocked HTTP)."""

    def test_supports_vision_true_for_gemma(self, monkeypatch):
        backend = OllamaBackend(base_url="http://fake:11434")

        class FakeResp:
            status_code = 200

            def json(self):
                return {"models": [
                    {"name": "hf.co/unsloth/gemma-4-E2B-it-GGUF:UD-IQ2_M",
                     "capabilities": ["completion", "vision"]}
                ]}

        monkeypatch.setattr("tools.local_model.requests.get", lambda *a, **k: FakeResp())
        assert backend.supports_vision() is True

    def test_vision_model_prefers_gemma(self, monkeypatch):
        backend = OllamaBackend(base_url="http://fake:11434")
        monkeypatch.setattr(
            backend, "list_models",
            lambda: ["qwen3:0.6b", "hf.co/unsloth/gemma-4-E2B-it-GGUF:UD-IQ2_M"],
        )
        assert "gemma-4-E2B" in backend.vision_model_name()

    def test_chat_with_image_missing_file_returns_empty(self):
        backend = OllamaBackend(base_url="http://fake:11434")
        assert backend.chat_with_image("desc", "C:/nope/missing.png") == ""

    def test_chat_with_image_posts_base64(self, monkeypatch, tmp_path):
        import base64
        backend = OllamaBackend(base_url="http://fake:11434")
        monkeypatch.setattr(
            backend, "list_models",
            lambda: ["hf.co/unsloth/gemma-4-E2B-it-GGUF:UD-IQ2_M"],
        )
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG fake")

        captured = {}

        class FakeResp:
            status_code = 200

            def json(self):
                return {"message": {"content": "two squares"}}

        def fake_post(url, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            return FakeResp()

        monkeypatch.setattr("tools.local_model.requests.post", fake_post)
        out = backend.chat_with_image("describe", str(img), max_tokens=64)
        assert out == "two squares"
        assert captured["url"].endswith("/api/chat")
        assert "gemma" in captured["json"]["model"]
        images = captured["json"]["messages"][0].get("images", [])
        assert len(images) == 1
        assert base64.b64decode(images[0]) == b"\x89PNG fake"

    def test_call_tools_returns_tool_calls(self, monkeypatch):
        backend = OllamaBackend(base_url="http://fake:11434")

        class FakeResp:
            status_code = 200

            def json(self):
                return {"message": {
                    "content": "",
                    "tool_calls": [{"function": {"name": "get_weather",
                                                  "arguments": {"city": "Paris"}}}],
                }}

        monkeypatch.setattr("tools.local_model.requests.post", lambda *a, **k: FakeResp())
        result = backend.call_tools(
            "weather in Paris?",
            [{"type": "function", "function": {"name": "get_weather"}}],
        )
        assert result["tool_calls"]
        assert result["tool_calls"][0]["function"]["name"] == "get_weather"

    def test_fast_model_picks_configured(self, monkeypatch):
        backend = OllamaBackend(base_url="http://fake:11434")
        monkeypatch.setenv("LOCAL_MODEL_FAST", "qwen3:0.6b")
        monkeypatch.setattr(backend, "list_models", lambda: ["qwen3:0.6b", "gemma3:4b"])
        assert backend.fast_model_name() == "qwen3:0.6b"


# ── Live integration tests (skip when no local backend) ────────────────────

def _require_local():
    reset_local_model()
    if not get_local_model().is_available():
        pytest.skip("No local model backend running (ollama/llama-server)")


class TestLocalModelLive:
    """Live inference against whatever local backend is up."""

    def test_generate_text(self):
        _require_local()
        svc = get_local_model()
        out = svc.generate_text("Reply with exactly: local-ok", max_tokens=32)
        assert out and "local-ok" in out

    def test_generate_json(self):
        _require_local()
        svc = get_local_model()
        out = svc.generate_json('Return JSON: {"status":"ok","answer":"hi"}')
        assert isinstance(out, dict)
        assert out.get("status") == "ok"

    def test_status_reports_backends(self):
        _require_local()
        svc = get_local_model()
        status = svc.status()
        assert status["available"] is True
        assert status["backend"] in ("ollama", "llama-server", "llama-cpp")
        assert "backends" in status

    def test_vision_capability_live(self):
        """The gemma models on this box advertise vision."""
        _require_local()
        svc = get_local_model()
        assert svc.supports_vision() is True
