from __future__ import annotations
"""
KAIROS — Assistant / daily-log mode.

Provides a persistent daily journal that auto-summarises each conversation
turn, tracks tasks/decisions, and builds a structured daily digest.
The digest is stored in .kairos/<YYYY-MM-DD>.json and can be queried
via the API at GET /kairos/today and GET /kairos/{date}.
"""
import json
import os
from datetime import date, datetime
from pathlib import Path
from tools.llm.router import chat

_DIR = Path(os.getenv('KAIROS_DIR', '.kairos'))
_DIR.mkdir(exist_ok=True)

_SYSTEM = (
    'You are a precise daily-log assistant. '
    'Given a conversation turn, extract: tasks (new/done/blocked), '
    'key decisions, open questions, and a 1-sentence summary. '
    'Return JSON: {"summary": str, "tasks": list, "decisions": list, "questions": list}'
)


def _today_path() -> Path:
    return _DIR / f'{date.today().isoformat()}.json'


def _load_today() -> dict:
    p = _today_path()
    if p.exists():
        return json.loads(p.read_text())
    return {'date': date.today().isoformat(), 'entries': [], 'tasks': [], 'decisions': [], 'questions': []}


def _save(data: dict) -> None:
    _today_path().write_text(json.dumps(data, indent=2))


def log_turn(query: str, response: str, session_id: str = '') -> dict:
    """Extract structured data from a turn and append to today's log."""
    raw = chat(
        system=_SYSTEM,
        user=f'User: {query}\nAssistant: {response[:1000]}',
        lane='cross_domain',
        max_tokens=512,
    )
    try:
        extracted = json.loads(raw)
    except Exception:
        extracted = {'summary': raw[:200], 'tasks': [], 'decisions': [], 'questions': []}

    entry = {
        'ts': datetime.utcnow().isoformat(),
        'session_id': session_id,
        'query_preview': query[:100],
        **extracted,
    }
    log = _load_today()
    log['entries'].append(entry)
    log['tasks'].extend(extracted.get('tasks', []))
    log['decisions'].extend(extracted.get('decisions', []))
    log['questions'].extend(extracted.get('questions', []))
    _save(log)
    return entry


def get_today() -> dict:
    return _load_today()


def get_date(d: str) -> dict:
    p = _DIR / f'{d}.json'
    return json.loads(p.read_text()) if p.exists() else {}


def list_dates() -> list[str]:
    return sorted(p.stem for p in _DIR.glob('*.json'))
