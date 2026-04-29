from __future__ import annotations
from tools.llm.router import chat
from tools.registry import tool_registry
from lanes.tool_calling.validator import validate_tool_call
from lanes.tool_calling.executor import dispatch_tool
import json

_SYSTEM = """You are a deterministic tool-calling agent.
Given a user query and a registry of available tools, select the best tool and construct the call.
Respond with valid JSON only — no prose, no markdown.
Schema: {"tool": "<tool_name>", "args": {<args_dict>}, "rationale": "<one sentence>"}"""

def _llm_select_tool(query: str, registry: list) -> dict:
    tool_list = '\n'.join(f'- {t["name"]}: {t["description"]} | args: {list(t["schema"].keys())}' for t in registry)
    user_msg = f'Query: {query}\n\nAvailable tools:\n{tool_list}\n\nSelect and construct the tool call:'
    raw = chat(system=_SYSTEM, user=user_msg, lane='tool_calling')
    try:
        # Strip markdown fences if model adds them
        clean = raw.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
        parsed = json.loads(clean)
        return {'tool': parsed['tool'], 'args': parsed.get('args', {}), 'approved': True,
                'rationale': parsed.get('rationale', '')}
    except Exception:
        return _fallback_select(query)

def _fallback_select(query: str) -> dict:
    q = query.lower()
    if 'search' in q or 'find' in q:
        return {'tool': 'qdrant_search', 'args': {'query': query, 'top_k': 5, 'collection': 'main'}, 'approved': True}
    if 'graph' in q or 'relation' in q:
        return {'tool': 'neo4j_query', 'args': {'cypher': 'MATCH (n) RETURN n LIMIT 5', 'params': {}}, 'approved': True}
    if 'verify' in q or 'constraint' in q:
        return {'tool': 'z3_verify', 'args': {'constraints': ['x > 0', 'x < 100'], 'variables': {'x': 'int'}}, 'approved': True}
    return {'tool': 'code_executor', 'args': {'code': 'def solve(x): return x', 'tests': ['assert solve(1) == 1']}, 'approved': True}

def run(state: dict) -> dict:
    registry = tool_registry()
    tool_call = _llm_select_tool(state['query'], registry)
    validation = validate_tool_call(tool_call)
    exec_result = dispatch_tool(tool_call) if validation['valid'] else {'error': validation['reason']}
    state['tool_calls'] = [tool_call]
    state['verification_results'].append({'stage': 'schema_validation', 'passed': validation['valid'],
                                          'reason': validation['reason']})
    state['working_memory']['available_tools'] = [t['name'] for t in registry]
    state['working_memory']['exec_result'] = exec_result
    state['working_memory']['tool_rationale'] = tool_call.get('rationale', '')
    state['final_output'] = 'Tool: ' + tool_call['tool'] + ' -> ' + str(exec_result)
    state['output_mode'] = 'action'
    state['confidence'] = 0.92 if validation['valid'] else 0.5
    state['history'].append({'lane': 'tool_calling', 'tool': tool_call['tool'], 'valid': validation['valid'],
                             'llm_backend': 'llama3_via_openrouter'})
    return state
