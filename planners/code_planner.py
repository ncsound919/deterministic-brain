from __future__ import annotations

def plan_code_task(query: str) -> dict:
    return {'kind': 'code', 'target_function': 'solve', 'query': query}
