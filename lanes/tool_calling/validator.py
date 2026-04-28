from __future__ import annotations
from tools.registry import get_tool

def validate_tool_call(tool_call: dict) -> dict:
    spec = get_tool(tool_call.get('tool', ''))
    if not spec:
        return {'valid': False, 'reason': f"Unknown tool: {tool_call.get('tool')}"}
    schema = spec.get('schema', {})
    args = tool_call.get('args', {})
    missing = [k for k in schema if k not in args]
    if missing:
        return {'valid': False, 'reason': f'Missing args: {missing}'}
    return {'valid': True, 'reason': 'schema_validated', 'tool': spec['name']}
