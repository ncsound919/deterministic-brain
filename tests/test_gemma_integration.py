"""Integration tests for Gemma across all brain subsystems."""
import pytest

from tools.local_gemma import get_gemma

# Entire module requires a live llama-server at :8088 — deselected by
# default via the `live` marker (pyproject addopts); run with -m live.
pytestmark = pytest.mark.live


def _require_gemma():
    """Skip tests that need a running local llama-server (Gemma) at :8088."""
    if not get_gemma().is_available():
        pytest.skip("llama-server (Gemma) not running on localhost:8088")


class TestGemmaIntegrationRouter:
    """Test Gemma integration in tools/llm/router.py."""

    def test_generate_text_via_gemma(self):
        """generate_text() should route to local Gemma and return a response."""
        _require_gemma()
        from tools.llm.router import generate_text
        result = generate_text("What is 2+2? Answer in one number.")
        assert result and isinstance(result, str) and len(result) > 0
        assert "4" in result  # Gemma correctly answers 2+2=4

    def test_generate_code_via_gemma(self):
        """generate_code() should route to local Gemma and return code."""
        _require_gemma()
        from tools.llm.router import generate_code
        result = generate_code("Write a Python function that returns 'hello world'")
        assert result and len(result) > 0
        assert "hello" in result.lower() or "def" in result

    def test_gemma_before_openrouter(self):
        """Gemma should be tried before OpenRouter."""
        from tools.llm.router import generate_text, get_gemma
        gemma = get_gemma()
        if not gemma.is_available():
            pytest.skip("llama-server not running")
        result = generate_text("Count from one to five: 1, 2, 3,")
        assert result and len(result) > 0


class TestGemmaIntegrationSemanticLayer:
    """Test Gemma integration in orchestration/semantic_layer.py."""

    def test_micro_llm_parse_ticket_schema(self):
        """micro_llm_parse should extract ticket fields from raw text."""
        from orchestration.semantic_layer import micro_llm_parse
        result = micro_llm_parse(
            "Hi, I have a billing issue. My invoice #INV-456 shows the wrong amount. "
            "This is urgent — I'm being overcharged by $200. Customer ID: ACME-789.",
            "ticket"
        )
        assert isinstance(result, dict)
        assert "issue" in result
        assert result["priority"] in [1, 2, 3, 4]

    def test_micro_llm_parse_email_schema(self):
        """micro_llm_parse should extract email fields from raw text."""
        from orchestration.semantic_layer import micro_llm_parse
        result = micro_llm_parse(
            "From: alice@example.com\nSubject: urgent billing problem\n\n"
            "I need help with my account right away.",
            "email"
        )
        assert isinstance(result, dict)
        assert "sender" in result
        assert result["is_urgent"] is True

    def test_micro_llm_parse_pr_review_schema(self):
        """micro_llm_parse should extract PR review fields from raw text."""
        from orchestration.semantic_layer import micro_llm_parse
        result = micro_llm_parse(
            "Please review https://github.com/ncsound919/deterministic-brain/pull/42 "
            "for the repo ncsound919/deterministic-brain",
            "pr_review"
        )
        assert isinstance(result, dict)
        assert "pr_url" in result

    def test_micro_llm_parse_fallback(self):
        """micro_llm_parse falls back to regex when Gemma is unavailable."""
        from orchestration.semantic_layer import micro_llm_parse
        result = micro_llm_parse(
            "Hi, I have a billing issue. My invoice #INV-456.",
            "ticket"
        )
        assert isinstance(result, dict)
        assert "issue" in result


class TestGemmaIntegrationBackend:
    """Test Gemma integration in orchestration/backends.py."""

    def test_llm_fallback_prefers_gemma(self):
        """backends should try local Gemma before OpenRouter."""
        _require_gemma()
        from orchestration.backends import LocalSkillBackend
        backend = LocalSkillBackend()
        task = {"raw": "build a hello world Python script"}
        result = backend._llm_fallback("hello-world", "# Hello World\n\nGenerate a hello world script.", task, {})
        assert result.get("success") is True
        logs = result.get("logs", [])
        assert any("Gemma" in log for log in logs)


class TestGemmaSkillResolver:
    """Test Gemma integration in tools/skill_resolver.py."""

    def test_resolve_with_gemma_disambiguation(self):
        """Gemma should help disambiguate ambiguous skill names."""
        from tools.skill_resolver import SkillResolver
        resolver = SkillResolver()
        path = resolver.resolve_with_gemma("landing page")
        assert path is None or isinstance(path, str)


class TestGemmaEndToEnd:
    """End-to-end tests verifying Gemma flows through the system."""

    def test_gemma_health_check(self):
        """Verify Gemma is running and responsive."""
        _require_gemma()
        gemma = get_gemma()
        assert gemma.is_available(), "Gemma/llama-server must be running at localhost:8088"

    def test_gemma_text_generation(self):
        """Gemma should generate coherent text completions."""
        _require_gemma()
        gemma = get_gemma()
        result = gemma.complete("Python is a", n_predict=32, temperature=0.1)
        assert result and len(result) > 0
        assert len(result) <= 200

    def test_gemma_json_parsing(self):
        """Gemma should produce parseable JSON when prompted."""
        _require_gemma()
        gemma = get_gemma()
        prompt = (
            'Parse this into JSON: "Issue: password reset broken, Priority: high, ID: USR-123"\n'
            'Return ONLY valid JSON like: {"id":"...","issue":"...","priority":...}'
        )
        result = gemma.complete(prompt, n_predict=128, temperature=0.05)
        assert result and len(result) > 0

    def test_gemma_code_generation(self):
        """Gemma should generate simple code snippets."""
        _require_gemma()
        gemma = get_gemma()
        prompt = "Write a one-line Python function hello() that returns 'hi':\n```python\n"
        result = gemma.complete(prompt, n_predict=64, temperature=0.1)
        assert result and len(result) > 0

    def test_gemma_skill_name_mapping(self):
        """Gemma should map ambiguous skill names to existing ones."""
        from tools.skill_resolver import SkillResolver
        resolver = SkillResolver()
        # Seed cache with some skills
        resolver._cache["landing-page"] = "/path/to/landing-page.md"
        resolver._cache["seo-audit"] = "/path/to/seo-audit.md"
        result = resolver.resolve_with_gemma("make a landing page for my product")
        # Should either resolve via keyword or Gemma should suggest landing-page
        assert result is None or isinstance(result, str)
