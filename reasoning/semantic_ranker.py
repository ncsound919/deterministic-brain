"""Flat semantic embedding index — dense integer-keyed skill matching.

Uses MiniLM-L6 (22MB model) to encode skill texts into 384-dim float vectors.
Stored as a single .npy matrix file (~130KB for 87 skills).
Query = single matrix multiply → top-k cosine scores in <1ms.
"""

from __future__ import annotations
import os
from typing import List, Optional, Tuple

import numpy as np


class FlatEmbeddingIndex:
    """Integer-keyed flat embedding index. No vector DB, no disk server."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self.ids: List[str] = []
        self.matrix: Optional[np.ndarray] = None  # shape (N, 384)

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def build(self, enriched: List[Tuple[str, str]], index_path: str = "skill_index.npy"):
        """Encode all enriched texts and build the index matrix."""
        texts = [text for _, text in enriched]
        self.ids = [sid for sid, _ in enriched]

        vecs = self.model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )
        self.matrix = vecs.astype("float32")

        if index_path:
            np.save(index_path, self.matrix)
            # Save IDs alongside
            id_path = index_path.replace(".npy", "_ids.json")
            import json
            json.dump(self.ids, open(id_path, "w"))

    def load(self, index_path: str = "skill_index.npy"):
        """Load a pre-built index from disk."""
        if not os.path.exists(index_path):
            return False
        self.matrix = np.load(index_path).astype("float32")
        id_path = index_path.replace(".npy", "_ids.json")
        if os.path.exists(id_path):
            import json
            self.ids = json.load(open(id_path))
        return True

    def query(self, text: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Encode query and return top-k (skill_id, cosine_score) pairs."""
        if self.matrix is None or len(self.ids) == 0:
            return []
        q = self.model.encode(
            [text], normalize_embeddings=True, show_progress_bar=False
        )
        scores = self.matrix @ q[0]  # (N, 384) @ (384,) = (N,)
        top = np.argpartition(scores, -top_k)[-top_k:]
        top = top[np.argsort(scores[top])[::-1]]
        return [(self.ids[i], float(scores[i])) for i in top]

    def find(self, text: str) -> Optional[Tuple[str, float]]:
        """Return the single best match, or None if no match found."""
        results = self.query(text, top_k=1)
        if results and results[0][1] > 0.3:
            return results[0]
        return None

    @property
    def size(self) -> int:
        return len(self.ids) if self.ids else 0
