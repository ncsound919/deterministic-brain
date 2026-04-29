from __future__ import annotations
"""
MESSAGE_ACTIONS — Message action buttons.

Attaches structured action buttons to brain responses. When a response
is returned via the API, this module computes relevant follow-up actions
the user can take (e.g. 'Run tests', 'Apply diff', 'Explain more',
'Save to memory', 'Create GitHub issue').
"""
from typing import Any

_ACTION_TEMPLATES: dict[str, list[dict]] = {
    'code': [
        {'id': 'run_tests',    'label': '▶ Run tests',      'action': 'run_tests'},
        {'id': 'apply_diff',   'label': '✅ Apply changes',  'action': 'apply_diff'},
        {'id': 'explain_code', 'label': '💡 Explain',        'action': 'explain'},
        {'id': 'review',       'label': '🔍 Review',         'action': 'review_artifact'},
    ],
    'plan': [
        {'id': 'approve',      'label': '✅ Approve',        'action': 'approve_plan'},
        {'id': 'refine',       'label': '✏️ Refine plan',   'action': 'refine'},
        {'id': 'save_memory',  'label': '💾 Save to memory', 'action': 'save_memory'},
    ],
    'action': [
        {'id': 'execute',      'label': '▶ Execute',        'action': 'execute_action'},
        {'id': 'dry_run',      'label': '🧪 Dry run',       'action': 'dry_run'},
        {'id': 'abort',        'label': '🛑 Abort',         'action': 'abort'},
    ],
    'answer': [
        {'id': 'save_memory',  'label': '💾 Save to memory', 'action': 'save_memory'},
        {'id': 'follow_up',    'label': '💬 Follow up',     'action': 'follow_up'},
        {'id': 'share',        'label': '📤 Share',          'action': 'share'},
    ],
    'clarify': [
        {'id': 'retry',        'label': '🔄 Retry',         'action': 'retry'},
        {'id': 'rephrase',     'label': '✏️ Rephrase',      'action': 'rephrase'},
    ],
}


def get_actions(output_mode: str, lane: str, confidence: float) -> list[dict]:
    actions = list(_ACTION_TEMPLATES.get(output_mode, _ACTION_TEMPLATES['answer']))
    if confidence < 0.5:
        actions.append({'id': 'retry_high_conf', 'label': '⚡ Retry (higher confidence)', 'action': 'retry_aggressive'})
    if lane == 'coding':
        actions.append({'id': 'create_pr', 'label': '🔀 Create PR', 'action': 'create_github_pr'})
    return actions


def attach(result: dict) -> dict:
    """Attach action buttons to a brain result dict."""
    result['actions'] = get_actions(
        output_mode=result.get('output_mode', 'answer'),
        lane=result.get('lane', 'cross_domain'),
        confidence=result.get('confidence', 1.0),
    )
    return result
