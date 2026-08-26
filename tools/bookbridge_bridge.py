
import requests
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

BOOKBRIDGE_URL = "http://127.0.0.1:8777"

def bookbridge_search(query: str, max_results: int = 5, include_equations: bool = False) -> Dict[str, Any]:
    """Search the personal book library for knowledge and equations."""
    try:
        resp = requests.post(
            f"{BOOKBRIDGE_URL}/search",
            json={
                "query": query,
                "max_results": max_results,
                "include_equations": include_equations
            },
            timeout=10
        )
        return resp.json()
    except Exception as e:
        logger.error(f"BookBridge search failed: {e}")
        return {"error": str(e)}

def bookbridge_retrieve(book_id: str, page_start: int, page_end: int) -> Dict[str, Any]:
    """Retrieve full text for a specific page range from a book."""
    try:
        resp = requests.post(
            f"{BOOKBRIDGE_URL}/retrieve",
            json={
                "book_id": book_id,
                "page_start": page_start,
                "page_end": page_end
            },
            timeout=15
        )
        # Note: If it's a streaming response in the actual server, we might need to collect it
        return {"content": resp.text}
    except Exception as e:
        logger.error(f"BookBridge retrieve failed: {e}")
        return {"error": str(e)}

def bookbridge_reading_plan(topic: str, goal: str = "") -> Dict[str, Any]:
    """Generate a prioritized reading plan for a research topic."""
    try:
        resp = requests.post(
            f"{BOOKBRIDGE_URL}/reading_plan",
            json={"topic": topic, "goal": goal},
            timeout=20
        )
        return resp.json()
    except Exception as e:
        logger.error(f"BookBridge reading plan failed: {e}")
        return {"error": str(e)}

def bookbridge_status() -> Dict[str, Any]:
    """Check BookBridge server health and index stats."""
    try:
        resp = requests.get(f"{BOOKBRIDGE_URL}/health", timeout=2)
        return resp.json()
    except Exception:
        return {"status": "offline"}


def bookbridge_books(tags: str = "", author: str = "") -> Dict[str, Any]:
    """List the indexed book library, optionally filtered by tag or author."""
    try:
        params = {}
        if tags:
            params["tag"] = tags
        if author:
            params["author"] = author
        resp = requests.get(f"{BOOKBRIDGE_URL}/books", params=params, timeout=10)
        return resp.json()
    except Exception as e:
        logger.error(f"BookBridge list failed: {e}")
        return {"error": str(e)}


def bookbridge_cite(book_id: str, style: str = "APA", page_start: int = None, page_end: int = None) -> Dict[str, Any]:
    """Format a citation for a book in the requested style."""
    try:
        payload = {"book_id": book_id, "style": style}
        if page_start:
            payload["page_start"] = page_start
        if page_end:
            payload["page_end"] = page_end
        resp = requests.post(f"{BOOKBRIDGE_URL}/citation", json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        logger.error(f"BookBridge citation failed: {e}")
        return {"error": str(e)}


def bookbridge_summarize(book_id: str, page_start: int = 1, page_end: int = 1, max_sentences: int = 5) -> Dict[str, Any]:
    """Summarize a page range of a book."""
    try:
        resp = requests.post(
            f"{BOOKBRIDGE_URL}/summarize",
            json={
                "book_id": book_id,
                "page_start": page_start,
                "page_end": page_end,
                "max_sentences": max_sentences,
            },
            timeout=20,
        )
        return resp.json()
    except Exception as e:
        logger.error(f"BookBridge summarize failed: {e}")
        return {"error": str(e)}


def bookbridge_scan() -> Dict[str, Any]:
    """Trigger a library scan so newly added books are ingested."""
    try:
        resp = requests.post(f"{BOOKBRIDGE_URL}/scan", json={"force": False}, timeout=30)
        return resp.json()
    except Exception as e:
        logger.error(f"BookBridge scan failed: {e}")
        return {"error": str(e)}


def bookbridge_distill(book_id: str = "", topic: str = "") -> Dict[str, Any]:
    """Distill a book (by id) or a topic (by search) into a skill stub.

    Grounds passages from the library, then emits a skill.md stub under
    skill_packs/books/ for the SkillRegistry to pick up. This is the
    deterministic-brain half of the book-to-skill chain; the heavy
    conversion happens in Draymond's book-to-skill converter.
    """
    import os
    import re

    grounded = []
    if book_id:
        src = bookbridge_summarize(book_id, page_start=1, page_end=10)
        if "error" not in src:
            grounded.append(src)
    if topic:
        results = bookbridge_search(topic, max_results=5)
        for r in (results.get("results") or []):
            grounded.append({
                "book_id": r.get("book_id"),
                "book_title": r.get("book_title"),
                "text": r.get("text", "")[:600],
                "citation_ready": r.get("citation_ready", ""),
            })

    if not grounded:
        return {"error": "No grounded passages found (BookBridge offline or empty library)"}

    slug = re.sub(r"[^a-z0-9]+", "-", (topic or book_id or "book").lower()).strip("-")
    slug = slug[:48] or "book-skill"
    out_dir = os.path.join("skill_packs", "books", slug)
    os.makedirs(out_dir, exist_ok=True)
    stub = f"""---
skill: {slug}
version: 1.0
source: bookbridge
inputs:
  query: string
tools: [bookbridge_search, bookbridge_retrieve, bookbridge_cite]
audit: []
monte_carlo: false
---
## Step 1
Ground: call bookbridge_search for the topic and collect cited passages.

## Step 2
Synthesize: extract the author's frameworks, principles, and techniques
from the passages below, keeping citations.

## Step 3
Emit skill.md under Draymond's agents/skills for full book-to-skill
conversion and registry registration.

Grounded passages:
"""
    for i, g in enumerate(grounded, 1):
        stub += f"\n[{i}] {g.get('book_title', g.get('book_id', ''))}: {g.get('text', '')} ({g.get('citation_ready', 'no citation')})\n"

    stub_path = os.path.join(out_dir, "skill.md")
    with open(stub_path, "w", encoding="utf-8") as f:
        f.write(stub)

    return {"success": True, "skill_stub": stub_path, "grounded_passages": len(grounded)}
