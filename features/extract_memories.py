from __future__ import annotations
"""
EXTRACT_MEMORIES — Background memory extraction agent.

After each brain run, a background thread extracts key facts, preferences,
and context from the conversation and stores them in the memory store.
These memories are surfaced in future retrievals to personalise responses.
"""
import json
import threading
from datetime import datetime
from pathlib import Path
from tools.llm.router import chat

_STORE = Path('.memories.jsonl')
_lock = threading.Lock()

_SYSTEM = (
    'Extract persistent memories from this exchange. '
    'Return a JSON array of memory objects: '
    '[{"fact": str, "category": "preference|fact|context|skill", "importance": 1-5}]'
)


def extract_async(query: str, response: str, session_id: str = '') -> threading.Thread:
    """Fire-and-forget background extraction."""
    def _run():
        raw = chat(
            system=_SYSTEM,
            user=f'User: {query[:500]}\nAssistant: {response[:500]}',
            lane='cross_domain',
            max_tokens=512,
        )
        try:
            clean = raw.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
            memories = json.loads(clean)
            if not isinstance(memories, list):
                memories = []
        except Exception:
            memories = []
        ts = datetime.utcnow().isoformat()
        with _lock:
            with open(_STORE, 'a') as f:
                for m in memories:
                    m['ts'] = ts
                    m['session_id'] = session_id
                    f.write(json.dumps(m) + '\n')
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def recall(query: str, limit: int = 10) -> list[dict]:
    """Simple keyword recall from extracted memories."""
    if not _STORE.exists():
        return []
    q = query.lower()
    memories = [json.loads(l) for l in _STORE.read_text().strip().splitlines()]
    scored = [
        m for m in memories
        if any(w in str(m.get('fact', '')).lower() for w in q.split())
    ]
    scored.sort(key=lambda m: -m.get('importance', 1))
    return scored[:limit]


def all_memories(limit: int = 100) -> list[dict]:
    if not _STORE.exists():
        return []
    lines = _STORE.read_text().strip().splitlines()
    return [json.loads(l) for l in lines[-limit:]]
