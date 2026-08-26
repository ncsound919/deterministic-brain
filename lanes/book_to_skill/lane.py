"""Lane: book-to-skill — ground a book/topic via BookBridge, distill a skill stub, route to Draymond conversion."""
from __future__ import annotations
import os
from typing import Dict


def run(inputs: Dict) -> Dict:
    book_id = inputs.get("book_id", "")
    topic = inputs.get("topic", "")
    source = inputs.get("source", "")  # optional local path to a book file

    if not (book_id or topic or source):
        return {"error": "Provide book_id, topic, or source"}

    from tools.bookbridge_bridge import (
        bookbridge_status,
        bookbridge_distill,
        bookbridge_books,
        bookbridge_scan,
    )

    # 1. Health check — if offline, still allow direct-file distillation.
    status = bookbridge_status()
    if status.get("status") == "offline" and not source:
        return {
            "error": "BookBridge offline",
            "hint": "Start BookBridge (agents/BookBridge--main, python main.py --watch) or pass a local source path.",
            "status": status,
        }

    # 2. Trigger a scan so newly dropped books are ingested (best-effort).
    try:
        scan = bookbridge_scan()
        if "error" in scan:
            # Non-fatal — library may be mid-ingest.
            pass
    except Exception:
        pass

    # 3. If only a topic was given, list candidates to ground.
    candidate_books = []
    if topic and not book_id:
        books = bookbridge_books()
        candidate_books = books if isinstance(books, list) else books.get("books", [])

    # 4. Distill the book/topic into a skill stub under skill_packs/books.
    distill = bookbridge_distill(book_id=book_id, topic=topic)

    return {
        "success": True,
        "status": status,
        "candidate_books": candidate_books[:10],
        "distill": distill,
        "next": {
            "action": "book_to_skill_convert",
            "hint": "Run Draymond's book-to-skill-chain (Stage 3) to convert the source into a full agent skill, then register it.",
            "source": source or distill.get("skill_stub", ""),
        },
    }
