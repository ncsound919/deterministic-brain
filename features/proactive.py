from __future__ import annotations
"""
PROACTIVE — Proactive autonomous mode.

Monitors a watch list of topics/repos/queries and autonomously runs
the brain on them on a schedule. Results are stored and surfaced via
the API at GET /proactive/results.
"""
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from tools.tracing import log_event

_STORE = Path('.proactive_results.jsonl')
_WATCH: list[dict] = []  # [{"id": str, "query": str, "interval_s": int, "last_run": float}]
_lock = threading.Lock()
_running = False


def register(query: str, interval_s: int = 3600, watch_id: str | None = None) -> dict:
    """Register a query for proactive autonomous monitoring."""
    entry = {
        'id': watch_id or f'watch_{len(_WATCH)+1}',
        'query': query,
        'interval_s': interval_s,
        'last_run': 0.0,
        'created': datetime.utcnow().isoformat(),
    }
    with _lock:
        _WATCH.append(entry)
    return entry


def _run_one(entry: dict) -> None:
    from orchestration.langgraph_app import build_app
    brain = build_app()
    try:
        result = brain.run(entry['query'])
        record = {
            'watch_id': entry['id'],
            'ts': datetime.utcnow().isoformat(),
            'query': entry['query'],
            'lane': result.get('lane', ''),
            'final_output': result.get('final_output', '')[:500],
            'confidence': result.get('confidence', 0),
        }
        with open(_STORE, 'a') as f:
            f.write(json.dumps(record) + '\n')
        log_event('proactive_run', record)
    except Exception as exc:
        log_event('proactive_error', {'watch_id': entry['id'], 'error': str(exc)})


def _loop() -> None:
    global _running
    while _running:
        now = time.time()
        with _lock:
            due = [e for e in _WATCH if now - e['last_run'] >= e['interval_s']]
        for entry in due:
            entry['last_run'] = now
            t = threading.Thread(target=_run_one, args=(entry,), daemon=True)
            t.start()
        time.sleep(10)


def start() -> None:
    global _running
    if not _running:
        _running = True
        threading.Thread(target=_loop, daemon=True).start()


def stop() -> None:
    global _running
    _running = False


def get_results(limit: int = 50) -> list[dict]:
    if not _STORE.exists():
        return []
    lines = _STORE.read_text().strip().splitlines()
    return [json.loads(l) for l in lines[-limit:]]


def list_watches() -> list[dict]:
    return list(_WATCH)
