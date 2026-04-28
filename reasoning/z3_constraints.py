from __future__ import annotations
from typing import Any, Dict

def verify_candidate(lane: str, candidate: Dict[str, Any]) -> Dict[str, Any]:
    if lane == 'coding':
        ok = 'def ' in candidate.get('content', '') and bool(candidate.get('tests'))
        return {'stage': 'z3_contract', 'passed': ok, 'reason': 'function_and_tests_required',
                'details': {'tests': len(candidate.get('tests', []))}}
    if lane == 'business_logic':
        rule_results = candidate.get('rule_results', [])
        fired = [r for r in rule_results if r.get('fired')]
        conflicts = candidate.get('conflicts', [])
        ok = len(fired) >= 1 and len(conflicts) == 0
        return {'stage': 'z3_logic', 'passed': ok, 'reason': 'at_least_one_rule_fired_no_conflicts',
                'details': {'fired': len(fired), 'conflicts': conflicts}}
    if lane == 'tool_calling':
        calls = candidate.get('tool_calls', [])
        ok = bool(calls) or 'tool_call_prepared' in candidate.get('content', '')
        return {'stage': 'z3_tools', 'passed': ok, 'reason': 'tool_call_required'}
    if lane == 'agent_brain':
        ok = candidate.get('approved', False)
        return {'stage': 'z3_agent', 'passed': ok, 'reason': 'approved_action_required'}
    ok = bool(candidate.get('signals')) or bool(candidate.get('content'))
    return {'stage': 'z3_cross_domain', 'passed': ok, 'reason': 'signals_or_content_required'}
