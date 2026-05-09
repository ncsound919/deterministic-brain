from __future__ import annotations
import os
import json
import time
import sqlite3
import hashlib
import logging
from typing import List, Dict, Optional, Tuple

import numpy as np

from knowledge.fragment import KnowledgeFragment

logger = logging.getLogger(__name__)


class KnowledgeBankIndex:
    """Knowledge bank backed by FlatEmbeddingIndex + SQLite storage.

    Reuses the same MiniLM-L6 embedding pipeline from semantic_ranker.py
    for zero-additional-dep semantic search over knowledge fragments.
    """

    def __init__(self, db_path: str = "knowledge_bank/fragments.db",
                 index_path: str = "knowledge_bank/index.npy",
                 model_name: str = "all-MiniLM-L6-v2"):
        self.db_path = db_path
        self.index_path = index_path
        self.model_name = model_name
        self._model = None
        self.matrix: Optional[np.ndarray] = None
        self.fragment_ids: List[str] = []
        self._loaded = False

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

    def init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fragments (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_title TEXT NOT NULL,
                chunk_text TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                build_relevance TEXT DEFAULT '[]',
                ts_ingested REAL NOT NULL,
                ts_accessed REAL NOT NULL,
                access_count INTEGER DEFAULT 0,
                confidence REAL DEFAULT 1.0
            )
        """)
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
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fragments_source_type ON fragments(source_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fragments_confidence ON fragments(confidence)
        """)
        conn.commit()
        conn.close()

    def load(self) -> bool:
        self.init_db()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id FROM fragments ORDER BY id"
        ).fetchall()
        self.fragment_ids = [r["id"] for r in rows]
        conn.close()

        if not self.fragment_ids:
            self._loaded = True
            return True

        id_path = self.index_path.replace(".npy", "_ids.json")
        if os.path.exists(self.index_path) and os.path.exists(id_path):
            self.matrix = np.load(self.index_path).astype("float32")
            with open(id_path) as f:
                stored_ids = json.load(f)
            if stored_ids == self.fragment_ids:
                self._loaded = True
                return True

        self.rebuild_index()
        self._loaded = True
        return True

    def rebuild_index(self):
        if not self.fragment_ids:
            self.matrix = None
            return

        texts = []
        conn = sqlite3.connect(self.db_path)
        for fid in self.fragment_ids:
            row = conn.execute(
                "SELECT source_title, tags, chunk_text FROM fragments WHERE id=?",
                (fid,)
            ).fetchone()
            if row:
                tags = json.loads(row[1])
                embed_text = f"{row[0]}. {' '.join(tags)}. {row[2][:300]}"
                texts.append(embed_text)
        conn.close()

        if texts:
            self.matrix = self._embed_texts(texts)
        else:
            self.matrix = None

        if self.matrix is not None:
            np.save(self.index_path, self.matrix)
        id_path = self.index_path.replace(".npy", "_ids.json")
        with open(id_path, "w") as f:
            json.dump(self.fragment_ids, f)

    def add_fragment(self, fragment: KnowledgeFragment) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO fragments
                   (id, source_type, source_url, source_title, chunk_text,
                    tags, build_relevance, ts_ingested, ts_accessed,
                    access_count, confidence)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (fragment.id, fragment.source_type, fragment.source_url,
                 fragment.source_title, fragment.chunk_text,
                 json.dumps(fragment.tags), json.dumps(fragment.build_relevance),
                 fragment.ts_ingested, fragment.ts_accessed,
                 fragment.access_count, fragment.confidence),
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to add fragment {fragment.id}: {e}")
            conn.close()
            return False
        conn.close()

        if fragment.id not in self.fragment_ids:
            self.fragment_ids.append(fragment.id)
            self.rebuild_index()
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
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT * FROM fragments WHERE id=?", (fragment_id,)
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return self._row_to_fragment(row)

    def query(self, text: str, top_k: int = 5) -> List[Tuple[KnowledgeFragment, float]]:
        if self.matrix is None or not self.fragment_ids:
            return []
        try:
            q_vecs = self._embed_texts([text])
            if q_vecs is None:
                return []
        except Exception:
            return []
        scores = self.matrix @ q_vecs[0]
        top = np.argpartition(scores, -min(top_k, len(scores)))[-top_k:]
        top = top[np.argsort(scores[top])[::-1]]

        results = []
        conn = sqlite3.connect(self.db_path)
        for i in top:
            fid = self.fragment_ids[i]
            score = float(scores[i])
            row = conn.execute(
                "SELECT * FROM fragments WHERE id=?", (fid,)
            ).fetchone()
            if row:
                frag = self._row_to_fragment(row)
                frag.ts_accessed = time.time()
                frag.access_count += 1
                conn.execute(
                    "UPDATE fragments SET ts_accessed=?, access_count=? WHERE id=?",
                    (frag.ts_accessed, frag.access_count, fid),
                )
                conn.commit()
                results.append((frag, score))
        conn.close()
        return results

    def find_near_duplicates(self, threshold: float = 0.92) -> List[List[str]]:
        if self.matrix is None or len(self.fragment_ids) < 2:
            return []
        sim = self.matrix @ self.matrix.T
        groups = []
        seen = set()
        for i in range(len(self.fragment_ids)):
            if i in seen:
                continue
            group = [self.fragment_ids[i]]
            seen.add(i)
            for j in range(i + 1, len(self.fragment_ids)):
                if j in seen:
                    continue
                if sim[i, j] > threshold:
                    group.append(self.fragment_ids[j])
                    seen.add(j)
            if len(group) > 1:
                groups.append(group)
        return groups

    def merge_fragments(self, fragment_ids: List[str]):
        if len(fragment_ids) < 2:
            return
        conn = sqlite3.connect(self.db_path)
        rows = []
        for fid in fragment_ids:
            row = conn.execute(
                "SELECT * FROM fragments WHERE id=?", (fid,)
            ).fetchone()
            if row:
                rows.append(row)
        if not rows:
            conn.close()
            return

        keep = max(rows, key=lambda r: r[5])  # highest access_count
        for row in rows:
            if row[0] == keep[0]:
                continue
            conn.execute("DELETE FROM fragments WHERE id=?", (row[0],))
            if row[0] in self.fragment_ids:
                self.fragment_ids.remove(row[0])
        conn.commit()
        conn.close()

    def age_decay(self, stale_days: int = 30, decay_factor: float = 0.95):
        conn = sqlite3.connect(self.db_path)
        cutoff = time.time() - stale_days * 86400
        conn.execute(
            "UPDATE fragments SET confidence = confidence * ? "
            "WHERE ts_accessed < ? AND confidence > 0.1",
            (decay_factor, cutoff),
        )
        conn.commit()
        conn.close()

    def prune_stale(self, min_confidence: float = 0.1):
        conn = sqlite3.connect(self.db_path)
        removed = conn.execute(
            "DELETE FROM fragments WHERE confidence < ?", (min_confidence,)
        )
        count = removed.rowcount
        conn.commit()
        if count:
            rows = conn.execute("SELECT id FROM fragments ORDER BY id").fetchall()
            self.fragment_ids = [r[0] for r in rows]
            conn.close()
            self.rebuild_index()
        else:
            conn.close()
        return count

    def all_fragments(self) -> List[KnowledgeFragment]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT * FROM fragments ORDER BY ts_ingested DESC").fetchall()
        conn.close()
        return [self._row_to_fragment(r) for r in rows]

    def fragments_by_source(self, source_type: str) -> List[KnowledgeFragment]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT * FROM fragments WHERE source_type=? ORDER BY ts_ingested DESC",
            (source_type,),
        ).fetchall()
        conn.close()
        return [self._row_to_fragment(r) for r in rows]

    def fragments_by_tag(self, tag: str) -> List[KnowledgeFragment]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT * FROM fragments").fetchall()
        conn.close()
        return [self._row_to_fragment(r) for r in rows
                if tag in json.loads(r[4])]  # tags column

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
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT * FROM snippets WHERE id=?", (snippet_id,)
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return {
            "id": row[0], "title": row[1], "content": row[2],
            "tags": json.loads(row[3]), "ts_created": row[4], "ts_modified": row[5],
        }

    def save_snippet(self, title: str, content: str, tags: List[str] = None) -> dict:
        hid = hashlib.sha256((title + content).encode()).hexdigest()[:12]
        now = time.time()
        conn = sqlite3.connect(self.db_path)
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
        conn.close()
        return self.get_snippet(hid)

    def list_snippets(self) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT * FROM snippets ORDER BY ts_modified DESC"
        ).fetchall()
        conn.close()
        return [
            {
                "id": r[0], "title": r[1], "content": r[2],
                "tags": json.loads(r[3]), "ts_created": r[4], "ts_modified": r[5],
            }
            for r in rows
        ]

    def delete_snippet(self, snippet_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM snippets WHERE id=?", (snippet_id,))
        conn.commit()
        conn.close()
        return True

    def generate_ref_doc(self, tag: str, fragments: List[KnowledgeFragment]) -> str:
        os.makedirs("knowledge_bank/refs", exist_ok=True)
        path = f"knowledge_bank/refs/{tag}.md"
        lines = [
            f"# {tag} — Knowledge Reference",
            f"",
            f"Auto-generated: {time.strftime('%Y-%m-%d %H:%M')}",
            f"Fragments: {len(fragments)}",
            f"",
        ]
        for f in fragments:
            lines.append(f"## {f.source_title}")
            lines.append(f"")
            lines.append(f"- Source: {f.source_url}")
            lines.append(f"- Tags: {', '.join(f.tags)}")
            lines.append(f"- Confidence: {f.confidence:.2f}")
            lines.append(f"- Accessed: {f.access_count}x")
            lines.append(f"")
            lines.append(f.chunk_text)
            lines.append(f"")
        content = "\n".join(lines)
        with open(path, "w") as fh:
            fh.write(content)
        return path

    def stats(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        total = conn.execute("SELECT COUNT(*) FROM fragments").fetchone()[0]
        sources = conn.execute(
            "SELECT source_type, COUNT(*) as cnt FROM fragments "
            "GROUP BY source_type ORDER BY cnt DESC"
        ).fetchall()
        snippet_count = conn.execute("SELECT COUNT(*) FROM snippets").fetchone()[0]
        conn.close()

        refs_count = 0
        refs_dir = "knowledge_bank/refs"
        if os.path.exists(refs_dir):
            refs_count = len([f for f in os.listdir(refs_dir) if f.endswith(".md")])

        return {
            "total_fragments": total,
            "snippets": snippet_count,
            "refs": refs_count,
            "sources": {s[0]: s[1] for s in sources},
            "index_loaded": self._loaded,
            "index_size": self.matrix.shape[0] if self.matrix is not None else 0,
        }

    def _row_to_fragment(self, row) -> KnowledgeFragment:
        return KnowledgeFragment(
            id=row[0],
            source_type=row[1],
            source_url=row[2],
            source_title=row[3],
            chunk_text=row[4],
            tags=json.loads(row[5]),
            build_relevance=json.loads(row[6]),
            ts_ingested=row[7],
            ts_accessed=row[8],
            access_count=row[9],
            confidence=row[10],
        )


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
