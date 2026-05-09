from __future__ import annotations
from typing import List
from knowledge.fragment import KnowledgeFragment, chunk_text


def ingest_web_url(url: str, tags: List[str] = None) -> List[KnowledgeFragment]:
    tags = tags or []
    try:
        from tools.web_fetcher import WebFetcher
        fetcher = WebFetcher()
        text = fetcher.text(url)
        title = _extract_title(text) or url.split("/")[-1] or url
        chunks = chunk_text(text, max_words=400)
        return [
            KnowledgeFragment.create(
                source_type="web",
                source_url=url,
                source_title=title,
                chunk_text=c,
                tags=tags,
            )
            for c in chunks
        ]
    except ImportError:
        import urllib.request
        import re
        req = urllib.request.Request(url, headers={
            "User-Agent": "DeterministicBrain-KnowledgeBank/1.0",
            "Accept": "text/html,application/xhtml+xml",
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                html = resp.read().decode(charset, errors="ignore")
        except Exception:
            return []

        text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.I)
        text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&[a-z]+;", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        title = _extract_title(html) or url.split("/")[-1] or url
        chunks = chunk_text(text, max_words=400)
        return [
            KnowledgeFragment.create(
                source_type="web",
                source_url=url,
                source_title=title,
                chunk_text=c,
                tags=tags,
            )
            for c in chunks
        ]


def _extract_title(html: str) -> str | None:
    import re
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
    if m:
        return m.group(1).strip()[:200]
    return None
