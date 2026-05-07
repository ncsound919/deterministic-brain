from __future__ import annotations
"""
KAIROS — Deterministic daily-log mode (no LLM).

Provides a persistent daily journal that logs conversation turns,
tracks tasks/decisions based on deterministic pattern matching,
and builds a structured daily digest.
The digest is stored in .kairos/<YYYY-MM-DD>.json and can be queried
via the API at GET /kairos/today and GET /kairos/{date}.
"""
import json
import os
import re
from datetime import date, datetime
from pathlib import Path

_DIR = Path(os.getenv('KAIROS_DIR', '.kairos'))
_DIR.mkdir(exist_ok=True)


def _today_path() -> Path:
    return _DIR / f'{date.today().isoformat()}.json'


def _load_today() -> dict:
    p = _today_path()
    if p.exists():
        return json.loads(p.read_text())
    return {'date': date.today().isoformat(), 'entries': [], 'tasks': [], 'decisions': [], 'questions': [], 'stats': {}}


def _save(data: dict) -> None:
    _today_path().write_text(json.dumps(data, indent=2))


def _extract_tasks_deterministic(query: str, response: str) -> list:
    tasks = []
    text = (query + " " + response).lower()

    task_patterns = [
        (r'\b(create|add|implement|build)\s+(\w+\s+){0,3}(component|function|module|api)', 'new'),
        (r'\b(fix|repair|debug|resolve)\s+(\w+\s+){0,3}(bug|issue|error|problem)', 'blocked'),
        (r'\b(done|completed|finished)\s+(\w+\s+){0,3}(task|feature|work)', 'done'),
    ]

    for pattern, status in task_patterns:
        if re.search(pattern, text):
            tasks.append({'task': query[:100], 'status': status, 'source': 'query'})

    return tasks


def _extract_decisions_deterministic(query: str, response: str) -> list:
    decisions = []
    text = response.lower()

    decision_indicators = ['decided', 'chose', 'selected', 'will use', 'going with', 'determined']
    for indicator in decision_indicators:
        if indicator in text:
            idx = text.find(indicator)
            snippet = response[max(0, idx-20):idx+50].strip()
            decisions.append({'decision': snippet, 'source': 'response'})

    return decisions


def _extract_questions_deterministic(query: str) -> list:
    questions = []
    if '?' in query:
        questions.append({'question': query.strip(), 'source': 'query'})
    return questions


def log_turn(query: str, response: str, session_id: str = '') -> dict:
    """Extract structured data from a turn (deterministic, no LLM)."""
    entry = {
        'ts': datetime.utcnow().isoformat(),
        'session_id': session_id,
        'query_preview': query[:100],
        'response_preview': response[:200],
        'tasks': _extract_tasks_deterministic(query, response),
        'decisions': _extract_decisions_deterministic(query, response),
        'questions': _extract_questions_deterministic(query),
    }

    log = _load_today()
    log['entries'].append(entry)
    log['tasks'].extend(entry['tasks'])
    log['decisions'].extend(entry['decisions'])
    log['questions'].extend(entry['questions'])

    stats = log.get('stats', {})
    stats['total_turns'] = stats.get('total_turns', 0) + 1
    stats['queries_with_question'] = stats.get('queries_with_question', 0) + (1 if '?' in query else 0)
    log['stats'] = stats

    _save(log)
    return entry


def get_today() -> dict:
    return _load_today()


def get_date(d: str) -> dict:
    p = _DIR / f'{d}.json'
    return json.loads(p.read_text()) if p.exists() else {}


def list_dates() -> list[str]:
    return sorted(p.stem for p in _DIR.glob('*.json'))


def get_stats() -> dict:
    """Get aggregate stats across all kairos logs."""
    dates = list_dates()
    all_stats = {
        'total_days': len(dates),
        'total_turns': 0,
        'total_tasks': 0,
        'total_decisions': 0,
    }

    for d in dates:
        data = get_date(d)
        stats = data.get('stats', {})
        all_stats['total_turns'] += stats.get('total_turns', 0)
        all_stats['total_tasks'] += len(data.get('tasks', []))
        all_stats['total_decisions'] += len(data.get('decisions', []))

    return all_stats
