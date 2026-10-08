"""
RemoteVectorMemory — the brain's vector memory served by the Cloudflare
`vec-memory` Worker (Workers AI embeddings + D1 store).

Same public surface as VectorMemory, selected automatically when
`BRAIN_VECTOR_URL` is set. Loads NO local qdrant and NO sentence-transformers,
so the local CPU/RAM cost of embedding + the vector DB is gone.

    export BRAIN_VECTOR_URL=https://vec-memory.tap4500.workers.dev
"""
import os
import json
import uuid
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional

from loguru import logger


_UA = "dev-brain-vecmemory/1.0"


def _post(url: str, path: str, payload: dict, timeout: int = 60) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url.rstrip("/") + path, data=data,
        headers={"content-type": "application/json", "accept": "application/json", "user-agent": _UA},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _get(url: str, path: str, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        url.rstrip("/") + path, headers={"accept": "application/json", "user-agent": _UA}, method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


class RemoteVectorMemory:
    def __init__(self, url: Optional[str] = None):
        self.url = (url or os.environ["BRAIN_VECTOR_URL"]).rstrip("/")
        self.vector_size = 384
        logger.info(f"VectorMemory: REMOTE mode -> {self.url} (no local qdrant/sentence-transformers)")

    # ── writes ────────────────────────────────────────────────────────────────
    def _upsert(self, collection: str, content: str, meta: Dict[str, Any]) -> None:
        _post(self.url, "/upsert", {"items": [{
            "id": meta.get("id"), "text": content, "collection": collection, "meta": meta,
        }]})

    def add_conversation(self, content: str, role: str, metadata: Optional[Dict] = None) -> str:
        eid = str(uuid.uuid4())
        meta = dict(metadata or {})
        meta.update({"role": role, "timestamp": datetime.now().isoformat(), "type": "conversation", "content": content, "id": eid})
        self._upsert("conversations", content, meta)
        return eid

    def add_skill(self, name: str, description: str, workflow: List[Dict], success_rate: float = 0.0) -> str:
        eid = str(uuid.uuid5(uuid.NAMESPACE_OID, name))
        content = f"{name}: {description}\nWorkflow: {workflow}"
        meta = {"name": name, "description": description, "success_rate": success_rate, "timestamp": datetime.now().isoformat(), "type": "skill", "content": content, "id": eid}
        self._upsert("skills", content, meta)
        return eid

    def add_knowledge(self, content: str, category: str, source: Optional[str] = None) -> str:
        eid = str(uuid.uuid4())
        meta = {"category": category, "source": source or "unknown", "timestamp": datetime.now().isoformat(), "type": "knowledge", "content": content, "id": eid}
        self._upsert("knowledge", content, meta)
        return eid

    def add_to_thread(self, thread_name: str, content: str, metadata: Optional[Dict] = None) -> str:
        eid = str(uuid.uuid4())
        meta = dict(metadata or {})
        meta.update({"thread": thread_name, "timestamp": datetime.now().isoformat(), "content": content, "id": eid})
        self._upsert("threads", content, meta)
        return eid

    # ── reads ─────────────────────────────────────────────────────────────────
    def _search(self, collection: str, query: str, n: int, where: Optional[Dict] = None) -> List[Dict]:
        body: Dict[str, Any] = {"query": query, "topK": n, "collection": collection}
        if where:
            body["whereJson"] = json.dumps(where)
        r = _post(self.url, "/query", body)
        return [
            {"id": m.get("id"), "content": m.get("content", ""), "metadata": m.get("metadata", {}), "distance": m.get("score")}
            for m in r.get("matches", [])
        ]

    def search_conversations(self, query: str, n_results: int = 5, filter_metadata: Optional[Dict] = None) -> List[Dict]:
        return self._search("conversations", query, n_results, filter_metadata)

    def search_skills(self, query: str, n_results: int = 3) -> List[Dict]:
        return self._search("skills", query, n_results)

    def search_knowledge(self, query: str, category: Optional[str] = None, n_results: int = 5) -> List[Dict]:
        return self._search("knowledge", query, n_results, {"category": category} if category else None)

    def search_thread(self, thread_name: str, query: str, n_results: int = 5) -> List[Dict]:
        return self._search("threads", query, n_results, {"thread": thread_name})

    def get_recent_context(self, limit: int = 10, thread: Optional[str] = None) -> List[Dict]:
        coll = "threads" if thread else "conversations"
        q = f"/recent?collection={coll}&limit={limit}"
        if thread:
            q += "&whereJson=" + urllib.parse.quote(json.dumps({"thread": thread}))
        r = _get(self.url, q)
        entries = r.get("entries", [])
        entries.sort(key=lambda x: (x.get("metadata", {}) or {}).get("timestamp", ""), reverse=True)
        return entries[:limit]

    def clear_thread(self, thread_name: str) -> None:
        q = "/recent?collection=threads&limit=500&whereJson=" + urllib.parse.quote(json.dumps({"thread": thread_name}))
        ids = [e.get("id") for e in _get(self.url, q).get("entries", [])]
        if ids:
            _post(self.url, "/delete", {"ids": ids})
        logger.info(f"Cleared thread (remote): {thread_name}")

    def get_stats(self) -> Dict:
        try:
            s = _get(self.url, "/stats")
            return {"total_entries": s.get("vectors", 0), "remote": True, "model": s.get("model"), "dims": s.get("dims")}
        except Exception:
            return {}

    def close(self) -> None:
        pass
