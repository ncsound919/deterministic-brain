from __future__ import annotations

from tools.browser.controller import execute_browser_action

def verify_action_outcome(tool_call: dict, expected_goal: str) -> dict:
    result = execute_browser_action(tool_call)
    keywords = expected_goal.lower().split()
    relevance = any(k in str(result) for k in keywords)
    return {'success': result['success'], 'relevant': relevance, 'result': result, 'goal': expected_goal}
