from __future__ import annotations

def allow_browser_action(action: str) -> bool:
    return action in {'inspect_page', 'extract_targets', 'navigate', 'click', 'type'}
