"""Science-domain embeddings for paper retrieval (PubMedNCL + SciRus-tiny).

Scoped to research-paper chunks from features/research_publisher.py. Runs on
sentence-transformers (already a dependency of vector_memory.py) instead of
Ollama so the general fleet memory keeps using nomic-embed-text untouched.

Models:
  - malteos/PubMedNCL            110M biomed citation-graph encoder, 768-dim
  - mlsa-iai-msu-lab/sci-rus-tiny  23M multilingual scientific encoder, 312-dim

Usage:
    from tools.science_embeddings import get_science_embedder
    emb = get_science_embedder("pubmedncl")        # or "scirus"
    vecs = emb.encode(["title abstract text..."])
"""
from __future__ import annotations

import logging
import threading
from typing import List, Optional

logger = logging.getLogger(__name__)

MODELS = {
    "pubmedncl": "malteos/PubMedNCL",
    "scirus": "mlsa-iai-msu-lab/sci-rus-tiny",
}

_LOCK = threading.Lock()
_CACHE: dict = {}


class ScienceEmbedder:
    def __init__(self, name: str):
        if name not in MODELS:
            raise ValueError(f"unknown science embedder '{name}', expected one of {list(MODELS)}")
        self.name = name
        self.model_id = MODELS[name]
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self.model_id)

    def encode(self, texts: List[str]):
        return self._model.encode(texts, show_progress_bar=False)

    @property
    def dimension(self) -> int:
        return int(self._model.get_sentence_embedding_dimension())


def get_science_embedder(name: str = "pubmedncl") -> ScienceEmbedder:
    key = name.lower().replace("-", "").replace("_", "")
    canonical = {"pubmedncl": "pubmedncl", "scirus": "scirus", "sci-rus-tiny": "scirus"}.get(key)
    if canonical is None:
        raise ValueError(f"unknown science embedder '{name}'")
    with _LOCK:
        if canonical not in _CACHE:
            _CACHE[canonical] = ScienceEmbedder(canonical)
            logger.info("science_embeddings loaded %s (%s)", canonical, MODELS[canonical])
        return _CACHE[canonical]


def available() -> List[str]:
    """Embedders whose weights are present locally or fetchable."""
    out = []
    for key, model_id in MODELS.items():
        try:
            from sentence_transformers import SentenceTransformer  # noqa: F401
            out.append(key)
        except Exception:  # noqa: BLE001
            pass
    return out
