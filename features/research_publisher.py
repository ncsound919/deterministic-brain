"""Research Paper Publisher — deterministic research-paper generation + Global Lens publish.

Zero-LLM research paper pipeline for the deterministic brain:

  1. Gather sources (arXiv / news / market / wiki via the tool registry, or the
     caller's inline findings). Fail-soft: when a source tool is unreachable it
     is skipped — the paper still renders from whatever was gathered.
  2. Render the `research-paper` skill pack's Jinja2 template (paper.md.j2)
     with the gathered context.
  3. Write the rendered paper to a build dir.
  4. POST it to Overlay Global Lens `/api/publish` (idempotent: Global Lens
     hashes source+title+body and INSERT OR IGNOREs).

This is the brain's answer to "still create research papers when LLMs are down":
it uses the deterministic skill packs + free research APIs, never an LLM.
"""
from __future__ import annotations

import json
import os
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Config (env-driven, defaults for local fleet) ──────────────────────────
GLOBAL_LENS_URL = os.getenv("GLOBAL_LENS_URL", os.getenv("GL_URL", "http://localhost:3090"))
GL_PUBLISH_KEY = os.getenv("GL_PUBLISH_KEY", "")
SKILL_PACKS_ROOT = os.getenv(
    "SKILL_PACKS_ROOT",
    str(Path(__file__).resolve().parent.parent / "skill_packs"),
)
BUILDS_ROOT = os.getenv("BRAIN_BUILDS_ROOT", "builds")
PUBLISH_TIMEOUT = float(os.getenv("GL_PUBLISH_TIMEOUT", "30"))


