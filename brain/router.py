from __future__ import annotations

from schemas.state import LaneName

def route_lane(query: str) -> LaneName:
    q = query.lower()
    if any(x in q for x in ['python', 'code', 'refactor', 'debug', 'function', 'write code', 'implement']):
        return 'coding'
    if any(x in q for x in ['policy', 'approval', 'workflow', 'compliance', 'business rule', 'budget request']):
        return 'business_logic'
    if any(x in q for x in ['browser agent', 'navigate to', 'click', 'inspect page', 'autonomous', 'dashboard']):
        return 'agent_brain'
    if any(x in q for x in ['call a tool', 'invoke', 'api call', 'validate data', 'run tool', 'qdrant', 'neo4j']):
        return 'tool_calling'
    return 'cross_domain'
