from __future__ import annotations
from tools.browser.dom_snapshot import get_dom_snapshot
from tools.browser.policies import allow_browser_action

def observe_browser_state(goal: str) -> dict:
    snapshot = get_dom_snapshot()
    return {'goal': goal, 'snapshot': snapshot, 'current_url': snapshot['url']}

def propose_browser_action(goal: str, observation: dict | None = None) -> dict:
    observation = observation or observe_browser_state(goal)
    snapshot = observation.get('snapshot', {})
    elements = snapshot.get('elements', [])
    g = goal.lower()
    selected = None
    for el in elements:
        text = (el.get('text') or el.get('placeholder') or '').lower()
        if any(k in g for k in ['login', 'sign in']) and 'login' in text:
            selected = el; break
        if any(k in g for k in ['search', 'find']) and 'search' in el.get('type', ''):
            selected = el; break
        if any(k in g for k in ['report', 'analytic']) and ('reports' in text or 'analytic' in text):
            selected = el; break
    if not selected:
        selected = elements[0] if elements else {'type': 'page', 'id': 'page'}
    action = 'click' if selected.get('type') == 'button' else 'inspect_page'
    return {'tool': 'browser_controller',
            'args': {'action': action, 'target': selected.get('id', 'page'), 'goal': goal},
            'approved': False}

def execute_browser_action(tool_call: dict) -> dict:
    if not tool_call.get('approved'):
        return {'success': False, 'reason': 'not_approved'}
    args = tool_call.get('args', {})
    return {'success': True, 'action': args.get('action'), 'target': args.get('target'), 'result': 'stub_result'}
