"""web_fetcher.py — replaces browser-harness as a lean Python tool.
Fetches, cleans, and chunks web pages. No Playwright, no Electron, no LLM.
For JS-heavy pages pass use_requests=False to fall back to urllib.
"""
from __future__ import annotations
import re
import urllib.request
import urllib.error
from typing import List, Dict


HEADERS = {
    "User-Agent": "DCA-WebFetcher/1.0 (deterministic-brain)",
    "Accept": "text/html,application/xhtml+xml",
}


class WebFetcher:
    """
    Minimal web agent:
      fetch(url)   → raw HTML string
      text(url)    → stripped plain text
      chunks(url)  → list of 200-word text chunks (for TF-IDF indexing)
      links(url)   → list of absolute hrefs found on the page
    """

    def fetch(self, url: str, timeout: int = 15) -> str:
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="ignore")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"WebFetcher: failed to fetch {url} — {exc}") from exc

    def text(self, url: str) -> str:
        html = self.fetch(url)
        return self._strip(html)

    def chunks(self, url: str, chunk_size: int = 200) -> List[str]:
        words = self.text(url).split()
        return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]

    def links(self, url: str) -> List[str]:
        html  = self.fetch(url)
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
        base  = "/".join(url.split("/")[:3])
        result = []
        for h in hrefs:
            if h.startswith("http"):
                result.append(h)
            elif h.startswith("/"):
                result.append(base + h)
        return list(dict.fromkeys(result))  # deduplicate, preserve order

    @staticmethod
    def _strip(html: str) -> str:
        text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.I)
        text = re.sub(r"<style[^>]*>[\s\S]*?</style>",  " ", text,  flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&[a-z]+;", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


# ── MCP tool wrapper ────────────────────────────────────────────────────────

_fetcher = WebFetcher()


def web_fetch(url: str) -> Dict:
    """MCP tool: fetch and clean a URL, return text + chunk count."""
    try:
        chunks = _fetcher.chunks(url)
        return {"success": True, "url": url, "chunks": chunks, "chunk_count": len(chunks)}
    except Exception as exc:
        return {"success": False, "url": url, "error": str(exc)}
