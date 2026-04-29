from __future__ import annotations
from planners.code_planner import plan_code_task
from tools.code_executor import execute_code
from tools.llm.router import generate_code
from lanes.coding.analysis import static_check, generate_contract

_MAX_REPAIR = 3

def _llm_generate_and_repair(query: str, contexts: list) -> dict:
    snippets = [c.get('text', '') for c in contexts[:5]]
    code = generate_code(query, context_snippets=snippets)
    tests = _infer_tests(query, code)
    candidate = {'id': 'code1', 'kind': 'code', 'content': code, 'tests': tests, 'repair_attempts': 0}

    for attempt in range(_MAX_REPAIR):
        result = execute_code(candidate['content'], candidate['tests'])
        if result['passed']:
            candidate['repair_attempts'] = attempt
            return candidate
        errors = result.get('errors', [])
        candidate['content'] = generate_code(
            candidate['content'],
            repair_errors=errors,
            repair_tests=candidate['tests'],
            repair_attempt=attempt,
        )

    candidate['repair_attempts'] = _MAX_REPAIR
    candidate['repair_failed'] = True
    return candidate

def _infer_tests(query: str, code: str) -> list[str]:
    """Derive simple smoke tests from the generated code."""
    q = query.lower()
    if 'sort' in q:
        return ["assert solve([3,1,2]) == [1,2,3]", "assert solve([]) == []"]
    if 'search' in q or 'find' in q:
        return ["assert solve([1,2,3], 2) == 1", "assert solve([], 0) == -1"]
    if 'router' in q:
        return ["assert solve('write code') == 'coding'",
                "assert solve('policy') == 'business_logic'"]
    # Generic: function must at least be callable
    fn_lines = [l for l in code.splitlines() if l.startswith('def ')]
    if fn_lines:
        fn_name = fn_lines[0].split('(')[0].replace('def ', '').strip()
        return [f"assert callable({fn_name})"]
    return ["assert True"]

def run(state: dict) -> dict:
    plan = plan_code_task(state['query'])
    contexts = state.get('retrieved_contexts', [])
    candidate = _llm_generate_and_repair(state['query'], contexts)
    exec_result = execute_code(candidate['content'], candidate['tests'])
    static = static_check(candidate['content'])
    contracts = generate_contract(candidate['content'])
    state['candidate_artifacts'] = [candidate]
    state['verification_results'].append({'stage': 'code_exec', 'passed': exec_result['passed'],
        'reason': exec_result['reason'], 'details': {'errors': exec_result.get('errors', [])}})
    state['verification_results'].append({'stage': 'static_analysis', 'passed': static['passed'],
        'reason': 'static_check', 'details': {'issues': static['issues']}})
    state['working_memory']['code_plan'] = plan
    state['working_memory']['code_tests'] = candidate['tests']
    state['working_memory']['contracts'] = contracts
    state['working_memory']['repair_attempts'] = candidate.get('repair_attempts', 0)
    state['final_output'] = candidate['content']
    state['output_mode'] = 'code'
    state['confidence'] = 0.96 if (exec_result['passed'] and static['passed']) else (0.72 if exec_result['passed'] else 0.45)
    state['history'].append({'lane': 'coding', 'plan': plan, 'candidate': candidate['id'],
                             'repair_attempts': candidate.get('repair_attempts', 0),
                             'llm_backend': 'opencode_via_openrouter'})
    return state
