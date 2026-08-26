"""Tests for the deterministic OSS capability tools (no LLM).

Covers trafilatura article extraction, DuckDuckGo web search, PyMuPDF PDF
extraction, ruff linting, bandit security scanning, markitdown doc conversion,
and the combined research sourcer used by research_publisher.

Run with:  pytest tests/test_oss_tools.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class FakeModule:
    def __init__(self, **attrs):
        self.__dict__.update(attrs)


class TestFetchArticle:
    def test_missing_trafilatura_returns_fail_soft(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "trafilatura":
                raise ImportError("no trafilatura")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        from tools.oss_tools import fetch_article

        result = fetch_article("https://example.com/a")
        assert result["ok"] is False
        assert "trafilatura" in result["error"]

    def test_extracts_article(self, monkeypatch):
        trafilatura = FakeModule()
        trafilatura.fetch_url = lambda url: f"<html><body>{url} content</body></html>"
        trafilatura.extract = lambda *a, **k: "The extracted article body."
        monkeypatch.setitem(sys.modules, "trafilatura", trafilatura)

        from tools.oss_tools import fetch_article

        result = fetch_article("https://example.com/a")
        assert result["ok"] is True
        assert result["text"] == "The extracted article body."
        assert result["source"] == "trafilatura"

    def test_no_extractable_content(self, monkeypatch):
        trafilatura = FakeModule()
        trafilatura.fetch_url = lambda url: "<html></html>"
        trafilatura.extract = lambda *a, **k: None
        monkeypatch.setitem(sys.modules, "trafilatura", trafilatura)

        from tools.oss_tools import fetch_article

        result = fetch_article("https://example.com/a")
        assert result["ok"] is False


class TestWebSearch:
    def test_missing_ddgs_returns_fail_soft(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "duckduckgo_search":
                raise ImportError("no ddgs")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        from tools.oss_tools import web_search

        result = web_search("hello")
        assert result["ok"] is False
        assert "duckduckgo-search" in result["error"]

    def test_returns_results(self, monkeypatch):
        hits = [
            {"title": "Result A", "href": "https://a.com", "body": "Snippet A"},
            {"title": "Result B", "href": "https://b.com", "body": "Snippet B"},
        ]

        class FakeDDGS:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def text(self, query, region="wt-wt", max_results=8):
                return hits

        ddgs = FakeModule(DDGS=FakeDDGS)
        monkeypatch.setitem(sys.modules, "duckduckgo_search", ddgs)

        from tools.oss_tools import web_search

        result = web_search("hello", max_results=2)
        assert result["ok"] is True
        assert result["count"] == 2
        assert result["results"][0]["url"] == "https://a.com"
        assert result["source"] == "duckduckgo"

    def test_web_search_to_findings_shapes_results(self, monkeypatch):
        hits = [{"title": "R", "href": "https://r.com", "body": "Snip"}]

        class FakeDDGS:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def text(self, query, region="wt-wt", max_results=8):
                return hits

        monkeypatch.setitem(sys.modules, "duckduckgo_search", FakeModule(DDGS=FakeDDGS))

        from tools.oss_tools import web_search_to_findings

        result = web_search_to_findings("hello")
        assert result["ok"] is True
        finding = result["findings"][0]
        assert finding["title"] == "R"
        assert finding["url"] == "https://r.com"
        assert finding["source"] == "web"


class TestExtractPdf:
    def test_missing_pymupdf_returns_fail_soft(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pymupdf":
                raise ImportError("no pymupdf")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        from tools.oss_tools import extract_pdf

        result = extract_pdf("nonexistent.pdf")
        assert result["ok"] is False
        assert "pymupdf" in result["error"]

    def test_extracts_pdf_text(self, monkeypatch, tmp_path):
        page = FakeModule()
        page.get_text = lambda mode="text": "PDF line one.\nPDF line two."

        doc = FakeModule(page_count=1)
        doc.load_page = lambda i: page
        doc.close = lambda: None

        pymupdf = FakeModule(open=lambda *a, **k: doc)
        monkeypatch.setitem(sys.modules, "pymupdf", pymupdf)

        from tools.oss_tools import extract_pdf

        result = extract_pdf(str(tmp_path / "does-not-exist.pdf"))
        assert result["ok"] is True
        assert "PDF line one." in result["text"]
        assert result["source"] == "pymupdf"


class TestLintPython:
    def test_missing_ruff_binary_returns_fail_soft(self, monkeypatch):
        monkeypatch.setenv("PATH", "")

        from tools.oss_tools import lint_python

        result = lint_python("def foo():\n    pass\n")
        assert result["ok"] is False
        assert "error" in result

    def test_lints_code_string(self, monkeypatch, tmp_path):
        import subprocess

        def fake_run(args, capture_output, text, timeout):
            assert args[0] == "ruff"
            assert args[1] == "check"
            return subprocess.CompletedProcess(args, 0, stdout="All checks passed", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        from tools.oss_tools import lint_python

        result = lint_python("x = 1\n")
        assert result["ok"] is True
        assert result["clean"] is True
        assert result["source"] == "ruff"


class TestScanPythonSecurity:
    def test_scans_and_counts_issues(self, monkeypatch, tmp_path):
        import subprocess

        bandit_output = (
            ">> Issue: [B501:request_with_no_cert_validation] "
            "Severity: Medium Confidence: High\n"
            ">> Issue: [B602:shell_injection] Severity: High Confidence: High\n"
        )

        def fake_run(args, capture_output, text, timeout):
            assert args[0] == "bandit"
            return subprocess.CompletedProcess(args, 1, stdout=bandit_output, stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        from tools.oss_tools import scan_python_security

        result = scan_python_security("x = 1\n")
        assert result["ok"] is True
        assert result["issue_count"] == 2
        assert result["source"] == "bandit"


class TestConvertDoc:
    def test_missing_markitdown_returns_fail_soft(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "markitdown":
                raise ImportError("no markitdown")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        from tools.oss_tools import convert_doc

        result = convert_doc("doc.docx")
        assert result["ok"] is False
        assert "markitdown" in result["error"]


class TestGatherWebFindings:
    def test_combines_search_and_extraction(self, monkeypatch):
        hits = [{"title": "R", "href": "https://r.com", "body": "Snip"}]

        class FakeDDGS:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def text(self, query, region="wt-wt", max_results=8):
                return hits

        monkeypatch.setitem(sys.modules, "duckduckgo_search", FakeModule(DDGS=FakeDDGS))

        trafilatura = FakeModule()
        trafilatura.fetch_url = lambda url: "<html>body</html>"
        trafilatura.extract = lambda *a, **k: "Full article body for the top result."
        monkeypatch.setitem(sys.modules, "trafilatura", trafilatura)

        from tools.oss_tools import gather_web_findings

        result = gather_web_findings("hello", max_results=2)
        assert result["ok"] is True
        assert result["count"] >= 1
        first = result["findings"][0]
        assert first["url"] == "https://r.com"
        assert "Full article body" in first.get("body", "")
