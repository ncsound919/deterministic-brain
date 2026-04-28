from __future__ import annotations
from planners.code_planner import plan_code_task
from tools.code_executor import execute_code
from lanes.coding.repair import repair_loop
from lanes.coding.analysis import static_check, generate_contract

ROUTER_CODE = (
    "def solve(query: str) -> str:\n"
    "    \"\"\"Route query to the appropriate lane.\"\"\"\n"
    "    q = query.lower()\n"
    "    if 'code' in q:\n        return 'coding'\n"
    "    if 'policy' in q:\n        return 'business_logic'\n"
    "    if 'browser' in q:\n        return 'agent_brain'\n"
    "    if 'tool' in q:\n        return 'tool_calling'\n"
    "    return 'cross_domain'\n"
)
SORT_CODE = (
    "def solve(data: list) -> list:\n"
    "    \"\"\"Return sorted copy of a list.\"\"\"\n"
    "    return sorted(data)\n"
)
DEFAULT_CODE = (
    "def solve(data: dict) -> dict:\n"
    "    \"\"\"Validate and return input data.\"\"\"\n"
    "    if not isinstance(data, dict):\n"
    "        raise TypeError('Input must be a dict')\n"
    "    return {'status': 'ok', 'input': data}\n"
)

def _build_candidate(query: str) -> dict:
    q = query.lower()
    if 'router' in q:
        return {'id': 'code1', 'kind': 'code', 'content': ROUTER_CODE,
                'tests': ["assert solve('write code') == 'coding'",
                           "assert solve('policy review') == 'business_logic'",
                           "assert solve('trend analysis') == 'cross_domain'"]}
    if 'sort' in q:
        return {'id': 'code1', 'kind': 'code', 'content': SORT_CODE,
                'tests': ["assert solve([3,1,2]) == [1,2,3]", "assert solve([]) == []"]}
    return {'id': 'code1', 'kind': 'code', 'content': DEFAULT_CODE,
            'tests': ["assert solve({'a': 1})['status'] == 'ok'"]}

def run(state: dict) -> dict:
    plan = plan_code_task(state['query'])
    candidate = _build_candidate(state['query'])
    candidate = repair_loop(candidate)
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
                             'repair_attempts': candidate.get('repair_attempts', 0)})
    return state
