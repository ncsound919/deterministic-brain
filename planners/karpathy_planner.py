from __future__ import annotations
from schemas.plans import TaskPlan

def build_plan(query: str, lane: str) -> TaskPlan:
    return {
        'planner': 'karpathy_interface', 'lane': lane, 'goal': query,
        'steps': [
            {'id': 's1', 'action': 'retrieve_context', 'inputs': {'query': query}, 'expected_output': 'relevant evidence'},
            {'id': 's2', 'action': 'produce_candidate', 'inputs': {'lane': lane}, 'expected_output': 'candidate artifact'},
            {'id': 's3', 'action': 'verify', 'inputs': {'lane': lane}, 'expected_output': 'verdict'},
        ],
    }
