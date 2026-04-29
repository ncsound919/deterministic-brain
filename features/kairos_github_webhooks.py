from __future__ import annotations
"""
KAIROS_GITHUB_WEBHOOKS — GitHub webhook integration.

Listens for GitHub webhook events (push, PR, issue) and automatically
runs the brain on them:

- push event     -> coding lane: analyse changed files
- PR opened/sync -> coding lane: review the diff
- issue opened   -> cross_domain lane: triage and suggest resolution
- PR review      -> business_logic lane: check against contribution policies

Mount at POST /webhooks/github in the main FastAPI app.
Requires GITHUB_WEBHOOK_SECRET to verify signatures.
"""
import hashlib
import hmac
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from tools.tracing import log_event

_SECRET  = os.getenv('GITHUB_WEBHOOK_SECRET', '')
_RESULTS = Path('.webhook_results.jsonl')


def verify_signature(payload_bytes: bytes, signature: str) -> bool:
    if not _SECRET:
        return True  # Skip verification if no secret configured
    expected = 'sha256=' + hmac.new(
        _SECRET.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _handle_event(event_type: str, payload: dict) -> None:
    from orchestration.langgraph_app import build_app
    brain = build_app()

    query = ''
    lane_override = None

    if event_type == 'push':
        commits = payload.get('commits', [])
        messages = ' | '.join(c.get('message', '') for c in commits[:3])
        repo = payload.get('repository', {}).get('full_name', '')
        query = f'Analyse this git push to {repo}: {messages}'
        lane_override = 'coding'

    elif event_type == 'pull_request':
        action = payload.get('action', '')
        pr = payload.get('pull_request', {})
        query = f'Review this PR ({action}): {pr.get("title", "")} - {pr.get("body", "")[:300]}'
        lane_override = 'coding'

    elif event_type == 'issues':
        issue = payload.get('issue', {})
        query = f'Triage this GitHub issue: {issue.get("title", "")} - {issue.get("body", "")[:300]}'
        lane_override = 'cross_domain'

    elif event_type == 'issue_comment':
        comment = payload.get('comment', {})
        issue   = payload.get('issue', {})
        query = f'Analyse this comment on issue "{issue.get("title", "")}": {comment.get("body", "")[:300]}'

    if not query:
        return

    try:
        result = brain.run(query, lane_override=lane_override)
        record = {
            'event': event_type,
            'ts': datetime.utcnow().isoformat(),
            'query': query[:200],
            'lane': result.get('lane', ''),
            'output': result.get('final_output', '')[:500],
            'confidence': result.get('confidence', 0),
        }
        with open(_RESULTS, 'a') as f:
            f.write(json.dumps(record) + '\n')
        log_event('webhook_handled', {'event': event_type, 'lane': record['lane']})

        # Channel notification if enabled
        from features import is_enabled
        if is_enabled('KAIROS_CHANNELS'):
            from features.kairos_channels import broadcast
            broadcast(result)

    except Exception as exc:
        log_event('webhook_error', {'event': event_type, 'error': str(exc)})


def handle_webhook(event_type: str, payload: dict) -> dict:
    """Handle a GitHub webhook event asynchronously."""
    threading.Thread(
        target=_handle_event,
        args=(event_type, payload),
        daemon=True,
    ).start()
    return {'status': 'accepted', 'event': event_type, 'ts': datetime.utcnow().isoformat()}


def get_results(limit: int = 50) -> list[dict]:
    if not _RESULTS.exists():
        return []
    return [json.loads(l) for l in _RESULTS.read_text().strip().splitlines()[-limit:]]
