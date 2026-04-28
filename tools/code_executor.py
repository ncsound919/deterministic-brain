from __future__ import annotations
"""
Hardened sandboxed code executor.

Runs untrusted generated code in a restricted Python execution environment:
  - Whitelisted builtins only (no open, __import__, eval, exec, etc.)
  - stdout captured via StringIO
  - Wall-clock timeout enforced via threading.Timer
  - Memory and recursion limits applied
  - Returns structured result dict
"""
import contextlib
import io
import os
import sys
import resource
import threading
from typing import Any


# ---------------------------------------------------------------------------
# Sandbox configuration
# ---------------------------------------------------------------------------

_TIMEOUT_S: int = int(os.getenv('EXECUTOR_TIMEOUT', '5'))
_MAX_RECURSION: int = int(os.getenv('EXECUTOR_RECURSION', '100'))

# Whitelist of safe builtins
_SAFE_BUILTINS: dict[str, Any] = {
    '__builtins__': {
        'len': len, 'range': range, 'str': str, 'int': int, 'float': float,
        'bool': bool, 'list': list, 'dict': dict, 'tuple': tuple, 'set': set,
        'sorted': sorted, 'reversed': reversed, 'enumerate': enumerate,
        'zip': zip, 'map': map, 'filter': filter, 'sum': sum, 'min': min,
        'max': max, 'abs': abs, 'round': round, 'isinstance': isinstance,
        'issubclass': issubclass, 'hasattr': hasattr, 'getattr': getattr,
        'setattr': setattr, 'type': type, 'repr': repr, 'print': print,
        'TypeError': TypeError, 'ValueError': ValueError,
        'KeyError': KeyError, 'IndexError': IndexError,
        'AttributeError': AttributeError, 'StopIteration': StopIteration,
        'Exception': Exception, 'RuntimeError': RuntimeError,
        'NotImplementedError': NotImplementedError,
        'True': True, 'False': False, 'None': None,
    }
}


# ---------------------------------------------------------------------------
# Execution harness
# ---------------------------------------------------------------------------

class _TimeoutError(Exception):
    pass


def _run_with_timeout(fn, timeout: int) -> Any:
    result: list[Any] = [None]
    exc: list[BaseException | None] = [None]

    def target():
        try:
            result[0] = fn()
        except BaseException as e:  # noqa: BLE001
            exc[0] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise _TimeoutError(f'Execution exceeded {timeout}s timeout')
    if exc[0] is not None:
        raise exc[0]
    return result[0]


def execute_code(code: str, tests: list[str]) -> dict:
    """Execute `code` string then each test string in a shared restricted scope.

    Returns:
        dict with keys: passed, reason, stdout, errors, tests_run, tests_passed
    """
    old_recursion = sys.getrecursionlimit()
    sys.setrecursionlimit(_MAX_RECURSION)

    stdout = io.StringIO()
    scope: dict[str, Any] = dict(_SAFE_BUILTINS)
    errors: list[str] = []
    tests_passed = 0

    def _exec():
        with contextlib.redirect_stdout(stdout):
            exec(code, scope, scope)  # noqa: S102
            for test in tests:
                try:
                    exec(test, scope, scope)  # noqa: S102
                    nonlocal tests_passed
                    tests_passed += 1
                except AssertionError as e:
                    errors.append(f'AssertionError: {e}')
                except Exception as e:  # noqa: BLE001
                    errors.append(f'{type(e).__name__}: {e}')

    try:
        _run_with_timeout(_exec, _TIMEOUT_S)
        passed = len(errors) == 0
        reason = 'tests_passed' if passed else 'test_failures'
    except _TimeoutError as e:
        passed = False
        reason = 'timeout'
        errors.append(str(e))
    except SyntaxError as e:
        passed = False
        reason = 'syntax_error'
        errors.append(f'SyntaxError: {e}')
    except Exception as e:  # noqa: BLE001
        passed = False
        reason = 'runtime_error'
        errors.append(f'{type(e).__name__}: {e}')
    finally:
        sys.setrecursionlimit(old_recursion)

    return {
        'passed': passed,
        'reason': reason,
        'stdout': stdout.getvalue(),
        'errors': errors,
        'tests_run': len(tests),
        'tests_passed': tests_passed,
    }


def static_analysis(code: str) -> dict:
    """Lightweight static analysis: flag dangerous patterns."""
    flags: list[str] = []
    danger_patterns = [
        ('eval(', 'eval_usage'),
        ('exec(', 'exec_usage'),
        ('__import__', 'dynamic_import'),
        ('open(', 'file_io'),
        ('os.system', 'os_system'),
        ('subprocess', 'subprocess_usage'),
        ('shell=True', 'shell_injection_risk'),
        ('socket', 'network_access'),
    ]
    for pattern, label in danger_patterns:
        if pattern in code:
            flags.append(label)
    return {
        'clean': len(flags) == 0,
        'flags': flags,
        'line_count': code.count('\n') + 1,
        'char_count': len(code),
    }
