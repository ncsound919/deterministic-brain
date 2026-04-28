from __future__ import annotations

from hashlib import sha256
from schemas.state import BrainState

def init_state(query: str, lane: str) -> BrainState:
    sid = sha256(query.encode()).hexdigest()[:16]
    return {
        'session_id': sid, 'query': query, 'lane': lane,
        'goal_stack': [query], 'permission_context': {},
        'working_memory': {}, 'retrieved_contexts': [],
        'graph_refs': [], 'tool_budget': {'max_calls': 8, 'used_calls': 0},
        'browser_sessions': {}, 'candidate_artifacts': [],
        'tool_calls': [], 'verification_results': [],
        'history': [], 'confidence': 0.0,
        'output_mode': 'answer', 'final_output': '', 'status': 'ok',
    }
