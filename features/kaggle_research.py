"""Kaggle Research Feed — pull a Kaggle dataset and make it research-ready.

Bridges the Kaggle data provider into the research stack:

1. `feed_dataset(ref)` — download the dataset as a deterministic snapshot
   (features/kaggle_manager) and ingest it into the knowledge bank as
   searchable fragments (knowledge.sources.kaggle).
2. Optionally rebuild the TF-IDF offline index from snapshot text so the
   retrieval layer can serve it with zero network/LLM.
3. `list_feeds()` — enumerate what has already been fed into research.

Keeps the deterministic-brain guarantee: snapshots are content-hashed and
cached, and ingestion is deterministic text chunking (no LLM).
"""
from __future__ import annotations
import os
from typing import Dict, List, Optional

DEFAULT_DATA_DIR = os.getenv("KAGGLE_DATA_DIR", "datasets/kaggle")


class KaggleResearchFeed:
    def __init__(self, data_dir: str = DEFAULT_DATA_DIR):
        self.data_dir = data_dir

    def feed_dataset(self, ref: str, tags: Optional[List[str]] = None,
                     force: bool = False, index_tfidf: bool = True) -> Dict:
        """Download a dataset snapshot and ingest it into the research stack."""
        from features.kaggle_manager import get_kaggle
        kg = get_kaggle()
        snap = kg.download_dataset(ref, force=force)
        if snap.get("status") != "ok":
            return snap

        snapshot_dir = snap.get("dir", "")
        # 1. Ingest into knowledge bank as fragments
        bank_result = self._ingest_to_bank(snapshot_dir, ref, tags or [])
        # 2. Rebuild TF-IDF index (best-effort)
        tfidf = self._rebuild_tfidf(snapshot_dir) if index_tfidf else {"status": "skipped"}

        return {
            "status": "ok",
            "ref": ref,
            "snapshot_dir": snapshot_dir,
            "content_hash": snap.get("content_hash", ""),
            "knowledge_bank": bank_result,
            "tfidf": tfidf,
        }

    def _ingest_to_bank(self, snapshot_dir: str, ref: str, tags: List[str]) -> Dict:
        from knowledge.ingester import get_ingester
        frags = get_ingester().ingest_kaggle_snapshot(snapshot_dir, ref, tags)
        added = 0
        bank_status = "unavailable"
        try:
            from knowledge.bank import get_knowledge_bank
            bank = get_knowledge_bank()
            if not bank.loaded:
                bank.load()
            if bank.loaded:
                added = bank.add_fragments(frags)
                bank_status = "ok"
        except Exception:
            bank_status = "unavailable"
        return {
            "status": bank_status,
            "fragments_created": len(frags),
            "fragments_added": added,
        }

    def _rebuild_tfidf(self, snapshot_dir: str) -> Dict:
        from knowledge.sources.kaggle import _DATA_EXTS
        try:
            from retrieval.tfidf_search import TFIDFSearch
        except Exception:
            return {"status": "skipped", "reason": "tfidf_search_not_available"}
        docs: List[str] = []
        for root, _dirs, files in os.walk(snapshot_dir):
            for name in files:
                if name == "manifest.json":
                    continue
                ext = os.path.splitext(name)[1].lower()
                if ext not in _DATA_EXTS:
                    continue
                try:
                    with open(os.path.join(root, name), "r", encoding="utf-8", errors="ignore") as f:
                        docs.append(f.read())
                except Exception:
                    continue
        if not docs:
            return {"status": "skipped", "reason": "no_text_documents"}
        try:
            index_dir = "retrieval/index"
            TFIDFSearch.build_index(docs, index_dir)
            return {"status": "ok", "documents": len(docs), "index_dir": index_dir}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def list_feeds(self) -> List[Dict]:
        from features.kaggle_manager import get_kaggle
        return get_kaggle().list_snapshots()

    def feed_status(self, ref: str) -> Dict:
        from features.kaggle_manager import get_kaggle
        snap = get_kaggle().download_dataset(ref)
        return snap


_FEED: Optional[KaggleResearchFeed] = None


def get_kaggle_research() -> KaggleResearchFeed:
    global _FEED
    if _FEED is None:
        _FEED = KaggleResearchFeed()
    return _FEED
