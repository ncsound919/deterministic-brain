from __future__ import annotations
from tools.code_executor import execute_code
from tools.browser.controller import observe_browser_state

def dispatch_tool(tool_call: dict) -> dict:
    name = tool_call.get('tool')
    args = tool_call.get('args', {})
    if name == 'code_executor':
        return execute_code(args.get('code', ''), args.get('tests', []))
    if name == 'browser_controller':
        obs = observe_browser_state(args.get('goal', ''))
        return {'success': True, 'observation': obs}
    if name == 'qdrant_search':
        return {'results': [{'id': 'v1', 'score': 0.92, 'text': f"Vector result for: {args.get('query')}"}]}
    if name == 'neo4j_query':
        return {'nodes': [{'id': 'n1', 'label': 'Entity', 'props': args.get('params', {})}]}
    if name == 'web_search':
        return {'results': [{'title': 'Web result', 'snippet': f"Result for: {args.get('query')}"}]}
    if name == 'z3_verify':
        return {'verified': True, 'model': {}}
    return {'error': f'No dispatcher for {name}'}
