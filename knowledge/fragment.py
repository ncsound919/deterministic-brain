from __future__ import annotations
import hashlib
import time
import json
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class KnowledgeFragment:
    id: str
    source_type: str
    source_url: str
    source_title: str
    chunk_text: str
    tags: List[str] = field(default_factory=list)
    build_relevance: List[str] = field(default_factory=list)
    ts_ingested: float = field(default_factory=time.time)
    ts_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    confidence: float = 1.0

    def to_embed_text(self) -> str:
        return f"{self.source_title}. {' '.join(self.tags)}. {self.chunk_text[:300]}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "chunk_text": self.chunk_text,
            "tags": self.tags,
            "build_relevance": self.build_relevance,
            "ts_ingested": self.ts_ingested,
            "ts_accessed": self.ts_accessed,
            "access_count": self.access_count,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> KnowledgeFragment:
        return cls(
            id=d["id"],
            source_type=d.get("source_type", "unknown"),
            source_url=d.get("source_url", ""),
            source_title=d.get("source_title", ""),
            chunk_text=d.get("chunk_text", ""),
            tags=d.get("tags", []),
            build_relevance=d.get("build_relevance", []),
            ts_ingested=d.get("ts_ingested", time.time()),
            ts_accessed=d.get("ts_accessed", time.time()),
            access_count=d.get("access_count", 0),
            confidence=d.get("confidence", 1.0),
        )

    @classmethod
    def create(cls, source_type: str, source_url: str, source_title: str,
               chunk_text: str, tags: List[str] = None,
               build_relevance: List[str] = None) -> KnowledgeFragment:
        h = hashlib.sha256(chunk_text.encode()).hexdigest()[:12]
        return cls(
            id=h,
            source_type=source_type,
            source_url=source_url,
            source_title=source_title,
            chunk_text=chunk_text,
            tags=tags or [],
            build_relevance=build_relevance or [],
        )


def chunk_text(text: str, max_words: int = 400, overlap: int = 50) -> List[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + max_words])
        chunks.append(chunk)
        i += max_words - overlap
    return chunks


def chunk_text_sentences(text: str, max_sentences: int = 5, max_words: int = 400) -> List[str]:
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = []
    current_len = 0
    for s in sentences:
        wc = len(s.split())
        if current and (len(current) >= max_sentences or current_len + wc > max_words):
            chunks.append(" ".join(current))
            current = []
            current_len = 0
        current.append(s)
        current_len += wc
    if current:
        chunks.append(" ".join(current))
    if not chunks:
        chunks = [text]
    return chunks
