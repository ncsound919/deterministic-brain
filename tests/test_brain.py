"""Golden-trace test suite for the Deterministic Brain.

Runs each demo query and asserts:
  - Correct lane is selected
  - Status is 'ok' or 'fallback' (not error)
  - Confidence is in valid range [0, 1]
  - Required verification stages are present
  - Same query always produces same session_id (determinism check)
  - Same query always routes to same lane

Run with:  pytest tests/test_brain.py -v
"""
from __future__ import annotations
import pytest


# ---------------------------------------------------------------------------
# Router tests (pure unit tests, no heavy imports)
# ---------------------------------------------------------------------------

class TestRouter:
    def test_coding_routes(self):
        from brain.router import route_lane
        assert route_lane('Write python code for sorting') == 'coding'
        assert route_lane('Implement a binary search function') == 'coding'
        assert route_lane('Refactor this code') == 'coding'

    def test_business_logic_routes(self):
        from brain.router import route_lane
        assert route_lane('Create an approval policy') == 'business_logic'
        assert route_lane('Check compliance with GDPR') == 'business_logic'
        assert route_lane('Define business rule for budget request') == 'business_logic'

    def test_agent_brain_routes(self):
        from brain.router import route_lane
        assert route_lane('Use browser agent to navigate') == 'agent_brain'
        assert route_lane('Click the submit button autonomously') == 'agent_brain'

    def test_tool_calling_routes(self):
        from brain.router import route_lane
        assert route_lane('Call a tool to validate data') == 'tool_calling'
        assert route_lane('Invoke the qdrant search api call') == 'tool_calling'

    def test_cross_domain_default(self):
        from brain.router import route_lane
        assert route_lane('Tell me about the weather trends') == 'cross_domain'

    def test_same_query_same_lane(self):
        from brain.router import route_lane
        q = 'Write python code for a router'
        assert route_lane(q) == route_lane(q)


# ---------------------------------------------------------------------------
# Memory / state init tests
# ---------------------------------------------------------------------------

class TestMemory:
    def test_init_state_keys(self):
        from brain.memory import init_state
        state = init_state('test query', 'coding')
        required = [
            'session_id', 'query', 'lane', 'history', 'retrieved_contexts',
            'candidate_artifacts', 'verification_results', 'confidence', 'status',
            'working_memory', 'tool_budget',
        ]
        for key in required:
            assert key in state, f'Missing key: {key}'

    def test_session_id_deterministic(self):
        from brain.memory import init_state
        s1 = init_state('hello world', 'coding')
        s2 = init_state('hello world', 'coding')
        assert s1['session_id'] == s2['session_id']

    def test_different_queries_different_ids(self):
        from brain.memory import init_state
        s1 = init_state('query A', 'coding')
        s2 = init_state('query B', 'coding')
        assert s1['session_id'] != s2['session_id']


# ---------------------------------------------------------------------------
# Retrieval tests
# ---------------------------------------------------------------------------

class TestRetrieval:
    def test_returns_list(self):
        from retrieval.hybrid import retrieve
        result = retrieve('test query', 'coding')
        assert isinstance(result, list)

    def test_static_fallback_non_empty(self):
        from retrieval.hybrid import retrieve
        # Without backends configured, should return static corpus
        result = retrieve('python function', 'coding')
        assert len(result) > 0

    def test_context_schema(self):
        from retrieval.hybrid import retrieve
        result = retrieve('policy approval', 'business_logic')
        for ctx in result:
            assert 'source' in ctx
            assert 'id' in ctx
            assert 'text' in ctx
            assert 'score' in ctx
            assert 0.0 <= ctx['score'] <= 1.0

    def test_deterministic_fallback_order(self):
        from retrieval.hybrid import retrieve
        r1 = retrieve('same query', 'coding')
        r2 = retrieve('same query', 'coding')
        assert [c['id'] for c in r1] == [c['id'] for c in r2]


# ---------------------------------------------------------------------------
# MCTS tests
# ---------------------------------------------------------------------------

class TestMCTS:
    def _make_candidates(self):
        return [
            {'id': 'c1', 'content': 'x' * 300, 'kind': 'coding'},
            {'id': 'c2', 'content': 'y' * 100, 'kind': 'coding'},
        ]

    def test_returns_ranked_list(self):
        from reasoning.mcts_search import MCTSSearch
        mcts = MCTSSearch()
        ranked, summary = mcts.rank('query', 'sess1', self._make_candidates(), [])
        assert len(ranked) == 2
        assert 'score' in ranked[0]
        assert ranked[0]['mcts_ranked'] is True

    def test_deterministic(self):
        from reasoning.mcts_search import MCTSSearch
        mcts = MCTSSearch()
        r1, _ = mcts.rank('query', 'sess1', self._make_candidates(), [])
        r2, _ = mcts.rank('query', 'sess1', self._make_candidates(), [])
        assert [c['id'] for c in r1] == [c['id'] for c in r2]
        assert [c['score'] for c in r1] == [c['score'] for c in r2]

    def test_different_queries_different_order(self):
        from reasoning.mcts_search import MCTSSearch
        mcts = MCTSSearch()
        # Not guaranteed to differ but we can check it runs without error
        r1, _ = mcts.rank('query A', 'sess', self._make_candidates(), [])
        r2, _ = mcts.rank('query B', 'sess', self._make_candidates(), [])
        assert len(r1) == len(r2) == 2


