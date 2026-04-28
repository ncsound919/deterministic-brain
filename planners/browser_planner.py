from __future__ import annotations

def plan_browser_task(query: str) -> dict:
    return {'kind': 'browser', 'goal': query,
            'actions': ['inspect_page', 'extract_targets', 'propose_action']}
