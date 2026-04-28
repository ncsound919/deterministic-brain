from __future__ import annotations
import ast
import re

def static_check(code: str) -> dict:
    issues = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {'passed': False, 'issues': [f'SyntaxError: {e}']}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if not ast.get_docstring(node):
                issues.append(f'Missing docstring: {node.name}')
            for arg in node.args.args:
                if arg.annotation is None:
                    issues.append(f'Missing type annotation on {node.name}.{arg.arg}')
    return {'passed': len(issues) == 0, 'issues': issues}

def generate_contract(code: str) -> list:
    contracts = []
    funcs = re.findall(r'def (\w+)\(', code)
    for f in funcs:
        contracts.append(f'assert callable({f})')
        contracts.append(f"assert {f}.__name__ == '{f}'")
    return contracts
