from __future__ import annotations
from tools.registry import tool_registry
from lanes.tool_calling.validator import validate_tool_call
from lanes.tool_calling.executor import dispatch_tool

def _select_tool_call(query: str) -> dict:
    q = query.lower()
    if 'browser' in q or 'page' in q:
        return {'tool': 'browser_controller', 'args': {'action': 'inspect_page', 'target': 'active_page', 'goal': query}, 'approved': True}
    if 'search' in q or 'find' in q:
        return {'tool': 'qdrant_search', 'args': {'query': query, 'top_k': 5, 'collection': 'main'}, 'approved': True}
    if 'graph' in q or 'relation' in q:
        return {'tool': 'neo4j_query', 'args': {'cypher': 'MATCH (n) RETURN n LIMIT 5', 'params': {}}, 'approved': True}
    if 'verify' in q or 'constraint' in q:
        return {'tool': 'z3_verify', 'args': {'constraints': ['x > 0', 'x < 100'], 'variables': {'x': 'int'}}, 'approved': True}
    return {'tool': 'code_executor', 'args': {'code': 'def solve(x): return x', 'tests': ['assert solve(1) == 1']}, 'approved': True}

def run(state: dict) -> dict:
    registry = tool_registry()
    tool_call = _select_tool_call(state['query'])
    validation = validate_tool_call(tool_call)
    exec_result = dispatch_tool(tool_call) if validation['valid'] else {'error': validation['reason']}
    state['tool_calls'] = [tool_call]
    state['verification_results'].append({'stage': 'schema_validation', 'passed': validation['valid'], 'reason': validation['reason']})
    state['working_memory']['available_tools'] = [t['name'] for t in registry]
    state['working_memory']['exec_result'] = exec_result
    state['final_output'] = 'Tool: ' + tool_call['tool'] + ' -> ' + str(exec_result)
    state['output_mode'] = 'action'
    state['confidence'] = 0.92 if validation['valid'] else 0.5
    state['history'].append({'lane': 'tool_calling', 'tool': tool_call['tool'], 'valid': validation['valid']})
    return state
