from __future__ import annotations
"""
Hardened sandboxed code executor.

Runs untrusted generated code in a restricted Python execution environment:
  - Whitelisted builtins only (no open, __import__, eval, exec, etc.)
  - stdout captured via StringIO
  - Wall-clock timeout enforced via daemon thread join
  - Recursion limit capped during execution
  - AST-based static analysis rejects dunder traversal (sandbox escapes),
    import statements, dynamic getattr, and gadget strings before execution
  - Returns structured result dict

NOTE: this is an in-process restricted environment, not an OS sandbox.
For hostile inputs run behind a container/job isolation boundary.
"""
import ast
import contextlib
import io
import os
import re
import sys
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
        'issubclass': issubclass, 'hasattr': hasattr, 'type': type, 'repr': repr, 'print': print,
        'TypeError': TypeError, 'ValueError': ValueError,
        'KeyError': KeyError, 'IndexError': IndexError,
        'AttributeError': AttributeError, 'StopIteration': StopIteration,
        'Exception': Exception, 'RuntimeError': RuntimeError,
        'NotImplementedError': NotImplementedError,
        'True': True, 'False': False, 'None': None,
    }
}


def _safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    """Restricted getattr to prevent reaching dangerous internals."""
    if name.startswith("_"):
        raise AttributeError(f"Access to private attribute '{name}' is blocked")
    return getattr(obj, name, default)

_SAFE_BUILTINS['__builtins__']['getattr'] = _safe_getattr


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

    # 1. Static Analysis
    analysis = static_analysis(code)
    if not analysis['clean']:
        return {
            'passed': False,
            'reason': 'security_blocked',
            'stdout': '',
            'errors': [f"Dangerous pattern detected: {', '.join(analysis['flags'])}"],
            'tests_run': len(tests),
            'tests_passed': 0,
        }

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
    """Static analysis: flag dangerous patterns before execution.

    Combines fast substring matching with an AST walk that rejects the known
    sandbox-escape primitives: dunder attribute traversal (``__class__``,
    ``__bases__``, ``__subclasses__``, ``__globals__``...), import statements,
    ``getattr`` with dynamic/private names, frame/builtin introspection
    (``globals``/``locals``/``vars``), and gadget substrings inside string
    literals (defeats ``"...".format(...)``-style obfuscation).
    """
    flags: list[str] = []
    danger_patterns = [
        ('eval(', 'eval_usage'),
        ('exec(', 'exec_usage'),
        ('__import__', 'dynamic_import'),
        ('open(', 'file_io'),
        ('os.system', 'os_system'),
        ('os.popen', 'os_popen'),
        ('subprocess', 'subprocess_usage'),
        ('shell=True', 'shell_injection_risk'),
        ('socket', 'network_access'),
        ('importlib', 'dynamic_import'),
        ('breakpoint(', 'debugger_hook'),
    ]
    for pattern, label in danger_patterns:
        if pattern in code:
            flags.append(label)

    dunder_re = re.compile(r'^__.*__$')
    gadget_re = re.compile(
        r'__(class|bases|subclasses|mro|dict|globals|builtins|import|code|'
        r'closure|init|reduce|base)__'
    )
    forbidden_names = {
        'globals': 'frame_introspection',
        'locals': 'frame_introspection',
        'vars': 'frame_introspection',
        '__builtins__': 'builtins_access',
    }

    def _flag(label: str, node: ast.AST | None = None) -> None:
        line = getattr(node, 'lineno', '?')
        flags.append(f'{label}@line{line}' if node is not None else label)

    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Let the runtime path surface the syntax error verbatim.
        return {
            'clean': len(flags) == 0,
            'flags': list(dict.fromkeys(flags)),
            'line_count': code.count('\n') + 1,
            'char_count': len(code),
        }

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            _flag('import_statement', node)
        elif isinstance(node, ast.Attribute):
            if dunder_re.match(node.attr) or node.attr == 'mro':
                _flag(f'dunder_attr:{node.attr}', node)
        elif isinstance(node, ast.Name) and node.id in forbidden_names:
            _flag(forbidden_names[node.id], node)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == 'getattr':
                if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
                    _flag('dynamic_getattr', node)
                elif isinstance(node.args[1].value, str) and (
                    node.args[1].value.startswith('_') or dunder_re.match(node.args[1].value)
                ):
                    _flag('private_getattr', node)
            elif isinstance(func, ast.Attribute) and func.attr == 'format':
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str) \
                            and gadget_re.search(arg.value):
                        _flag('gadget_string', node)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if gadget_re.search(node.value):
                _flag('gadget_string', node)

    return {
        'clean': len(flags) == 0,
        'flags': list(dict.fromkeys(flags)),
        'line_count': code.count('\n') + 1,
        'char_count': len(code),
    }
