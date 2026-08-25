"""Dev Brain — agent guardrails, blast radius & circuit breakers.

Ported from ncsound919/Dev-Brain src/engine/guardrailEngine.ts.
Rule-gated action evaluation with composite risk-tier scoring for agent
action payloads. Complements deterministic-brain's policy_engine /
z3_constraints: this is the per-action pre-flight check.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def evaluate_condition(
    actual: Any, operator: str, threshold: Any
) -> bool:
    """Shared condition evaluator (mirrors DecisionTreeEngine.evaluateCondition)."""
    try:
        if operator == "gt":
            return float(actual) > float(threshold)
        if operator == "gte":
            return float(actual) >= float(threshold)
        if operator == "lt":
            return float(actual) < float(threshold)
        if operator == "lte":
            return float(actual) <= float(threshold)
        if operator == "eq":
            return actual == threshold
        if operator == "neq":
            return actual != threshold
        if operator == "exists":
            return actual is not None
        if operator == "contains":
            return str(threshold) in str(actual)
    except (TypeError, ValueError):
        return False
    return False


class GuardrailEngine:
    @staticmethod
    def evaluate_guardrails(
        payload: Dict[str, Any], rules: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        violated = []
        parameters = payload.get("parameters", {})
        for rule in rules:
            if not rule.get("enabled", False):
                continue
            evaluator = rule["evaluator"]
            field = evaluator["field"]
            actual_value = parameters.get(field)
            if actual_value is not None and evaluate_condition(
                actual_value,
                evaluator["operator"],
                evaluator["thresholdValue"],
            ):
                violated.append({
                    "ruleId": rule["id"],
                    "ruleName": rule["name"],
                    "severity": rule["severity"],
                    "remediationAdvice": rule["remediationAdvice"],
                })
        return {
            "violatedRules": violated,
            "hasBlockingViolations": any(
                v["severity"] == "BLOCKING" for v in violated
            ),
            "hasEscalationViolations": any(
                v["severity"] == "ESCALATION_REQUIRED" for v in violated
            ),
        }

    @staticmethod
    def calculate_blast_radius(payload: Dict[str, Any]) -> Dict[str, Any]:
        params = payload.get("parameters", {}) or {}
        financial = customer = system = legal = 10
        irreversible = False
        recovery_time = "< 5 minutes"
        worst_case = "Minor temporary operational logging overhead."

        # 1. Financial
        amount = float(
            params.get(
                "amount_usd",
                params.get(
                    "refund_amount_usd", params.get("estimated_cost_usd", 0)
                ),
            )
            or 0
        )
        if amount > 5000:
            financial = 95
            worst_case = (
                "Material direct capital depletion exceeding monthly burn "
                "threshold."
            )
        elif amount > 1000:
            financial = 75
            worst_case = (
                "Unbudgeted capital outflow requiring treasury liquidity "
                "adjustment."
            )
        elif amount > 100:
            financial = 40

        discount = params.get("discount_percentage")
        if discount is not None and float(discount) > 30:
            financial = max(financial, 85)
            worst_case = (
                "Permanent degradation of average revenue per account (ARPU) "
                "and customer margin erosion."
            )

        # 2. Customer / brand reach
        recipients = float(params.get("recipient_count", 1) or 1)
        if recipients > 500:
            customer = 90
            worst_case = (
                "Mass public email spam report cascade leading to domain "
                "deliverability blacklisting."
            )
        elif recipients > 50:
            customer = 65
        elif params.get("action_scope") in ("mass_broadcast", "public_social_post"):
            customer = 80

        if params.get("contains_future_promises") is True:
            customer = max(customer, 75)
            legal = max(legal, 80)
            worst_case = (
                "Creation of legally binding feature/SLA delivery obligations "
                "subject to promissory estoppel."
            )

        # 3. System & database integrity
        if params.get("has_destructive_syntax") is True:
            system = 100
            irreversible = True
            recovery_time = "Hours / Point-in-time restore required"
            worst_case = (
                "Total loss of live transactional production tables with "
                "active user downtime."
            )
        elif params.get("is_production_mutation") is True:
            system = max(system, 65)
            if params.get("has_verified_rollback_and_backup") is False:
                system = 85
                worst_case = (
                    "Production schema lock without automated down-migration "
                    "recovery mechanism."
                )

        recursion_depth = params.get("recursion_depth")
        if recursion_depth is not None and float(recursion_depth) > 4:
            system = max(system, 80)
            worst_case = (
                "Asynchronous swarm lockup exhausting serverless worker "
                "capacity."
            )

        # 4. Legal / PII secrets
        if params.get("contains_pii_or_secrets") is True:
            legal = 95
            worst_case = (
                "Regulatory data privacy violation (GDPR/CCPA) and credential "
                "exposure to public logs."
            )
        if (
            params.get("has_custom_liabilities") is True
            or params.get("has_uncapped_liability") is True
        ):
            legal = 95
            worst_case = (
                "Uncapped indemnification exposure in enterprise customer "
                "contract."
            )

        overall = round(
            financial * 0.30 + customer * 0.25 + system * 0.25 + legal * 0.20
        )
        if overall >= 80 or system >= 90 or legal >= 90 or financial >= 90:
            tier = "CATASTROPHIC"
        elif overall >= 60:
            tier = "HIGH"
        elif overall >= 30:
            tier = "MEDIUM"
        else:
            tier = "LOW"

        return {
            "financialRiskScore": financial,
            "customerImpactScore": customer,
            "systemIntegrityScore": system,
            "legalRegulatoryScore": legal,
            "overallRiskScore": overall,
            "riskTier": tier,
            "isIrreversible": irreversible,
            "estimatedRecoveryTime": recovery_time,
            "worstCaseScenario": worst_case,
        }

    @staticmethod
    def check_circuit_breakers(
        payload: Dict[str, Any],
        breakers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        global_breaker = next(
            (b for b in breakers if b["id"] == "cb_global_kill"), None
        )
        if global_breaker and global_breaker.get("status") == "TRIPPED":
            return {
                "isTripped": True,
                "status": "TRIPPED_GLOBAL",
                "trippedBreaker": global_breaker,
            }
        domain_breaker = next(
            (
                b
                for b in breakers
                if b.get("domain") == payload.get("actionType")
                and b.get("status") == "TRIPPED"
            ),
            None,
        )
        if domain_breaker:
            return {
                "isTripped": True,
                "status": "TRIPPED_DOMAIN",
                "trippedBreaker": domain_breaker,
            }
        return {"isTripped": False, "status": "NORMAL", "trippedBreaker": None}
