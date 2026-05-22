from __future__ import annotations
import os
import json
import time
import sqlite3
import hashlib
import logging
import atexit
import sys
from contextlib import closing
from typing import List, Dict, Optional, Tuple

import numpy as np

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

from config import cfg
from knowledge.fragment import KnowledgeFragment

logger = logging.getLogger(__name__)


class KnowledgeBankIndex:
    """Knowledge bank backed by Qdrant + SQLite snippets.

    Reuses the same MiniLM-L6 embedding pipeline for semantic search.
    """

    def __init__(self, db_path: str = "knowledge_bank/fragments.db",
                 model_name: str = "all-MiniLM-L6-v2"):
        self.db_path = db_path
        self.model_name = model_name
        self._model = None
        self._loaded = False
        
        self.url = cfg.qdrant_url
        self.api_key = cfg.qdrant_api_key
        
        try:
            if self.url and self.url != "http://localhost:6333":
                self.client = QdrantClient(url=self.url, api_key=self.api_key)
            else:
                os.makedirs(".qdrant_data", exist_ok=True)
                self.client = QdrantClient(path=".qdrant_data")
            
            # Register explicit close on exit to avoid meta_path None errors
            atexit.register(self.close)
        except Exception as e:
            if "already accessed by another instance" in str(e):
                logger.warning("Qdrant storage locked (bank). Using in-memory fallback.")
                self.client = QdrantClient(location=":memory:")
            else:
                raise e

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                self._model = False
        return self._model if self._model is not False else None

    def _embed_texts(self, texts: List[str]) -> np.ndarray | None:
        model = self.model
        if model is not None:
            return model.encode(
                texts, normalize_embeddings=True,
                batch_size=32, show_progress_bar=False,
            ).astype("float32")
        return self._fallback_embed(texts)

    def _fallback_embed(self, texts: List[str]) -> np.ndarray:
        dim = 128
        vecs = np.zeros((len(texts), dim), dtype="float32")
        for i, text in enumerate(texts):
            digest = hashlib.sha256(text.encode()).digest()
            raw = list(digest * 4)
            norm = np.array([(b / 127.5) - 1.0 for b in raw], dtype="float32")
            vecs[i] = norm / (np.linalg.norm(norm) + 1e-8)
        return vecs

    @property
    def loaded(self) -> bool:
        return self._loaded

    def _wal_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with closing(self._wal_conn()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS snippets (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '[]',
                    ts_created REAL NOT NULL,
                    ts_modified REAL NOT NULL
                )
            """)
            conn.commit()

        # Init Qdrant Collection
        try:
            collections = [c.name for c in self.client.get_collections().collections]
            if "fragments" not in collections:
                self.client.create_collection(
                    collection_name="fragments",
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                )
        except Exception as e:
            logger.error(f"Failed to init Qdrant collection: {e}")

    def load(self) -> bool:
        self.init_db()
        self._loaded = True
        return True

    def add_fragment(self, fragment: KnowledgeFragment, level: int = 0) -> bool:
        embed_text = f"{fragment.source_title}. {' '.join(fragment.tags)}. {fragment.chunk_text[:300]}"
        vecs = self._embed_texts([embed_text])
        if vecs is None:
            return False

        payload = {
            "source_type": fragment.source_type,
            "source_url": fragment.source_url,
            "source_title": fragment.source_title,
            "chunk_text": fragment.chunk_text,
            "tags": fragment.tags,
            "level": level,
            "build_relevance": fragment.build_relevance,
            "ts_ingested": fragment.ts_ingested,
            "ts_accessed": fragment.ts_accessed,
            "access_count": fragment.access_count,
            "confidence": fragment.confidence,
        }
        
        self.client.upsert(
            collection_name="fragments",
            points=[
                PointStruct(
                    id=fragment.id if '-' in fragment.id else hashlib.md5(fragment.id.encode()).hexdigest(),
                    vector=vecs[0].tolist(),
                    payload=payload
                )
            ]
        )
        return True

    def add_fragments(self, fragments: List[KnowledgeFragment]) -> int:
        count = 0
        for f in fragments:
            if self.add_fragment(f):
                count += 1
        return count

    def add(self, fragment: KnowledgeFragment) -> bool:
        return self.add_fragment(fragment)

    def add_snippet(self, fragment: KnowledgeFragment) -> bool:
        return self.save_snippet(fragment.source_title, fragment.chunk_text, fragment.tags) is not None

    def get_fragment(self, fragment_id: str) -> Optional[KnowledgeFragment]:
        qid = fragment_id if '-' in fragment_id else hashlib.md5(fragment_id.encode()).hexdigest()
        try:
            res = self.client.retrieve(collection_name="fragments", ids=[qid])
            if not res:
                return None
            return self._payload_to_fragment(qid, res[0].payload)
        except Exception:
            return None

    def query(self, text: str, top_k: int = 5) -> List[Tuple[KnowledgeFragment, float]]:
        vecs = self._embed_texts([text])
        if vecs is None:
            return []
            
        results = self.client.query_points(
            collection_name="fragments",
            query=vecs[0].tolist(),
            limit=top_k
        ).points
        
        ret = []
        for p in results:
            frag = self._payload_to_fragment(str(p.id), p.payload)
            frag.ts_accessed = time.time()
            frag.access_count += 1
            # In Qdrant, we just update the payload
            p.payload["ts_accessed"] = frag.ts_accessed
            p.payload["access_count"] = frag.access_count
            self.client.set_payload("fragments", payload=p.payload, points=[p.id])
            ret.append((frag, p.score))
        return ret

    def find_near_duplicates(self, threshold: float = 0.92) -> List[List[str]]:
        # Not easily supported in Qdrant without a full scan
        return []

    def merge_fragments(self, fragment_ids: List[str]):
        if len(fragment_ids) < 2:
            return
        
        qids = [fid if '-' in fid else hashlib.md5(fid.encode()).hexdigest() for fid in fragment_ids]
        points = self.client.retrieve("fragments", ids=qids)
        if not points:
            return
            
        keep = max(points, key=lambda p: p.payload.get("access_count", 0))
        to_delete = [p.id for p in points if p.id != keep.id]
        
        if to_delete:
            self.client.delete("fragments", points_selector=to_delete)

    def age_decay(self, stale_days: int = 30, decay_factor: float = 0.95):
        # Scan and update payload for stale fragments
        cutoff = time.time() - stale_days * 86400
        res, _ = self.client.scroll(
            collection_name="fragments",
            scroll_filter=Filter(must=[FieldCondition(key="confidence", range={"gt": 0.1})]),
            limit=1000
        )
        for p in res:
            if p.payload.get("ts_accessed", time.time()) < cutoff:
                p.payload["confidence"] = p.payload.get("confidence", 1.0) * decay_factor
                self.client.set_payload("fragments", payload=p.payload, points=[p.id])

    def prune_stale(self, min_confidence: float = 0.1):
        self.client.delete(
            collection_name="fragments",
            points_selector=Filter(
                must=[FieldCondition(key="confidence", range={"lt": min_confidence})]
            )
        )
        return 0

    def all_fragments(self) -> List[KnowledgeFragment]:
        res, _ = self.client.scroll(collection_name="fragments", limit=1000)
        return [self._payload_to_fragment(str(p.id), p.payload) for p in res]

    def fragments_by_source(self, source_type: str) -> List[KnowledgeFragment]:
        res, _ = self.client.scroll(
            collection_name="fragments",
            scroll_filter=Filter(must=[FieldCondition(key="source_type", match=MatchValue(value=source_type))]),
            limit=1000
        )
        return [self._payload_to_fragment(str(p.id), p.payload) for p in res]

    def fragments_by_tag(self, tag: str) -> List[KnowledgeFragment]:
        res, _ = self.client.scroll(
            collection_name="fragments",
            scroll_filter=Filter(must=[FieldCondition(key="tags", match=MatchValue(value=tag))]),
            limit=1000
        )
        return [self._payload_to_fragment(str(p.id), p.payload) for p in res]

    def cluster_by_tags(self, min_size: int = 5) -> Dict[str, List[KnowledgeFragment]]:
        all_frags = self.all_fragments()
        tag_map: Dict[str, List[KnowledgeFragment]] = {}
        for f in all_frags:
            for tag in f.tags:
                if tag not in tag_map:
                    tag_map[tag] = []
                tag_map[tag].append(f)
        return {tag: frags for tag, frags in tag_map.items()
                if len(frags) >= min_size}

    def get_snippet(self, snippet_id: str) -> Optional[dict]:
        with closing(self._wal_conn()) as conn:
            row = conn.execute(
                "SELECT * FROM snippets WHERE id=?", (snippet_id,)
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0], "title": row[1], "content": row[2],
            "tags": json.loads(row[3]), "ts_created": row[4], "ts_modified": row[5],
        }

    def save_snippet(self, title: str, content: str, tags: List[str] = None) -> dict:
        hid = hashlib.sha256((title + content).encode()).hexdigest()[:12]
        now = time.time()
        with closing(self._wal_conn()) as conn:
            existing = conn.execute(
                "SELECT id FROM snippets WHERE id=?", (hid,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE snippets SET content=?, tags=?, ts_modified=? WHERE id=?",
                    (content, json.dumps(tags or []), now, hid),
                )
            else:
                conn.execute(
                    "INSERT INTO snippets (id, title, content, tags, ts_created, ts_modified) "
                    "VALUES (?,?,?,?,?,?)",
                    (hid, title, content, json.dumps(tags or []), now, now),
                )
            conn.commit()
        return self.get_snippet(hid)

    def list_snippets(self) -> List[dict]:
        with closing(self._wal_conn()) as conn:
            rows = conn.execute(
                "SELECT * FROM snippets ORDER BY ts_modified DESC"
            ).fetchall()
        return [
            {
                "id": r[0], "title": r[1], "content": r[2],
                "tags": json.loads(r[3]), "ts_created": r[4], "ts_modified": r[5],
            }
            for r in rows
        ]

    def delete_snippet(self, snippet_id: str) -> bool:
        with closing(self._wal_conn()) as conn:
            conn.execute("DELETE FROM snippets WHERE id=?", (snippet_id,))
            conn.commit()
        return True

    def generate_ref_doc(self, tag: str, fragments: List[KnowledgeFragment]) -> str:
        os.makedirs("knowledge_bank/refs", exist_ok=True)
        path = f"knowledge_bank/refs/{tag}.md"
        lines = [
            f"# {tag} — Knowledge Reference",
            "",
            f"Auto-generated: {time.strftime('%Y-%m-%d %H:%M')}",
            f"Fragments: {len(fragments)}",
            "",
        ]
        for f in fragments:
            lines.append(f"## {f.source_title}")
            lines.append("")
            lines.append(f"- Source: {f.source_url}")
            lines.append(f"- Tags: {', '.join(f.tags)}")
            lines.append(f"- Confidence: {f.confidence:.2f}")
            lines.append(f"- Accessed: {f.access_count}x")
            lines.append("")
            lines.append(f.chunk_text)
            lines.append("")
        content = "\n".join(lines)
        with open(path, "w") as fh:
            fh.write(content)
        return path

    def stats(self) -> dict:
        total = self.client.count(collection_name="fragments").count
        
        try:
            with closing(self._wal_conn()) as conn:
                snippet_count = conn.execute("SELECT COUNT(*) FROM snippets").fetchone()[0]
        except Exception:
            snippet_count = 0

        refs_count = 0
        refs_dir = "knowledge_bank/refs"
        if os.path.exists(refs_dir):
            refs_count = len([f for f in os.listdir(refs_dir) if f.endswith(".md")])

        return {
            "total_fragments": total,
            "snippets": snippet_count,
            "refs": refs_count,
            "sources": {},
            "index_loaded": self._loaded,
            "index_size": total,
        }

    def _payload_to_fragment(self, fid: str, payload: dict) -> KnowledgeFragment:
        return KnowledgeFragment(
            id=fid,
            source_type=payload.get("source_type", ""),
            source_url=payload.get("source_url", ""),
            source_title=payload.get("source_title", ""),
            chunk_text=payload.get("chunk_text", ""),
            tags=payload.get("tags", []),
            build_relevance=payload.get("build_relevance", []),
            ts_ingested=payload.get("ts_ingested", 0.0),
            ts_accessed=payload.get("ts_accessed", 0.0),
            access_count=payload.get("access_count", 0),
            confidence=payload.get("confidence", 1.0),
        )

    def close(self):
        """Explicitly close the Qdrant client."""
        if hasattr(self, "client") and self.client:
            try:
                if sys.meta_path is not None:
                    self.client.close()
            except:
                pass


_BANK: Optional[KnowledgeBankIndex] = None


def get_knowledge_bank() -> KnowledgeBankIndex:
    global _BANK
    if _BANK is None:
        _BANK = KnowledgeBankIndex()
        _BANK.load()
    return _BANK


def reset_knowledge_bank() -> None:
    global _BANK
    _BANK = None
