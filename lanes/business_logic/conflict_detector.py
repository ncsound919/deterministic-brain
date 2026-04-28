from __future__ import annotations

def detect_conflicts(rule_results: list) -> list:
    fired_actions = [r['action'] for r in rule_results if r['fired']]
    conflicts = []
    if 'AUTO_APPROVE' in fired_actions and 'MANAGER_APPROVAL' in fired_actions:
        conflicts.append('Conflict: AUTO_APPROVE and MANAGER_APPROVAL both fired')
    if 'AUTO_APPROVE' in fired_actions and 'FINANCE_APPROVAL' in fired_actions:
        conflicts.append('Conflict: AUTO_APPROVE and FINANCE_APPROVAL both fired')
    return conflicts
