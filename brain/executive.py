from __future__ import annotations

from brain.memory import init_state
from brain.permissions import default_permissions
from brain.router import route_lane
from planners.karpathy_planner import build_plan
from retrieval.hybrid import retrieve
from reasoning.mcts_search import rank_candidates
from reasoning.z3_constraints import verify_candidate
from lanes.coding.lane import run as run_coding
from lanes.business_logic.lane import run as run_business_logic
from lanes.agent_brain.lane import run as run_agent_brain
from lanes.tool_calling.lane import run as run_tool_calling
from lanes.cross_domain.lane import run as run_cross_domain

LANE_RUNNERS = {
    'coding': run_coding,
    'business_logic': run_business_logic,
    'agent_brain': run_agent_brain,
    'tool_calling': run_tool_calling,
    'cross_domain': run_cross_domain,
}

class ExecutiveBrain:
    def run(self, query: str) -> dict:
        lane = route_lane(query)
        state = init_state(query, lane)
        state['permission_context'] = default_permissions()
        state['working_memory']['plan'] = build_plan(query, lane)
        state['retrieved_contexts'] = retrieve(query, lane)
        state['history'].append({'node': 'executive', 'action': 'route', 'lane': lane})
        state = LANE_RUNNERS[lane](state)
        if lane == 'tool_calling' and state.get('tool_calls'):
            state['candidate_artifacts'] = [{'id': 'tool1', 'kind': 'tool_calling', 'content': 'tool_call_prepared', 'tool_calls': state['tool_calls']}]
        if lane == 'agent_brain' and state.get('tool_calls'):
            call = state['tool_calls'][0]
            state['candidate_artifacts'] = [{'id': 'agent1', 'kind': 'agent_brain', 'content': state['final_output'], 'approved': call.get('approved', False)}]
        candidates = state.get('candidate_artifacts', [])
        if candidates:
            ranked = rank_candidates(query, candidates)
            state['candidate_artifacts'] = ranked
            verdict = verify_candidate(lane, ranked[0])
            state['verification_results'].append(verdict)
            if not verdict['passed']:
                state['status'] = 'retry'
                state['final_output'] = 'Verification failed; refinement required.'
                state['confidence'] = min(state.get('confidence', 0.0), 0.49)
            else:
                state['status'] = 'ok'
        else:
            state['status'] = 'ok'
        return state