class ResearchPublisher:
    """Deterministic research-paper generation + Global Lens publishing."""

    def __init__(self, builds_root: str = BUILDS_ROOT):
        self.builds_root = Path(builds_root)
        self.builds_root.mkdir(parents=True, exist_ok=True)

    # ── Sourcing (fail-soft, no LLM) ──────────────────────────────────────

    def gather_sources(self, topic: str, inline: Optional[List[Dict]] = None) -> List[Dict]:
        """Gather findings for a topic from the free research tools.

        Each tool is best-effort: a timeout/error skips that source. Inline
        findings (provided by the caller) are always kept first.
        """
        findings: List[Dict] = []
        seen: set = set()

        def add(f: Dict):
            title = str(f.get("title", "")).strip()
            if not title or title in seen:
                return
            seen.add(title)
            findings.append(f)

        for f in inline or []:
            add(f)

        # arXiv search — free, no key, deterministic.
        try:
            from tools.more_free_apis import ArxivClient
            ax = ArxivClient()
            res = ax.search(topic, max_results=5)
            if res.get("ok"):
                for p in res.get("papers", []):
                    add({
                        "title": p.get("title", ""),
                        "summary": p.get("summary", ""),
                        "url": p.get("url", ""),
                        "authors": p.get("authors", []),
                        "source": "arxiv",
                    })
        except Exception as e:
            logger.warning("[research_publisher] arxiv search skipped: %s", e)

        # News — free RSS, deterministic keyword extraction.
        try:
            from tools.news_client import fetch_news
            topics = topic.lower().split()
            for item in (fetch_news() or {}).get("headlines", [])[:20]:
                title = item.get("title", "")
                if topics and not any(t in title.lower() for t in topics):
                    continue
                add({
                    "title": title,
                    "summary": title,
                    "url": item.get("link", ""),
                    "source": "news",
                })
        except Exception as e:
            logger.warning("[research_publisher] news skipped: %s", e)

        # Wikipedia summary — free, no key.
        try:
            from tools.free_api_clients import WikipediaClient
            wp = WikipediaClient()
            summary = wp.summary(topic)
            if summary:
                add({
                    "title": f"Wikipedia: {topic}",
                    "summary": str(summary)[:800],
                    "url": f"https://en.wikipedia.org/wiki/{topic.replace(' ', '_')}",
                    "source": "wikipedia",
                })
        except Exception as e:
            logger.warning("[research_publisher] wikipedia skipped: %s", e)

        # Web search + article extraction — DuckDuckGo (no key) + trafilatura.
        # Fail-soft: if the OSS tools aren't installed or the network is down,
        # the paper still renders from the deterministic sources above.
        try:
            from tools.oss_tools import gather_web_findings
            web = gather_web_findings(topic, max_results=5)
            if web.get("ok"):
                for f in web.get("findings", []):
                    add({
                        "title": f.get("title", ""),
                        "summary": (f.get("summary") or "")[:800],
                        "url": f.get("url", ""),
                        "body": (f.get("body") or "")[:6000],
                        "source": "web",
                    })
        except Exception as e:
            logger.warning("[research_publisher] web sourcing skipped: %s", e)

        return findings

    # ── Rendering (Jinja2 from the skill pack template, no LLM) ───────────

    def render_paper(
        self,
        topic: str,
        findings: List[Dict],
        title: Optional[str] = None,
        abstract: Optional[str] = None,
        category: Optional[str] = None,
        pillar: Optional[str] = None,
        source_name: Optional[str] = None,
        extra_sources: Optional[List[str]] = None,
        generated_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Render the research-paper skill template. Returns paper + metadata."""
        try:
            from jinja2 import Template
        except ImportError as e:
            return {"ok": False, "error": f"jinja2 required: {e}"}

        template_path = Path(SKILL_PACKS_ROOT) / "research-paper" / "templates" / "paper.md.j2"
        if not template_path.exists():
            return {"ok": False, "error": f"template missing: {template_path}"}

        sources = [
            *[f"arXiv: {f['title']} — {f.get('url', '')}" for f in findings if f.get("source") == "arxiv"],
            *[f"News: {f['title']} — {f.get('url', '')}" for f in findings if f.get("source") == "news"],
            *[f"Wikipedia: {f['title']} — {f.get('url', '')}" for f in findings if f.get("source") == "wikipedia"],
            *[f"Web: {f['title']} — {f.get('url', '')}" for f in findings if f.get("source") == "web"],
            *[s for s in (extra_sources or []) if isinstance(s, str) and s.strip()],
        ]

        ctx = {
            "topic": topic,
            "title": title or topic,
            "abstract": abstract or "",
            "findings": findings,
            "sources": sources,
            "category": category or "general",
            "pillar": pillar or "research",
            "source_name": source_name or "Overlay365",
            "generated_at": generated_at or datetime.utcnow().isoformat(),
            "finding_count": len(findings),
        }

        try:
            tmpl = Template(template_path.read_text(encoding="utf-8"))
            paper = tmpl.render(**ctx).strip()
        except Exception as e:
            logger.error("[research_publisher] render failed: %s", e)
            return {"ok": False, "error": f"render failed: {e}"}

        if not paper:
            return {"ok": False, "error": "rendered empty paper"}

        # Stable build id derived from content, NOT wall-clock time. Time-based
        # ids made every re-publish of the same paper generate a fresh id, so the
        # Global Lens paper attachment (keyed on id) inserted a duplicate row on
        # every run. Hashing title+source keeps re-publishes idempotent; the
        # leading source_name disambiguates distinct publishers.
        build_id = hashlib.sha256(
            f"{source_name or 'brain'}:{title or topic}".encode()
        ).hexdigest()[:12]
        build_dir = self.builds_root / build_id
        build_dir.mkdir(parents=True, exist_ok=True)
        path = build_dir / "research_paper.md"
        path.write_text(paper, encoding="utf-8")

        return {
            "ok": True,
            "build_id": build_id,
            "path": str(path),
            "title": ctx["title"],
            "body": paper,
            "finding_count": len(findings),
            "sources": sources,
        }

    # ── Publishing (Global Lens /api/publish, idempotent) ─────────────────

    def publish_to_global_lens(
        self,
        title: str,
        body: str,
        category: str = "global",
        source_name: str = "Overlay365",
        url: str = "",
        paper: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """POST a finished paper/article to Overlay Global Lens `/api/publish`."""
        base = GLOBAL_LENS_URL.rstrip("/")
        if not base:
            return {"ok": False, "error": "GLOBAL_LENS_URL not configured"}

        payload = {
            "title": title,
            "body": body,
            "category": category,
            "source_name": source_name,
            "url": url,
            **({"paper": paper} if paper else {}),
        }

        headers = {"Content-Type": "application/json"}
        if GL_PUBLISH_KEY:
            headers["Authorization"] = f"Bearer {GL_PUBLISH_KEY}"

        try:
            import urllib.request

            req = urllib.request.Request(
                f"{base}/api/publish",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=PUBLISH_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = {"raw": raw}
                parsed["http_status"] = resp.status
                return parsed
        except Exception as e:
            logger.error("[research_publisher] publish failed: %s", e)
            return {"ok": False, "error": f"publish failed: {e}"}

    # ── One-shot pipeline ─────────────────────────────────────────────────

    def create_and_publish(
        self,
        topic: str,
        *,
        title: Optional[str] = None,
        abstract: Optional[str] = None,
        findings: Optional[List[Dict]] = None,
        category: str = "global",
        pillar: str = "research",
        source_name: str = "Overlay365 Deterministic Brain",
        url: str = "",
        publish: bool = True,
        attach_paper: bool = True,
    ) -> Dict[str, Any]:
        """End-to-end: source → render → (optionally) publish to Global Lens."""
        gathered = self.gather_sources(topic, inline=findings)

        rendered = self.render_paper(
            topic=topic,
            findings=gathered,
            title=title,
            abstract=abstract,
            category=category,
            pillar=pillar,
            source_name=source_name,
        )
        if not rendered.get("ok"):
            return rendered

        result = {
            "ok": True,
            "build_id": rendered["build_id"],
            "path": rendered["path"],
            "title": rendered["title"],
            "finding_count": rendered["finding_count"],
            "sources": rendered["sources"],
        }

        if publish:
            paper_meta = None
            if attach_paper:
                paper_meta = {
                    "id": f"brain-{rendered['build_id']}",
                    "title": rendered["title"],
                    "authors": source_name,
                    "abstract": abstract or rendered["body"][:500],
                    "summary": rendered["body"][:1000],
                    "category": category,
                    "pillar": pillar,
                    "evidence_tier": "E1",
                    "url": url,
                    "payload": {"build_id": rendered["build_id"], "generation_mode": "deterministic"},
                }
            result["publish"] = self.publish_to_global_lens(
                title=rendered["title"],
                body=rendered["body"],
                category=category,
                source_name=source_name,
                url=url,
                paper=paper_meta,
            )

        return result


_PUBLISHER: Optional[ResearchPublisher] = None


def get_publisher() -> ResearchPublisher:
    global _PUBLISHER
    if _PUBLISHER is None:
        _PUBLISHER = ResearchPublisher()
    return _PUBLISHER


def publish_research(
    topic: str,
    findings: Optional[List[Dict]] = None,
    title: Optional[str] = None,
    category: str = "global",
    pillar: str = "research",
) -> Dict[str, Any]:
    """MCP/tool entrypoint: deterministic research paper → Global Lens."""
    return get_publisher().create_and_publish(
        topic=topic,
        title=title,
        findings=findings,
        category=category,
        pillar=pillar,
    )
