from __future__ import annotations
"""
PyReason adapter — neuro-symbolic graph reasoning over retrieved contexts.

When the `pyreason` package is installed this module uses it to run
temporal annotated logic rules over a small in-memory graph built from
the retrieved contexts.  When pyreason is absent it falls back to a
pure-Python rule engine that produces the same interface contract:

    (derived_facts: list[dict], trace: list[str])
"""
import re
from typing import Any

try:
    import pyreason as pr
    _PR_OK = True
except ImportError:
    _PR_OK = False


# ---------------------------------------------------------------------------
# Lane-specific rule sets (Python fallback)
# ---------------------------------------------------------------------------

class _Rule:
    def __init__(self, name: str, patterns: list[str], conclusion: str, weight: float = 1.0):
        self.name = name
        self.patterns = [p.lower() for p in patterns]
        self.conclusion = conclusion
        self.weight = weight

    def fires(self, text: str) -> bool:
        t = text.lower()
        return any(p in t for p in self.patterns)


_LANE_RULES: dict[str, list[_Rule]] = {
    'coding': [
        _Rule('needs_tests',      ['test', 'pytest', 'coverage'],  'requires_test_suite', 0.9),
        _Rule('needs_types',      ['type hint', 'annotation', 'mypy'], 'requires_type_annotations', 0.85),
        _Rule('needs_docstring',  ['docstring', 'doctest', 'sphinx'], 'requires_documentation', 0.80),
        _Rule('security_scan',   ['sql', 'exec(', 'eval(', 'shell=True'], 'flag_security_review', 1.0),
    ],
    'business_logic': [
        _Rule('approval_required', ['approval', 'authoris', 'sign-off', 'budget request'],
              'escalate_for_approval', 1.0),
        _Rule('compliance_check',  ['gdpr', 'hipaa', 'pci', 'compliance', 'regulation'],
              'run_compliance_check', 1.0),
        _Rule('conflict_risk',     ['conflict', 'contradict', 'mutual exclusive', 'override'],
              'flag_rule_conflict', 0.95),
    ],
    'agent_brain': [
        _Rule('external_link',   ['http', 'https', 'external', 'click link'], 'verify_link_policy', 1.0),
        _Rule('data_exfil',      ['download', 'export', 'send data', 'upload'],  'flag_data_exfil_risk', 1.0),
        _Rule('auth_required',   ['login', 'sign in', 'authenticate', 'credentials'], 'require_auth_approval', 1.0),
    ],
    'tool_calling': [
        _Rule('schema_check',    ['schema', 'validate', 'json', 'format'], 'enforce_schema_validation', 0.95),
        _Rule('rate_limit',      ['rate', 'throttle', 'quota', 'limit'],    'apply_rate_limiting', 0.80),
        _Rule('idempotency',     ['idempotent', 'retry', 'duplicate'],      'verify_idempotency', 0.75),
    ],
    'cross_domain': [
        _Rule('evidence_merge',  ['evidence', 'source', 'corroborate', 'confirm'], 'merge_evidence', 0.85),
        _Rule('contradiction',   ['contradict', 'conflict', 'disagree', 'oppose'], 'flag_contradiction', 0.90),
        _Rule('low_confidence',  ['uncertain', 'unclear', 'ambiguous', 'unknown'],  'request_clarification', 0.70),
    ],
}


# ---------------------------------------------------------------------------
# PyReason-backed graph reasoning
# ---------------------------------------------------------------------------

def _pyreason_reason(lane: str, contexts: list[dict], query: str) -> tuple[list[dict], list[str]]:
    """Run pyreason on a small graph built from contexts."""
    import tempfile, os, yaml

    # Build a minimal YAML graph file
    nodes = [{'name': c['id'], 'facts': [f'text_{re.sub(chr(32), "_", c["text"][:30])}']} for c in contexts]
    edges = [{'from': contexts[i]['id'], 'to': contexts[i+1]['id'], 'label': 'linked'}
             for i in range(len(contexts)-1)]
    graph_data = {'nodes': nodes, 'edges': edges}

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(graph_data, f)
        graph_path = f.name

    try:
        pr.reset()
        pr.load_graph(graph_path)
        # Simple rule: connected nodes share context
        pr.add_rule('linked(X,Y) ^ text(X) => context_linked(X,Y) : [0.8, 1]')
        pr.reason(timesteps=2)
        interp = pr.get_interpretation()
        derived = []
        trace = []
        for atom, bounds in interp.items():
            if bounds[0] > 0.5:
                derived.append({'fact': str(atom), 'confidence': float(bounds[0])})
                trace.append(f'pyreason: {atom} [{bounds[0]:.2f}, {bounds[1]:.2f}]')
        return derived, trace
    except Exception as exc:  # noqa: BLE001
        return [], [f'pyreason_error: {exc}']
    finally:
        os.unlink(graph_path)


# ---------------------------------------------------------------------------
# Pure-Python fallback rule engine
# ---------------------------------------------------------------------------

def _python_reason(lane: str, contexts: list[dict], query: str) -> tuple[list[dict], list[str]]:
    """Apply lane rules against all context texts + query."""
    rules = _LANE_RULES.get(lane, _LANE_RULES['cross_domain'])
    all_text = query + ' ' + ' '.join(c.get('text', '') for c in contexts)

    derived: list[dict] = []
    trace: list[str] = []

    for rule in rules:
        if rule.fires(all_text):
            derived.append({
                'fact': rule.conclusion,
                'rule': rule.name,
                'weight': rule.weight,
                'lane': lane,
            })
            trace.append(f'rule:{rule.name} => {rule.conclusion} (w={rule.weight})')

    # Always emit a base context-count fact
    derived.append({'fact': 'context_available', 'count': len(contexts), 'lane': lane})
    trace.append(f'base: {len(contexts)} contexts retrieved for lane={lane}')
    return derived, trace


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------

class PyReasonAdapter:
    """Unified interface: uses pyreason if available, else pure-Python rules."""

    def reason(
        self,
        lane: str,
        contexts: list[dict],
        query: str,
    ) -> tuple[list[dict], list[str]]:
        """Return (derived_facts, trace) for the given lane and contexts."""
        if _PR_OK and contexts:
            try:
                return _pyreason_reason(lane, contexts, query)
            except Exception:  # noqa: BLE001
                pass
        return _python_reason(lane, contexts, query)


# ---------------------------------------------------------------------------
# Legacy shim (keep backward compat with old import)
# ---------------------------------------------------------------------------

def enrich_business_logic(text: str) -> str:
    adapter = PyReasonAdapter()
    facts, _ = adapter.reason('business_logic', [], text)
    tags = ', '.join(f['fact'] for f in facts)
    return f'Policy/Rule Draft [{tags}]: {text}'
