from __future__ import annotations
from schemas.tools import ToolSpec

_REGISTRY: list = [
    {'name': 'code_executor', 'description': 'Run code against tests; returns pass/fail and stdout.', 'category': 'code',
     'schema': {'code': 'str', 'tests': 'list[str]'}},
    {'name': 'browser_controller', 'description': 'Control browser: click, navigate, fill, extract.', 'category': 'browser',
     'schema': {'action': 'str', 'target': 'str', 'goal': 'str'}},
    {'name': 'qdrant_search', 'description': 'Vector similarity search over knowledge base.', 'category': 'data',
     'schema': {'query': 'str', 'top_k': 'int', 'collection': 'str'}},
    {'name': 'neo4j_query', 'description': 'Run Cypher query over knowledge graph.', 'category': 'data',
     'schema': {'cypher': 'str', 'params': 'dict'}},
    {'name': 'web_search', 'description': 'Real-time web augmentation via Tavily.', 'category': 'data',
     'schema': {'query': 'str', 'max_results': 'int'}},
    {'name': 'z3_verify', 'description': 'Run Z3 SMT constraint verification.', 'category': 'system',
     'schema': {'constraints': 'list[str]', 'variables': 'dict'}},
]

def tool_registry() -> list:
    return _REGISTRY

def get_tool(name: str):
    return next((t for t in _REGISTRY if t['name'] == name), None)
