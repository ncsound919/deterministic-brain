from __future__ import annotations

from reasoning.pyreason_adapter import enrich_business_logic
from lanes.business_logic.rule_engine import APPROVAL_RULESET, COMPLIANCE_RULESET
from lanes.business_logic.conflict_detector import detect_conflicts

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
    rules_text = ['Rule ' + r['rule_id'] + ': ' + r['name'] + ' -> ' + r['action'] for r in fired]
    content = enrich_business_logic(ruleset.name + ': ' + '; '.join(rules_text) if rules_text else 'No rules fired')
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
                             'rules_fired': len(fired), 'conflicts': len(conflicts)})
    return state
