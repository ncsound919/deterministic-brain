"""Tests for the deterministic research-paper publisher (zero-LLM).

The research-paper skill pack renders a structured paper from sourced findings
and publishes it to Overlay Global Lens /api/publish — all without any LLM.

Run with:  pytest tests/test_research_publisher.py -v
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestRenderPaper:
    def test_render_with_inline_findings_is_deterministic(self):
        from features.research_publisher import get_publisher

        p = get_publisher()
        findings = [
            {"title": "Finding A", "summary": "Summary of A", "url": "https://example.com/a", "source": "inline"},
            {"title": "Finding B", "summary": "Summary of B", "url": "https://example.com/b", "source": "inline"},
        ]
        r1 = p.render_paper("test topic", findings, title="Test Paper", category="eng", pillar="platform", generated_at="2026-01-01T00:00:00")
        r2 = p.render_paper("test topic", findings, title="Test Paper", category="eng", pillar="platform", generated_at="2026-01-01T00:00:00")

        assert r1["ok"] is True
        # Deterministic: identical inputs → identical body.
        assert r1["body"] == r2["body"]
        assert "Finding A" in r1["body"]
        assert "Finding B" in r1["body"]
        assert "deterministic" in r1["body"].lower()
        assert r1["finding_count"] == 2

    def test_render_handles_empty_findings(self):
        from features.research_publisher import get_publisher

        p = get_publisher()
        r = p.render_paper("empty topic", [], title="Empty Paper")
        assert r["ok"] is True
        assert "No findings were provided" in r["body"]

    def test_render_writes_build_file(self):
        from features.research_publisher import get_publisher

        p = get_publisher()
        r = p.render_paper("file topic", [{"title": "X", "summary": "Y", "source": "inline"}])
        assert r["ok"] is True
        path = Path(r["path"])
        assert path.exists()
        assert path.read_text(encoding="utf-8").strip() == r["body"]


class TestGatherWebSources:
    def test_gather_sources_includes_web_findings(self, monkeypatch):
        """DuckDuckGo + trafilatura web sourcing feeds the paper."""
        from tools import oss_tools

        def fake_gather(topic, max_results=5):
            return {
                "ok": True,
                "findings": [
                    {
                        "title": "Web Article",
                        "summary": "A web-sourced snippet",
                        "url": "https://example.com/article",
                        "body": "The full article body text for the paper.",
                        "source": "web",
                    }
                ],
                "count": 1,
            }

        monkeypatch.setattr(oss_tools, "gather_web_findings", fake_gather)

        from features.research_publisher import get_publisher

        findings = get_publisher().gather_sources("web topic")
        web = [f for f in findings if f.get("source") == "web"]
        assert web, "web-sourced finding missing"
        assert web[0]["title"] == "Web Article"
        assert web[0]["body"]

    def test_web_sources_render_in_paper_and_references(self, monkeypatch):
        from tools import oss_tools

        def fake_gather(topic, max_results=5):
            return {
                "ok": True,
                "findings": [
                    {
                        "title": "Web Article",
                        "summary": "A web-sourced snippet",
                        "url": "https://example.com/article",
                        "body": "The full article body text for the paper.",
                        "source": "web",
                    }
                ],
                "count": 1,
            }

        monkeypatch.setattr(oss_tools, "gather_web_findings", fake_gather)

        from features.research_publisher import get_publisher

        r = get_publisher().render_paper(
            "web topic",
            [{"title": "Web Article", "summary": "A web-sourced snippet",
              "url": "https://example.com/article",
              "body": "The full article body text for the paper.",
              "source": "web"}],
            generated_at="2026-01-01T00:00:00",
        )
        assert r["ok"] is True
        assert any(s.startswith("Web:") for s in r["sources"]), r["sources"]
        assert "The full article body text" in r["body"]


class TestPublishPayload:
    def test_publish_posts_correct_shape(self, monkeypatch):
        from features.research_publisher import get_publisher

        captured = {}

        class FakeResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b'{"ok": true, "inserted": true}'

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["data"] = json.loads(req.data.decode("utf-8"))
            return FakeResponse()

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        p = get_publisher()
        result = p.publish_to_global_lens(
            "Test Title",
            "paper body",
            category="engineering",
            source_name="Brain",
            paper={"id": "brain-x", "title": "Test Title"},
        )

        assert result.get("ok") is True
        assert captured["url"] == "http://localhost:3090/api/publish"
        data = captured["data"]
        assert data["title"] == "Test Title"
        assert data["body"] == "paper body"
        assert data["category"] == "engineering"
        assert data["source_name"] == "Brain"
        assert data["paper"]["id"] == "brain-x"
