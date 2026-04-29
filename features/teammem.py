from __future__ import annotations
"""
TEAMMEM — Shared team memory.

A team-shared key-value + semantic memory store. Multiple users/agents
can read and write to a shared namespace. Backed by a local JSON file
(or Qdrant collection when available).
"""
import json
import threading
from datetime import datetime
from pathlib import Path

_STORE = Path('.teammem.json')
_lock = threading.Lock()


def _load() -> dict:
    if _STORE.exists():
        return json.loads(_STORE.read_text())
    return {'namespace': 'default', 'entries': {}}


def _save(data: dict) -> None:
    _STORE.write_text(json.dumps(data, indent=2))


def write(key: str, value: str, author: str = 'brain', namespace: str = 'default') -> dict:
    with _lock:
        data = _load()
        entry = {
            'key': key,
            'value': value,
            'author': author,
            'namespace': namespace,
            'ts': datetime.utcnow().isoformat(),
        }
        data['entries'][key] = entry
        _save(data)
    return entry


def read(key: str) -> dict | None:
    data = _load()
    return data['entries'].get(key)


def search(query: str, limit: int = 10) -> list[dict]:
    data = _load()
    q = query.lower()
    matches = [
        e for e in data['entries'].values()
        if q in e['key'].lower() or q in str(e['value']).lower()
    ]
    return matches[:limit]


def list_keys(namespace: str = 'default') -> list[str]:
    data = _load()
    return [
        k for k, v in data['entries'].items()
        if v.get('namespace', 'default') == namespace
    ]


def delete(key: str) -> bool:
    with _lock:
        data = _load()
        if key in data['entries']:
            del data['entries'][key]
            _save(data)
            return True
    return False
