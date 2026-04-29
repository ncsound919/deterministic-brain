from __future__ import annotations
from tools.llm.router import chat
from lanes.business_logic.rule_engine import APPROVAL_RULESET, COMPLIANCE_RULESET
from lanes.business_logic.conflict_detector import detect_conflicts

_SYSTEM = """You are a deterministic business logic expert.
Given a set of fired rules and their context, produce a structured policy decision.
Format your response as:
DECISION: <one of: AUTO_APPROVE | MANAGER_APPROVAL | FINANCE_APPROVAL | REQUIRE_AUDIT_LOG | REQUIRE_ROLE | REQUIRE_ELEVATION | BLOCKED>
RATIONALE: <2-3 sentences explaining the decision>
ACTIONS: <comma-separated list of required actions>
RISK_LEVEL: <LOW | MEDIUM | HIGH>"""

def _select_ruleset(query: str):
    q = query.lower()
    if 'approval' in q or 'budget' in q or 'amount' in q:
        return APPROVAL_RULESET, {'amount': 500, 'requester': 'user@company.com'}
    if 'compliance' in q or 'audit' in q or 'export' in q:
        return COMPLIANCE_RULESET, {'data_class': 'sensitive', 'role': None, 'action': 'export'}
    return APPROVAL_RULESET, {'amount': 100}

def run(state: dict) -> dict:
    ruleset, context = _select_ruleset(state['query'])
    rule_results = ruleset.evaluate(context)
    conflicts = detect_conflicts(rule_results)
    fired = [r for r in rule_results if r['fired']]
    rules_text = ['Rule ' + r['rule_id'] + ': ' + r['name'] + ' -> ' + str(r['action']) for r in fired]

    user_msg = (
        f"Query: {state['query']}\n\n"
        f"Ruleset: {ruleset.name}\n"
        f"Fired rules: {'; '.join(rules_text) if rules_text else 'None'}\n"
        f"Conflicts: {'; '.join(conflicts) if conflicts else 'None'}\n"
        f"Rule context: {context}\n\n"
        "Produce the policy decision."
    )

    content = chat(system=_SYSTEM, user=user_msg, lane='business_logic')

    candidate = {'id': 'logic1', 'kind': 'business_logic', 'content': content,
                 'rules': rules_text, 'rule_results': rule_results, 'conflicts': conflicts}
    state['candidate_artifacts'] = [candidate]
    state['working_memory']['rule_set'] = rules_text
    state['working_memory']['rule_context'] = context
    state['working_memory']['conflicts'] = conflicts
    state['final_output'] = content
    state['output_mode'] = 'plan'
    state['confidence'] = 0.94 if not conflicts else 0.68
    state['history'].append({'lane': 'business_logic', 'candidate': candidate['id'],
                             'rules_fired': len(fired), 'conflicts': len(conflicts),
                             'llm_backend': 'claude_via_openrouter'})
    return state
