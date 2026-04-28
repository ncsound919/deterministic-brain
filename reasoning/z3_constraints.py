from __future__ import annotations
"""
Z3-backed constraint verification for each lane.

When z3-solver is installed this module encodes lane-specific constraints
as SMT formulas and checks satisfiability.  When z3 is absent it falls
back to pure-Python heuristic checks that mirror the same logic.

Public interface:
    verify_candidate(lane: str, candidate: dict) -> Verdict
"""
from typing import Any, Dict

try:
    import z3
    _Z3_OK = True
except ImportError:
    _Z3_OK = False


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


def _verify_coding_py(candidate: dict) -> Verdict:
    content = candidate.get('content', '')
    tests = candidate.get('tests', [])
    has_def = 'def ' in content
    has_tests = bool(tests)
    no_eval = 'eval(' not in content
    no_shell = 'shell=True' not in content
    passed = has_def and has_tests and no_eval and no_shell
    return _verdict(
        stage='z3_contract',
        passed=passed,
        reason='function_and_tests_required',
        details={'tests': len(tests), 'has_def': has_def, 'no_eval': no_eval},
        soft_score=0.9 if passed else 0.3,
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


def _verify_business_logic_py(candidate: dict) -> Verdict:
    rule_results = candidate.get('rule_results', [])
    fired = [r for r in rule_results if r.get('fired')]
    conflicts = candidate.get('conflicts', [])
    ok = len(fired) >= 1 and len(conflicts) == 0
    return _verdict(
        stage='z3_logic',
        passed=ok,
        reason='at_least_one_rule_fired_no_conflicts',
        details={'fired': len(fired), 'conflicts': conflicts},
        soft_score=0.9 if ok else 0.35,
        hard_ok=ok,
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


def _verify_tool_calling_py(candidate: dict) -> Verdict:
    calls = candidate.get('tool_calls', [])
    content_ok = 'tool_call_prepared' in candidate.get('content', '')
    ok = bool(calls) or content_ok
    return _verdict(
        stage='z3_tools', passed=ok, reason='tool_call_required',
        details={'calls': len(calls)}, soft_score=0.9 if ok else 0.4, hard_ok=ok,
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


def _verify_agent_brain_py(candidate: dict) -> Verdict:
    ok = candidate.get('approved', False)
    return _verdict(
        stage='z3_agent', passed=bool(ok), reason='approved_action_required',
        details={'approved': ok}, soft_score=0.95 if ok else 0.2, hard_ok=bool(ok),
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


def _verify_cross_domain_py(candidate: dict) -> Verdict:
    ok = bool(candidate.get('signals')) or bool(candidate.get('content'))
    return _verdict(
        stage='z3_cross_domain', passed=ok, reason='signals_or_content_required',
        details={'signals': bool(candidate.get('signals')), 'content': bool(candidate.get('content'))},
        soft_score=0.85 if ok else 0.4, hard_ok=ok,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_Z3_VERIFIERS = {
    'coding':        (_verify_coding_z3,         _verify_coding_py),
    'business_logic':(_verify_business_logic_z3,  _verify_business_logic_py),
    'tool_calling':  (_verify_tool_calling_z3,    _verify_tool_calling_py),
    'agent_brain':   (_verify_agent_brain_z3,     _verify_agent_brain_py),
    'cross_domain':  (_verify_cross_domain_z3,    _verify_cross_domain_py),
}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def verify_candidate(lane: str, candidate: Dict[str, Any]) -> Verdict:
    """Verify a candidate artifact against lane-specific Z3 or Python constraints.

    Returns a Verdict dict with keys:
        stage, passed, reason, details, soft_score, hard_constraints_ok
    """
    z3_fn, py_fn = _Z3_VERIFIERS.get(
        lane,
        (_verify_cross_domain_z3, _verify_cross_domain_py),
    )
    if _Z3_OK:
        try:
            return z3_fn(candidate)
        except Exception:  # noqa: BLE001
            pass
    return py_fn(candidate)
