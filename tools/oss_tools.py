"""Open-source capability tools — deterministic, no LLM.

Wires high-quality OSS libraries into the brain's tool registry so it can do
real work without any LLM:

  - trafilatura          → clean web-article extraction (research sourcing)
  - duckduckgo-search    → free web search (no API key)
  - pymupdf (fitz)       → fast PDF text extraction
  - ruff                 → modern Python linter (replace pylint)
  - bandit               → Python security scanner
  - markitdown (optional)→ Microsoft Office/PDF → Markdown

Every function is fail-soft: a missing module / network error returns a
structured {ok: False, error: ...} so the brain never crashes on a tool miss.
"""

from __future__ import annotations
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ============================================================================
# Web article extraction — trafilatura
# ============================================================================

def fetch_article(url: str, max_chars: int = 12000) -> Dict[str, Any]:
    """Extract the main article text from a URL (trafilatura)."""
    try:
        import trafilatura
    except ImportError as e:
        return {"ok": False, "error": f"trafilatura not installed: {e}"}
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return {"ok": False, "error": f"no content fetched from {url}"}
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
            output_format="txt",
        )
        if not text:
            return {"ok": False, "error": f"no extractable article at {url}"}
        return {
            "ok": True,
            "url": url,
            "text": text[:max_chars],
            "length": len(text),
            "truncated": len(text) > max_chars,
            "source": "trafilatura",
        }
    except Exception as e:
        logger.warning("[oss_tools] fetch_article failed: %s", e)
        return {"ok": False, "error": str(e)}


# ============================================================================
# Web search — duckduckgo-search (no API key)
# ============================================================================

def web_search(query: str, max_results: int = 8, region: str = "wt-wt") -> Dict[str, Any]:
    """Free web search via DuckDuckGo (no API key)."""
    try:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            # duckduckgo-search v8+ renamed to `ddgs`; support both.
            from ddgs import DDGS
    except ImportError as e:
        return {"ok": False, "error": f"duckduckgo-search not installed: {e}"}
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, region=region, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
        return {"ok": True, "query": query, "results": results, "count": len(results), "source": "duckduckgo"}
    except Exception as e:
        logger.warning("[oss_tools] web_search failed: %s", e)
        return {"ok": False, "error": str(e)}


def web_search_to_findings(query: str, max_results: int = 6) -> Dict[str, Any]:
    """Search + shape results into research-paper findings."""
    res = web_search(query, max_results=max_results)
    if not res.get("ok"):
        return res
    findings = [
        {
            "title": r["title"] or r["url"],
            "summary": r["snippet"],
            "url": r["url"],
            "source": "web",
        }
        for r in res.get("results", [])
        if r.get("url")
    ]
    return {"ok": True, "findings": findings, "count": len(findings), "source": "duckduckgo"}


# ============================================================================
# PDF text extraction — pymupdf
# ============================================================================

def extract_pdf(path_or_bytes: str, max_pages: int = 50, max_chars: int = 50000) -> Dict[str, Any]:
    """Extract text from a PDF file path or raw bytes (pymupdf)."""
    try:
        import pymupdf
    except ImportError as e:
        return {"ok": False, "error": f"pymupdf not installed: {e}"}
    try:
        if Path(path_or_bytes).exists():
            doc = pymupdf.open(path_or_bytes)
        else:
            doc = pymupdf.open(stream=path_or_bytes, filetype="pdf")
        pages = min(max_pages, doc.page_count)
        parts = []
        for i in range(pages):
            page = doc.load_page(i)
            parts.append(page.get_text("text"))
        doc.close()
        text = "\n\n".join(parts).strip()
        if not text:
            return {"ok": False, "error": "no extractable text in PDF"}
        return {
            "ok": True,
            "page_count": doc.page_count if False else pages,
            "text": text[:max_chars],
            "length": len(text),
            "truncated": len(text) > max_chars,
            "source": "pymupdf",
        }
    except Exception as e:
        logger.warning("[oss_tools] extract_pdf failed: %s", e)
        return {"ok": False, "error": str(e)}


# ============================================================================
# Code quality — ruff + bandit (deterministic, no LLM)
# ============================================================================

