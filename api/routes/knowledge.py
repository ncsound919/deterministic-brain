"""Knowledge bank API routes."""
from __future__ import annotations
import logging
from typing import Optional, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class IngestRequest(BaseModel):
    url: str
    title: Optional[str] = None
    tags: Optional[list[str]] = None


class IngestTextRequest(BaseModel):
    text: str
    title: Optional[str] = None
    tags: Optional[list[str]] = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 3


class SnippetCreateRequest(BaseModel):
    text: str
    title: str
    tags: Optional[list[str]] = None


def _get_bank():
    from knowledge.bank import get_knowledge_bank
    return get_knowledge_bank()


@router.get("/stats")
def knowledge_stats():
    bank = _get_bank()
    return {"status": "ok" if bank.loaded else "unloaded", "stats": bank.stats() if bank.loaded else {}}


@router.post("/ingest")
def knowledge_ingest(req: IngestRequest):
    bank = _get_bank()
    result = bank.ingest_url(req.url, title=req.title, tags=req.tags or [])
    return {"status": "ok", "snippet_id": result}


@router.post("/ingest-text")
def knowledge_ingest_text(req: IngestTextRequest):
    bank = _get_bank()
    result = bank.ingest_text(req.text, title=req.title, tags=req.tags or [])
    return {"status": "ok", "snippet_id": result}


@router.post("/search")
def knowledge_search(req: SearchRequest):
    bank = _get_bank()
    fragments = bank.query(req.query, top_k=req.top_k)
    results = [
        {"text": f.chunk_text, "title": f.source_title, "tags": f.tags, "confidence": f.confidence}
        for f, score in fragments
    ]
    return {"results": results}


@router.get("/fragments")
def knowledge_fragments():
    bank = _get_bank()
    return {"fragments": bank.list_fragments() if hasattr(bank, "list_fragments") else []}


@router.get("/snippets")
def knowledge_snippets():
    bank = _get_bank()
    return {"snippets": bank.list_snippets() if hasattr(bank, "list_snippets") else []}


@router.post("/snippets")
def knowledge_create_snippet(req: SnippetCreateRequest):
    bank = _get_bank()
    result = bank.add_snippet(req.text, title=req.title, tags=req.tags or [])
    return {"status": "ok", "snippet_id": result}


@router.delete("/snippets/{snippet_id}")
def knowledge_delete_snippet(snippet_id: str):
    bank = _get_bank()
    bank.remove_snippet(snippet_id)
    return {"status": "deleted"}


@router.post("/generate-refs")
def knowledge_generate_refs():
    bank = _get_bank()
    count = bank.generate_refs()
    return {"status": "ok", "refs_generated": count}


@router.post("/consolidate")
def knowledge_consolidate(dry_run: bool = False):
    from brain.autodream import consolidate_knowledge_bank
    return consolidate_knowledge_bank(dry_run=dry_run)
