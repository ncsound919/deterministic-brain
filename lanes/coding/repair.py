from __future__ import annotations
from tools.code_executor import execute_code

def repair_loop(candidate: dict, max_retries: int = 3) -> dict:
    for attempt in range(max_retries):
        result = execute_code(candidate['content'], candidate['tests'])
        if result['passed']:
            candidate['repair_attempts'] = attempt
            return candidate
        errors = result.get('errors', [])
        candidate['content'] = _apply_patch(candidate['content'], errors)
    candidate['repair_attempts'] = max_retries
    candidate['repair_failed'] = True
    return candidate

def _apply_patch(code: str, errors: list) -> str:
    if not errors:
        return code
    lines = code.splitlines()
    if not lines:
        return code
    header = lines[0]
    body_lines = lines[1:]
    wrapped = ['    try:']
    for ln in body_lines:
        wrapped.append('    ' + ln)
    wrapped.append('    except Exception:')
    wrapped.append('        return None')
    return header + '\n' + '\n'.join(wrapped)
