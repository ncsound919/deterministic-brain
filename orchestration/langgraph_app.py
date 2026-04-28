from __future__ import annotations
import time
from typing import Any

from langgraph.graph import StateGraph, END

from brain.memory import init_state
from brain.permissions import default_permissions
from brain.router import route_lane
from planners.karpathy_planner import build_plan
from retrieval.hybrid import retrieve
from reasoning.mcts_search import MCTSSearch
from reasoning.z3_constraints import verify_candidate
from reasoning.pyreason_adapter import PyReasonAdapter
from tools.tracing import checkpoint_state, get_trace
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

_mcts = MCTSSearch()
_pyreason = PyReasonAdapter()


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------

def node_input_parser(state: dict) -> dict:
    """Parse query, set intent signals and confidence baseline."""
    q = state['query'].lower()
    intent_signals: list[str] = []
    for kw in ['python', 'code', 'function', 'implement', 'refactor']:
        if kw in q:
            intent_signals.append('coding')
            break
    for kw in ['policy', 'approval', 'compliance', 'workflow', 'business rule']:
        if kw in q:
            intent_signals.append('business_logic')
            break
    for kw in ['browser', 'navigate', 'click', 'inspect page', 'autonomous']:
        if kw in q:
            intent_signals.append('agent_brain')
            break
    for kw in ['call a tool', 'invoke', 'api call', 'validate data', 'qdrant', 'neo4j']:
        if kw in q:
            intent_signals.append('tool_calling')
            break
    if not intent_signals:
        intent_signals.append('cross_domain')
    state['working_memory']['intent_signals'] = intent_signals
    state['history'].append({'node': 'input_parser', 'intent_signals': intent_signals})
    checkpoint_state('input_parser', state)
    return state


def node_retriever(state: dict) -> dict:
    """Hybrid retrieval: Qdrant + Neo4j + optional Tavily."""
    t0 = time.perf_counter()
    contexts = retrieve(state['query'], state['lane'])
    state['retrieved_contexts'] = contexts
    elapsed = round(time.perf_counter() - t0, 4)
    state['history'].append({
        'node': 'retriever',
        'count': len(contexts),
        'sources': list({c['source'] for c in contexts}),
        'elapsed_s': elapsed,
    })
    checkpoint_state('retriever', state)
    return state


def node_lane_selector(state: dict) -> dict:
    """Route to lane and build a Karpathy-style task plan."""
    lane = route_lane(state['query'])
    state['lane'] = lane
    state['permission_context'] = default_permissions()
    state['working_memory']['plan'] = build_plan(state['query'], lane)
    state['history'].append({'node': 'lane_selector', 'lane': lane})
    checkpoint_state('lane_selector', state)
    return state


def node_pyreason(state: dict) -> dict:
    """Run neuro-symbolic graph reasoning over retrieved contexts."""
    derived, trace = _pyreason.reason(
        state['lane'],
        state['retrieved_contexts'],
        state['query'],
    )
    state['working_memory']['derived_facts'] = derived
    state['working_memory']['logic_trace'] = trace
    state['history'].append({'node': 'pyreason', 'derived_count': len(derived)})
    checkpoint_state('pyreason', state)
    return state


def node_lane_runner(state: dict) -> dict:
    """Execute the selected lane."""
    lane = state['lane']
    state = LANE_RUNNERS[lane](state)

    # Normalise artifacts for lanes that don't build candidate_artifacts themselves
    if lane == 'tool_calling' and state.get('tool_calls') and not state.get('candidate_artifacts'):
        state['candidate_artifacts'] = [{
            'id': 'tool1', 'kind': 'tool_calling',
            'content': 'tool_call_prepared',
            'tool_calls': state['tool_calls'],
        }]
    if lane == 'agent_brain' and state.get('tool_calls') and not state.get('candidate_artifacts'):
        call = state['tool_calls'][0]
        state['candidate_artifacts'] = [{
            'id': 'agent1', 'kind': 'agent_brain',
            'content': state.get('final_output', ''),
            'approved': call.get('approved', False),
        }]
    state['history'].append({'node': 'lane_runner', 'lane': lane,
                             'artifacts': len(state.get('candidate_artifacts', []))})
    checkpoint_state('lane_runner', state)
    return state


def node_mcts_ranker(state: dict) -> dict:
    """MCTS-based candidate ranking with deterministic seeded search."""
    candidates = state.get('candidate_artifacts', [])
    if not candidates:
        return state
    ranked, tree_summary = _mcts.rank(
        state['query'],
        state['session_id'],
        candidates,
        state.get('retrieved_contexts', []),
    )
    state['candidate_artifacts'] = ranked
    state['working_memory']['mcts_tree'] = tree_summary
    state['history'].append({'node': 'mcts_ranker', 'top_score': ranked[0].get('score') if ranked else None})
    checkpoint_state('mcts_ranker', state)
    return state


