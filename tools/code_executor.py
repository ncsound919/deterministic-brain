from __future__ import annotations
import contextlib
import io

def execute_code(code: str, tests: list) -> dict:
    scope = {'__builtins__': {'len': len, 'range': range, 'str': str, 'int': int,
                               'dict': dict, 'list': list, 'sorted': sorted,
                               'isinstance': isinstance, 'TypeError': TypeError}}
    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            exec(code, scope, scope)
            for test in tests:
                exec(test, scope, scope)
        return {'passed': True, 'reason': 'tests_passed', 'stdout': stdout.getvalue(), 'errors': []}
    except Exception as e:
        return {'passed': False, 'reason': 'tests_failed', 'stdout': stdout.getvalue(), 'errors': [f'{type(e).__name__}: {e}']}