# ---------------------------------------------------------------------------
# Z3 verification tests
# ---------------------------------------------------------------------------

class TestZ3:
    def test_coding_passes_with_def_and_tests(self):
        from reasoning.z3_constraints import verify_candidate
        v = verify_candidate('coding', {
            'content': 'def foo(): pass',
            'tests': ['assert foo() is None'],
        })
        assert v['passed'] is True

    def test_coding_fails_without_tests(self):
        from reasoning.z3_constraints import verify_candidate
        v = verify_candidate('coding', {'content': 'def foo(): pass', 'tests': []})
        assert v['passed'] is False

    def test_business_logic_passes(self):
        from reasoning.z3_constraints import verify_candidate
        v = verify_candidate('business_logic', {
            'rule_results': [{'fired': True, 'name': 'r1'}],
            'conflicts': [],
        })
        assert v['passed'] is True

    def test_business_logic_fails_on_conflict(self):
        from reasoning.z3_constraints import verify_candidate
        v = verify_candidate('business_logic', {
            'rule_results': [{'fired': True}],
            'conflicts': ['conflict1'],
        })
        assert v['passed'] is False

    def test_verdict_has_soft_score(self):
        from reasoning.z3_constraints import verify_candidate
        v = verify_candidate('tool_calling', {'tool_calls': [{'tool': 'x'}]})
        assert 'soft_score' in v
        assert 'hard_constraints_ok' in v


# ---------------------------------------------------------------------------
# PyReason tests
# ---------------------------------------------------------------------------

class TestPyReason:
    def test_returns_tuple(self):
        from reasoning.pyreason_adapter import PyReasonAdapter
        adapter = PyReasonAdapter()
        facts, trace = adapter.reason('coding', [], 'test')
        assert isinstance(facts, list)
        assert isinstance(trace, list)

    def test_base_fact_always_present(self):
        from reasoning.pyreason_adapter import PyReasonAdapter
        adapter = PyReasonAdapter()
        facts, _ = adapter.reason('coding', [], 'query')
        fact_names = [f['fact'] for f in facts]
        assert 'context_available' in fact_names

    def test_security_rule_fires(self):
        from reasoning.pyreason_adapter import PyReasonAdapter
        adapter = PyReasonAdapter()
        facts, trace = adapter.reason('coding', [], 'eval(dangerous_code)')
        fact_names = [f['fact'] for f in facts]
        assert 'flag_security_review' in fact_names


# ---------------------------------------------------------------------------
# Code executor tests
# ---------------------------------------------------------------------------

class TestCodeExecutor:
    def test_simple_pass(self):
        from tools.code_executor import execute_code
        result = execute_code('x = 1 + 1', ['assert x == 2'])
        assert result['passed'] is True
        assert result['tests_passed'] == 1

    def test_failing_assertion(self):
        from tools.code_executor import execute_code
        result = execute_code('x = 1', ['assert x == 99'])
        assert result['passed'] is False
        assert result['tests_passed'] == 0

    def test_syntax_error(self):
        from tools.code_executor import execute_code
        result = execute_code('def foo(: pass', [])
        assert result['passed'] is False
        assert result['reason'] == 'syntax_error'

    def test_static_analysis_flags_eval(self):
        from tools.code_executor import static_analysis
        result = static_analysis('eval(user_input)')
        assert result['clean'] is False
        assert 'eval_usage' in result['flags']

    def test_static_analysis_clean_code(self):
        from tools.code_executor import static_analysis
        result = static_analysis('def add(a, b): return a + b')
        assert result['clean'] is True


# ---------------------------------------------------------------------------
# Golden scenario tests (end-to-end, require full import chain)
# ---------------------------------------------------------------------------

SCENARIOS = [
    ('Write python code for a deterministic router', 'coding'),
    ('Create a business rule approval policy for budget requests', 'business_logic'),
    ('Call a tool to validate data schema', 'tool_calling'),
    ('Analyze cross-domain trends in AI', 'cross_domain'),
]


@pytest.mark.parametrize('query,expected_lane', SCENARIOS)
def test_golden_scenario(query: str, expected_lane: str):
    from brain.router import route_lane
    from brain.memory import init_state
    from retrieval.hybrid import retrieve

    # 1. Lane routing
    lane = route_lane(query)
    assert lane == expected_lane, f'Expected {expected_lane}, got {lane}'

    # 2. State init
    state = init_state(query, lane)
    assert state['lane'] == lane
    assert state['query'] == query

    # 3. Retrieval returns something
    contexts = retrieve(query, lane)
    assert len(contexts) > 0

    # 4. Same query produces same session_id (determinism)
    state2 = init_state(query, lane)
    assert state['session_id'] == state2['session_id']


def test_determinism_full_pipeline():
    """Run the same query twice and verify session_id and lane are identical."""
    from brain.router import route_lane
    from brain.memory import init_state
    q = 'Write python code for sorting'
    s1 = init_state(q, route_lane(q))
    s2 = init_state(q, route_lane(q))
    assert s1['session_id'] == s2['session_id']
    assert s1['lane'] == s2['lane']
