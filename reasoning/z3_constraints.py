from __future__ import annotations
"""
Z3-backed constraint verification for each lane.

This module encodes lane-specific constraints as SMT formulas
and checks satisfiability.

Public interface:
    verify_candidate(lane: str, candidate: dict) -> Verdict
"""
from typing import Any, Dict
import z3


# ---------------------------------------------------------------------------
# Helper types
# ---------------------------------------------------------------------------

Verdict = Dict[str, Any]  # {stage, passed, reason, details, soft_score, hard_constraints_ok}


def _verdict(stage: str, passed: bool, reason: str,
             details: dict | None = None,
             soft_score: float = 1.0,
             hard_ok: bool = True) -> Verdict:
    return {
        'stage': stage,
        'passed': passed,
        'reason': reason,
        'details': details or {},
        'soft_score': soft_score,
        'hard_constraints_ok': hard_ok,
    }


# ---------------------------------------------------------------------------
# Coding lane — Z3 checks: function defined, tests present, no dangerous calls
# ---------------------------------------------------------------------------

def _verify_coding_z3(candidate: dict) -> Verdict:
    content = candidate.get('content', '')
    tests = candidate.get('tests', [])

    has_def = z3.Bool('has_def')
    has_tests = z3.Bool('has_tests')
    no_eval = z3.Bool('no_eval')
    no_exec_shell = z3.Bool('no_exec_shell')

    s = z3.Solver()
    # Assert concrete values
    s.add(has_def == z3.BoolVal('def ' in content))
    s.add(has_tests == z3.BoolVal(bool(tests)))
    s.add(no_eval == z3.BoolVal('eval(' not in content))
    s.add(no_exec_shell == z3.BoolVal('shell=True' not in content))
    # Constraints: all must be true
    s.add(z3.And(has_def, has_tests, no_eval, no_exec_shell))

    result = s.check()
    passed = (result == z3.sat)
    return _verdict(
        stage='z3_coding',
        passed=passed,
        reason='coding_constraints_satisfied' if passed else 'coding_constraints_violated',
        details={
            'has_def': 'def ' in content,
            'has_tests': bool(tests),
            'no_eval': 'eval(' not in content,
            'no_shell': 'shell=True' not in content,
            'z3_result': str(result),
        },
        soft_score=0.95 if passed else 0.3,
        hard_ok=passed,
    )


# ---------------------------------------------------------------------------
# Business logic lane — Z3: at least one rule fired, no conflicts
# ---------------------------------------------------------------------------

def _verify_business_logic_z3(candidate: dict) -> Verdict:
    rule_results = candidate.get('rule_results', [])
    fired = [r for r in rule_results if r.get('fired')]
    conflicts = candidate.get('conflicts', [])

    at_least_one = z3.Bool('at_least_one_rule')
    no_conflicts = z3.Bool('no_conflicts')

    s = z3.Solver()
    s.add(at_least_one == z3.BoolVal(len(fired) >= 1))
    s.add(no_conflicts == z3.BoolVal(len(conflicts) == 0))
    s.add(z3.And(at_least_one, no_conflicts))

    result = s.check()
    passed = (result == z3.sat)
    return _verdict(
        stage='z3_logic',
        passed=passed,
        reason='at_least_one_rule_fired_no_conflicts' if passed else 'rule_constraint_violated',
        details={'fired': len(fired), 'conflicts': conflicts, 'z3_result': str(result)},
        soft_score=0.92 if passed else 0.35,
        hard_ok=passed,
    )


# ---------------------------------------------------------------------------
# Tool calling lane — Z3: tool_calls list non-empty or content prepared
# ---------------------------------------------------------------------------

def _verify_tool_calling_z3(candidate: dict) -> Verdict:
    calls = candidate.get('tool_calls', [])
    content_ok = 'tool_call_prepared' in candidate.get('content', '')

    has_calls = z3.Bool('has_calls')
    s = z3.Solver()
    s.add(has_calls == z3.BoolVal(bool(calls) or content_ok))
    s.add(has_calls)

    result = s.check()
    passed = (result == z3.sat)
    return _verdict(
        stage='z3_tools',
        passed=passed,
        reason='tool_call_required',
        details={'calls': len(calls), 'content_ok': content_ok, 'z3_result': str(result)},
        soft_score=0.9 if passed else 0.4,
        hard_ok=passed,
    )


# ---------------------------------------------------------------------------
# Agent brain lane — Z3: action was approved
# ---------------------------------------------------------------------------

def _verify_agent_brain_z3(candidate: dict) -> Verdict:
    approved = candidate.get('approved', False)
    a = z3.Bool('action_approved')
    s = z3.Solver()
    s.add(a == z3.BoolVal(bool(approved)))
    s.add(a)
    result = s.check()
    passed = (result == z3.sat)
    return _verdict(
        stage='z3_agent', passed=passed, reason='approved_action_required',
        details={'approved': approved, 'z3_result': str(result)},
        soft_score=0.95 if passed else 0.2, hard_ok=passed,
    )


# ---------------------------------------------------------------------------
# Cross-domain lane — check signals or content present
# ---------------------------------------------------------------------------

def _verify_cross_domain_z3(candidate: dict) -> Verdict:
    has_signals = bool(candidate.get('signals'))
    has_content = bool(candidate.get('content'))
    ok_val = has_signals or has_content
    ok = z3.Bool('has_output')
    s = z3.Solver()
    s.add(ok == z3.BoolVal(ok_val))
    s.add(ok)
    result = s.check()
    passed = (result == z3.sat)
    return _verdict(
        stage='z3_cross_domain', passed=passed, reason='signals_or_content_required',
        details={'signals': has_signals, 'content': has_content, 'z3_result': str(result)},
        soft_score=0.85 if passed else 0.4, hard_ok=passed,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_VERIFIERS = {
    'coding':        _verify_coding_z3,
    'business_logic':_verify_business_logic_z3,
    'tool_calling':  _verify_tool_calling_z3,
    'agent_brain':   _verify_agent_brain_z3,
    'cross_domain':  _verify_cross_domain_z3,
}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def verify_candidate(lane: str, candidate: Dict[str, Any]) -> Verdict:
    """Verify a candidate artifact against lane-specific Z3 constraints.

    Returns a Verdict dict with keys:
        stage, passed, reason, details, soft_score, hard_constraints_ok
    """
    fn = _VERIFIERS.get(lane, _verify_cross_domain_z3)
    return fn(candidate)
