from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

@dataclass
class Rule:
    id: str
    name: str
    condition: Callable[[dict], bool]
    action: str
    priority: int = 0
    metadata: dict = field(default_factory=dict)

@dataclass
class RuleSet:
    name: str
    rules: list = field(default_factory=list)

    def evaluate(self, context: dict) -> list:
        results = []
        for rule in sorted(self.rules, key=lambda r: -r.priority):
            fired = rule.condition(context)
            results.append({'rule_id': rule.id, 'name': rule.name, 'fired': fired,
                            'action': rule.action if fired else None})
        return results

APPROVAL_RULESET = RuleSet(name='Approval', rules=[
    Rule('r1', 'auto_approve', lambda c: c.get('amount', 0) < 1000, 'AUTO_APPROVE', priority=3),
    Rule('r2', 'manager_approve', lambda c: 1000 <= c.get('amount', 0) < 10000, 'MANAGER_APPROVAL', priority=2),
    Rule('r3', 'finance_approve', lambda c: c.get('amount', 0) >= 10000, 'FINANCE_APPROVAL', priority=1),
])

COMPLIANCE_RULESET = RuleSet(name='Compliance', rules=[
    Rule('c1', 'audit_log_sensitive', lambda c: c.get('data_class') == 'sensitive', 'REQUIRE_AUDIT_LOG', priority=3),
    Rule('c2', 'rbac_required', lambda c: not c.get('role'), 'REQUIRE_ROLE', priority=2),
    Rule('c3', 'export_elevated', lambda c: c.get('action') == 'export', 'REQUIRE_ELEVATION', priority=1),
])
