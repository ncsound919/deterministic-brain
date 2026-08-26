"""Tests for the funded opencode Go tier client (tools/llm/gotier_client.py)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class FakeResp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class TestGoTierClient:
    def test_available_true_with_key(self, monkeypatch):
        monkeypatch.setenv("OPENCODE_API_KEY", "sk-test")
        from tools.llm.gotier_client import GoTierClient

        c = GoTierClient()
        assert c.available is True

    def test_available_via_live_gateway_without_key(self, monkeypatch):
        from tools.llm.gotier_client import GoTierClient
        from tools.llm import gotier_client as gc

        monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
        monkeypatch.delenv("LITELLM_API_KEY", raising=False)
        monkeypatch.setattr(gc, "requests", type("R", (), {"get": staticmethod(lambda *a, **k: FakeResp(200, {"data": []}))}))

        c = GoTierClient(litellm_url="http://fake:4100")
        assert c.available is True

    def test_unavailable_without_key_and_dead_gateway(self, monkeypatch):
        from tools.llm.gotier_client import GoTierClient
        from tools.llm import gotier_client as gc

        monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
        monkeypatch.delenv("LITELLM_API_KEY", raising=False)

        def boom(*a, **k):
            raise RuntimeError("refused")

        monkeypatch.setattr(gc, "requests", type("R", (), {"get": staticmethod(boom)}))

        c = GoTierClient(litellm_url="http://fake:4100")
        assert c.available is False

    def test_complete_uses_litellm_gateway_first(self, monkeypatch):
        from tools.llm.gotier_client import GoTierClient
        from tools.llm import gotier_client as gc

        calls = []

        def fake_post(url, **kwargs):
            calls.append(url)
            if "4100" in url:
                return FakeResp(200, {"choices": [{"message": {"content": "gateway reply"}}]})
            return FakeResp(200, {"choices": [{"message": {"content": "direct reply"}}]})

        monkeypatch.setattr(gc, "requests", type("R", (), {"post": staticmethod(fake_post)}))
        monkeypatch.setenv("OPENCODE_API_KEY", "sk-test")

        c = GoTierClient()
        assert c.chat("sys", "user") == "gateway reply"
        assert calls[0].endswith("/v1/chat/completions")
        assert calls[0].startswith("http://localhost:4100")

    def test_complete_falls_back_to_direct_go(self, monkeypatch):
        from tools.llm.gotier_client import GoTierClient
        from tools.llm import gotier_client as gc

        calls = []

        def fake_post(url, **kwargs):
            calls.append(url)
            if "4100" in url:
                return FakeResp(500, {}, text="gateway down")
            return FakeResp(200, {"choices": [{"message": {"content": "direct reply"}}]})

        monkeypatch.setattr(gc, "requests", type("R", (), {"post": staticmethod(fake_post)}))
        monkeypatch.setenv("OPENCODE_API_KEY", "sk-test")

        c = GoTierClient()
        assert c.chat("sys", "user") == "direct reply"
        assert calls[-1].startswith("https://opencode.ai/zen/go/v1/chat/completions")

    def test_complete_empty_when_all_fail(self, monkeypatch):
        from tools.llm.gotier_client import GoTierClient
        from tools.llm import gotier_client as gc

        def fake_post(url, **kwargs):
            return FakeResp(500, {}, text="boom")

        monkeypatch.setattr(gc, "requests", type("R", (), {"post": staticmethod(fake_post)}))
        monkeypatch.setenv("OPENCODE_API_KEY", "sk-test")

        c = GoTierClient()
        assert c.chat("sys", "user") == ""

    def test_generate_json_parses_dict(self, monkeypatch):
        from tools.llm.gotier_client import GoTierClient
        from tools.llm import gotier_client as gc

        def fake_post(url, **kwargs):
            return FakeResp(200, {"choices": [{"message": {"content": '{"ok": true}'}}]})

        monkeypatch.setattr(gc, "requests", type("R", (), {"post": staticmethod(fake_post)}))
        monkeypatch.setenv("OPENCODE_API_KEY", "sk-test")

        c = GoTierClient()
        assert c.generate_json("give me json") == {"ok": True}

    def test_generate_json_empty_on_bad_output(self, monkeypatch):
        from tools.llm.gotier_client import GoTierClient
        from tools.llm import gotier_client as gc

        def fake_post(url, **kwargs):
            return FakeResp(200, {"choices": [{"message": {"content": "not json"}}]})

        monkeypatch.setattr(gc, "requests", type("R", (), {"post": staticmethod(fake_post)}))
        monkeypatch.setenv("OPENCODE_API_KEY", "sk-test")

        c = GoTierClient()
        assert c.generate_json("give me json") == {}

    def test_complete_with_cot_splits_thinking(self, monkeypatch):
        from tools.llm.gotier_client import GoTierClient
        from tools.llm import gotier_client as gc

        def fake_post(url, **kwargs):
            return FakeResp(200, {"choices": [{"message": {"content": "<thinking>\nstep 1\n</thinking>\n\nfinal answer"}}]})

        monkeypatch.setattr(gc, "requests", type("R", (), {"post": staticmethod(fake_post)}))
        monkeypatch.setenv("OPENCODE_API_KEY", "sk-test")

        c = GoTierClient()
        scratch, answer = c.complete_with_cot("sys", "user")
        assert scratch == "step 1"
        assert answer == "final answer"


class TestRouterGoTierPriority:
    """Router should use Go tier after local, before gemma/OpenRouter."""

    @pytest.fixture(autouse=True)
    def _allow_routing(self, monkeypatch):
        # These tests exercise routing order with faked backends — lift the
        # suite-wide BRAIN_DISABLE_LLM default from conftest.
        monkeypatch.delenv("BRAIN_DISABLE_LLM", raising=False)

    def test_generate_text_uses_gotier_when_local_down(self, monkeypatch):
        from tools.llm import router as llm_router

        class DeadService:
            def is_available(self):
                return False

        class LiveGoTier:
            available = True

            def generate_text(self, prompt, system=None, max_tokens=2048):
                return "gotier answer"

            def complete_with_cot(self, system, user, max_tokens=2048):
                return "thinking", "answer"

            def generate_json(self, prompt, max_tokens=2048):
                return {"ok": True}

        class DeadGemma:
            def is_available(self):
                return False

        monkeypatch.setattr(llm_router, "get_local_model", lambda: DeadService())
        monkeypatch.setattr(llm_router, "get_gotier", lambda: LiveGoTier())
        monkeypatch.setattr(llm_router, "get_gemma", lambda: DeadGemma())

        assert llm_router.generate_text("hello") == "gotier answer"

    def test_generate_code_uses_gotier_when_local_down(self, monkeypatch):
        from tools.llm import router as llm_router

        class DeadService:
            def is_available(self):
                return False

        class LiveGoTier:
            available = True

            def chat(self, system, user, max_tokens=256, temperature=0.1):
                return "def foo():\n    return 42"

        class DeadGemma:
            def is_available(self):
                return False

        monkeypatch.setattr(llm_router, "get_local_model", lambda: DeadService())
        monkeypatch.setattr(llm_router, "get_gotier", lambda: LiveGoTier())
        monkeypatch.setattr(llm_router, "get_gemma", lambda: DeadGemma())

        assert llm_router.generate_code("write foo") == "def foo():\n    return 42"

    def test_generate_json_uses_gotier_when_local_down(self, monkeypatch):
        from tools.llm import router as llm_router

        class DeadService:
            def is_available(self):
                return False

        class LiveGoTier:
            available = True

            def generate_json(self, prompt, max_tokens=2048):
                return {"from": "gotier"}

        monkeypatch.setattr(llm_router, "get_local_model", lambda: DeadService())
        monkeypatch.setattr(llm_router, "get_gotier", lambda: LiveGoTier())

        assert llm_router.generate_json("json please") == {"from": "gotier"}

    def test_local_still_wins_over_gotier(self, monkeypatch):
        """Local-first: when a local backend is up, it is used, not the Go tier."""
        from tools.llm import router as llm_router

        class LiveService:
            def is_available(self):
                return True

            def generate_text(self, prompt, system=None, max_tokens=2048):
                return "local answer"

        class GoTierShouldNotRun:
            available = True

            def generate_text(self, prompt, system=None, max_tokens=2048):
                raise AssertionError("gotier should not be called when local is up")

        monkeypatch.setattr(llm_router, "get_local_model", lambda: LiveService())
        monkeypatch.setattr(llm_router, "get_gotier", lambda: GoTierShouldNotRun())

        assert llm_router.generate_text("hello") == "local answer"


class TestConfigDefaults:
    def test_no_premium_defaults(self, monkeypatch):
        monkeypatch.delenv("MODEL_CODING", raising=False)
        monkeypatch.delenv("MODEL_BUSINESS_LOGIC", raising=False)
        monkeypatch.delenv("MODEL_AGENT_BRAIN", raising=False)
        monkeypatch.delenv("MODEL_CROSS_DOMAIN", raising=False)
        monkeypatch.delenv("MODEL_DEFAULT", raising=False)
        monkeypatch.delenv("MODEL_OPENCODE", raising=False)

        from tools.llm.openrouter_client import LANE_MODELS
        from tools.llm.opencode_client import _MODEL

        for lane, model in LANE_MODELS.items():
            assert "o3" not in model, f"{lane} defaulted to premium o3: {model}"
            assert "opus" not in model.lower(), f"{lane} defaulted to premium opus: {model}"
            assert "sonnet" not in model.lower(), f"{lane} defaulted to premium sonnet: {model}"
            assert "gpt-4o" not in model, f"{lane} defaulted to premium gpt-4o: {model}"
            assert "gemini-2.5" not in model, f"{lane} defaulted to premium gemini-2.5: {model}"
        assert "o3" not in _MODEL and "opus" not in _MODEL.lower() and "gpt-4o" not in _MODEL
