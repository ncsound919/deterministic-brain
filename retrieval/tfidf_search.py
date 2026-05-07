"""TF-IDF semantic search — offline index, zero network, zero LLM."""
from __future__ import annotations
import os
import pickle
from typing import List, Tuple


class TFIDFSearch:
    """
    Offline TF-IDF search over a pre-built index.
    Build the index once with TFIDFSearch.build_index(docs, index_dir).
    """

    def __init__(self, index_dir: str = "retrieval/index"):
        self.index_dir = index_dir
        self._load()

    def _load(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        matrix_path = os.path.join(self.index_dir, "tfidf.pkl")
        docs_path   = os.path.join(self.index_dir, "docs.txt")
        vect_path   = os.path.join(self.index_dir, "vectorizer.pkl")
        if not os.path.exists(matrix_path):
            self.tfidf_matrix = None
            self.documents    = []
            self.vectorizer   = None
            return
        with open(matrix_path, "rb") as f:
            self.tfidf_matrix = pickle.load(f)
        with open(vect_path, "rb") as f:
            self.vectorizer = pickle.load(f)
        with open(docs_path) as f:
            self.documents = [l.strip() for l in f]

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        if self.tfidf_matrix is None:
            return []
        from sklearn.metrics.pairwise import cosine_similarity
        q_vec  = self.vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self.tfidf_matrix).flatten()
        top    = scores.argsort()[-top_k:][::-1]
        return [(self.documents[i], float(scores[i])) for i in top]

    @staticmethod
    def build_index(documents: List[str], index_dir: str = "retrieval/index"):
        from sklearn.feature_extraction.text import TfidfVectorizer
        os.makedirs(index_dir, exist_ok=True)
        vect   = TfidfVectorizer(stop_words="english", max_features=10000)
        matrix = vect.fit_transform(documents)
        with open(os.path.join(index_dir, "tfidf.pkl"), "wb") as f:
            pickle.dump(matrix, f)
        with open(os.path.join(index_dir, "vectorizer.pkl"), "wb") as f:
            pickle.dump(vect, f)
        with open(os.path.join(index_dir, "docs.txt"), "w") as f:
            f.write("\n".join(documents))
        print(f"Index built: {len(documents)} docs → {index_dir}")