def lint_python(code_or_path: str) -> Dict[str, Any]:
    """Lint Python with ruff (fast, deterministic). Accepts code or a file path."""
    try:
        if Path(code_or_path).exists():
            args = ["ruff", "check", code_or_path]
        else:
            # Write code to a temp file and lint it.
            import tempfile
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
                f.write(code_or_path)
                tmp = f.name
            args = ["ruff", "check", tmp]
    except Exception as e:
        return {"ok": False, "error": str(e)}

    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=60)
        return {
            "ok": True,
            "clean": proc.returncode == 0,
            "output": (proc.stdout or proc.stderr).strip()[:4000],
            "source": "ruff",
        }
    except Exception as e:
        logger.warning("[oss_tools] lint_python failed: %s", e)
        return {"ok": False, "error": str(e)}


def scan_python_security(code_or_path: str) -> Dict[str, Any]:
    """Scan Python for security issues with bandit."""
    try:
        if Path(code_or_path).exists():
            args = ["bandit", "-q", "-r", code_or_path]
        else:
            import tempfile
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
                f.write(code_or_path)
                tmp = f.name
            args = ["bandit", "-q", tmp]
    except Exception as e:
        return {"ok": False, "error": str(e)}

    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=90)
        out = (proc.stdout or proc.stderr).strip()
        issues = 0
        import re
        for m in re.finditer(r"Severity:\s*(\w+)", out):
            issues += 1
        return {
            "ok": True,
            "issue_count": issues,
            "output": out[:4000],
            "source": "bandit",
        }
    except Exception as e:
        logger.warning("[oss_tools] scan_python_security failed: %s", e)
        return {"ok": False, "error": str(e)}


# ============================================================================
# Microsoft Office / rich docs → Markdown — markitdown (optional)
# ============================================================================

def convert_doc(path: str, max_chars: int = 50000) -> Dict[str, Any]:
    """Convert a Microsoft Office / PDF / HTML file to Markdown (markitdown)."""
    try:
        from markitdown import MarkItDown
    except ImportError as e:
        return {"ok": False, "error": f"markitdown not installed: {e}"}
    try:
        md = MarkItDown()
        result = md.convert(path)
        text = getattr(getattr(result, "text_content", None) or result, "text", "")
        if not text:
            return {"ok": False, "error": f"no extractable content in {path}"}
        return {
            "ok": True,
            "path": path,
            "text": text[:max_chars],
            "length": len(text),
            "truncated": len(text) > max_chars,
            "source": "markitdown",
        }
    except Exception as e:
        logger.warning("[oss_tools] convert_doc failed: %s", e)
        return {"ok": False, "error": str(e)}


# ============================================================================
# Combined research sourcer — used by the research-paper pipeline
# ============================================================================

def gather_web_findings(topic: str, max_results: int = 6) -> Dict[str, Any]:
    """DuckDuckGo search + trafilatura article extraction → research findings."""
    findings: List[Dict] = []
    errors: List[str] = []

    search = web_search(topic, max_results=max_results)
    if not search.get("ok"):
        errors.append(search.get("error", "web_search failed"))
    else:
        for r in search.get("results", []):
            url = r.get("url", "")
            if not url:
                continue
            findings.append({
                "title": r.get("title") or url,
                "summary": r.get("snippet", ""),
                "url": url,
                "source": "web",
            })
            # Deep-extract the top result for richer body text.
            if len(findings) == 1:
                art = fetch_article(url, max_chars=6000)
                if art.get("ok"):
                    findings[0]["body"] = art["text"]

    # If search failed but we got a direct URL, try article extraction.
    if not findings:
        for u in [t for t in [topic] if t.startswith("http")]:
            art = fetch_article(u, max_chars=12000)
            if art.get("ok"):
                findings.append({
                    "title": u,
                    "summary": art["text"][:400],
                    "url": u,
                    "body": art["text"],
                    "source": "web",
                })

    return {
        "ok": bool(findings) or not errors,
        "findings": findings,
        "count": len(findings),
        "errors": errors,
        "source": "duckduckgo+trafilatura",
    }