def node_verifier(state: dict) -> dict:
    """Z3 + heuristic verification of top candidate."""
    candidates = state.get('candidate_artifacts', [])
    if not candidates:
        state['status'] = 'ok'
        return state
    verdict = verify_candidate(state['lane'], candidates[0])
    state['verification_results'].append(verdict)
    if not verdict['passed']:
        state['status'] = 'retry'
        state['final_output'] = 'Verification failed; refinement required.'
        state['confidence'] = min(state.get('confidence', 0.0), 0.49)
    else:
        state['status'] = 'ok'
    state['history'].append({'node': 'verifier', 'passed': verdict['passed'], 'stage': verdict['stage']})
    checkpoint_state('verifier', state)
    return state


def node_composer(state: dict) -> dict:
    """Assemble final_output and set output_mode."""
    lane = state['lane']
    artifacts = state.get('candidate_artifacts', [])
    if artifacts and not state.get('final_output'):
        state['final_output'] = artifacts[0].get('content', '')
    mode_map = {
        'coding': 'code',
        'business_logic': 'plan',
        'agent_brain': 'action',
        'tool_calling': 'action',
        'cross_domain': 'answer',
    }
    state['output_mode'] = mode_map.get(lane, 'answer')
    state['history'].append({'node': 'composer', 'output_mode': state['output_mode']})
    checkpoint_state('composer', state)
    return state


def node_fallback_llm(state: dict) -> dict:
    """Low-confidence fallback: clarify or produce minimal safe answer."""
    state['final_output'] = (
        f'[Fallback] Query not confidently resolved. '
        f'Lane={state["lane"]}, confidence={state.get("confidence", 0):.2f}. '
        'Please refine your query or provide more context.'
    )
    state['status'] = 'fallback'
    state['output_mode'] = 'clarify'
    state['history'].append({'node': 'fallback_llm'})
    checkpoint_state('fallback_llm', state)
    return state


# ---------------------------------------------------------------------------
# Routing conditions
# ---------------------------------------------------------------------------

def route_after_verifier(state: dict) -> str:
    """After verification: retry lane or go to composer or fallback."""
    retry_count = state['working_memory'].get('retry_count', 0)
    budget = state.get('tool_budget', {}).get('max_retries', 2)
    if state['status'] == 'retry' and retry_count < budget:
        state['working_memory']['retry_count'] = retry_count + 1
        return 'lane_runner'
    conf = state.get('confidence', 1.0)
    if conf < 0.35:
        return 'fallback_llm'
    return 'composer'


def route_after_lane_runner(state: dict) -> str:
    """Skip ranker if no candidates were produced."""
    if state.get('candidate_artifacts'):
        return 'mcts_ranker'
    return 'composer'


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    g = StateGraph(dict)

    g.add_node('input_parser', node_input_parser)
    g.add_node('retriever', node_retriever)
    g.add_node('lane_selector', node_lane_selector)
    g.add_node('pyreason', node_pyreason)
    g.add_node('lane_runner', node_lane_runner)
    g.add_node('mcts_ranker', node_mcts_ranker)
    g.add_node('verifier', node_verifier)
    g.add_node('composer', node_composer)
    g.add_node('fallback_llm', node_fallback_llm)

    g.set_entry_point('input_parser')
    g.add_edge('input_parser', 'lane_selector')
    g.add_edge('lane_selector', 'retriever')
    g.add_edge('retriever', 'pyreason')
    g.add_edge('pyreason', 'lane_runner')
    g.add_conditional_edges('lane_runner', route_after_lane_runner,
                            {'mcts_ranker': 'mcts_ranker', 'composer': 'composer'})
    g.add_edge('mcts_ranker', 'verifier')
    g.add_conditional_edges('verifier', route_after_verifier,
                            {'lane_runner': 'lane_runner',
                             'fallback_llm': 'fallback_llm',
                             'composer': 'composer'})
    g.add_edge('fallback_llm', END)
    g.add_edge('composer', END)
    return g


class BrainApp:
    """Thin wrapper: compile graph once, expose .run(query) interface."""

    def __init__(self) -> None:
        self._graph = build_graph().compile()

    def run(self, query: str, lane_override: str | None = None) -> dict:
        from brain.memory import init_state
        from brain.router import route_lane
        lane = lane_override or route_lane(query)
        state = init_state(query, lane)
        return self._graph.invoke(state)

    def trace(self, session_id: str) -> dict:
        return get_trace(session_id)


def build_app() -> BrainApp:
    return BrainApp()
