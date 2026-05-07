from __future__ import annotations
"""
AGENT_TRIGGERS — Scheduled cron agents.

Allows registering queries as cron-scheduled triggers. At the scheduled
time the brain autonomously runs the query and stores the result.
Built on Python's schedule library (falls back to threading-based timer).
"""
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from tools.tracing import log_event

_STORE = Path('.agent_triggers.json')
_RESULTS = Path('.agent_trigger_results.jsonl')
_TRIGGERS: list[dict] = []
_lock = threading.Lock()
_running = False


def register(query: str, cron: str = '0 * * * *', trigger_id: str | None = None) -> dict:
    """
    Register a cron-scheduled agent trigger.
    cron format: 'interval_seconds' (int as string) or standard cron string.
    For simplicity we support 'every_N_seconds' as an integer string.
    """
    entry = {
        'id': trigger_id or f'trigger_{len(_TRIGGERS)+1}',
        'query': query,
        'cron': cron,
        'interval_s': int(cron) if cron.isdigit() else 3600,
        'last_run': 0.0,
        'created': datetime.utcnow().isoformat(),
        'run_count': 0,
    }
    with _lock:
        _TRIGGERS.append(entry)
    _persist()
    return entry


def _persist() -> None:
    _STORE.write_text(json.dumps(_TRIGGERS, indent=2))


def _run_trigger(entry: dict) -> None:
    from orchestration.langgraph_app import build_app
    brain = build_app()
    try:
        result = brain.run(entry['query'])
        record = {
            'trigger_id': entry['id'],
            'ts': datetime.utcnow().isoformat(),
            'query': entry['query'],
            'output': result.get('final_output', '')[:500],
            'confidence': result.get('confidence', 0),
        }
        with open(_RESULTS, 'a') as f:
            f.write(json.dumps(record) + '\n')
        entry['run_count'] += 1
        log_event('trigger_fired', {'id': entry['id'], 'query': entry['query'][:60]})
    except Exception as exc:
        log_event('trigger_error', {'id': entry['id'], 'error': str(exc)})


def _loop() -> None:
    global _running
    while _running:
        now = time.time()
        with _lock:
            due = [e for e in _TRIGGERS if now - e['last_run'] >= e['interval_s']]
        for entry in due:
            entry['last_run'] = now
            threading.Thread(target=_run_trigger, args=(entry,), daemon=True).start()
        time.sleep(5)


def start() -> None:
    global _running
    if not _running:
        _running = True
        threading.Thread(target=_loop, daemon=True).start()


def stop() -> None:
    global _running
    _running = False


def list_triggers() -> list[dict]:
    return list(_TRIGGERS)


def get_results(limit: int = 50) -> list[dict]:
    if not _RESULTS.exists():
        return []
    return [json.loads(l) for l in _RESULTS.read_text().strip().splitlines()[-limit:]]
