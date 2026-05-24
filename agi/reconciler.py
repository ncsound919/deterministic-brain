"""Reconciler: compares expected vs observed daily outcomes."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ledger import read_events


@dataclass
class DriftItem:
    field: str
    expected: Any
    observed: Any
    delta: Any


@dataclass
class DriftReport:
    plan_id: str
    date: str
    reconciled_at: str = ""
    campaigns_launched: int = 0
    campaigns_completed: int = 0
    calls_attempted: int = 0
    calls_answered: int = 0
    voicemails: int = 0
    interested: int = 0
    converted: int = 0
    total_duration_minutes: float = 0.0
    answer_rate: float = 0.0
    conversion_rate: float = 0.0
    total_cost: float = 0.0
    drift_items: List[Dict[str, Any]] = field(default_factory=list)
    corrective_actions: List[str] = field(default_factory=list)
    learning_inputs: Dict[str, Any] = field(default_factory=dict)


class Reconciler:
    def compare(
        self,
        plan: Dict[str, Any],
        campaign_stats: Dict[str, Any],
        usage: Dict[str, Any],
        velocity: Dict[str, Any] = None,
    ) -> DriftReport:
        now = datetime.now(timezone.utc).isoformat()
        expected = plan.get("expected_effects", {})

        report = DriftReport(
            plan_id=plan.get("plan_id", ""),
            date=plan.get("date", ""),
            reconciled_at=now,
            campaigns_launched=len(plan.get("campaigns", [])),
            calls_attempted=campaign_stats.get("total_calls", 0),
            calls_answered=campaign_stats.get("answered", 0),
            voicemails=campaign_stats.get("voicemail", 0),
            interested=campaign_stats.get("interested", 0),
            converted=campaign_stats.get("converted", 0),
            total_cost=usage.get("cost", 0.0),
        )

        report.answer_rate = (
            report.calls_answered / report.calls_attempted
            if report.calls_attempted > 0
            else 0.0
        )
        report.conversion_rate = (
            report.converted / report.calls_attempted
            if report.calls_attempted > 0
            else 0.0
        )

        drift_items = []

        expected_calls = expected.get("calls_attempted", 0)
        if expected_calls > 0 and report.calls_attempted != expected_calls:
            drift_items.append({
                "field": "calls_attempted",
                "expected": expected_calls,
                "observed": report.calls_attempted,
                "delta": report.calls_attempted - expected_calls,
            })

        expected_interested = expected.get("interested", 0)
        if expected_interested > 0 and report.interested != expected_interested:
            drift_items.append({
                "field": "interested",
                "expected": expected_interested,
                "observed": report.interested,
                "delta": report.interested - expected_interested,
            })

        expected_cost = expected.get("max_cost", 0)
        if expected_cost > 0 and report.total_cost > expected_cost:
            drift_items.append({
                "field": "total_cost",
                "expected": expected_cost,
                "observed": report.total_cost,
                "delta": report.total_cost - expected_cost,
            })

        report.drift_items = drift_items

        if drift_items:
            report.corrective_actions.append("review_drift_items")
        if report.answer_rate < 0.20:
            report.corrective_actions.append("reduce_lead_limit_or_check_profile")

        report.learning_inputs = {
            "best_profile": plan.get("campaigns", [{}])[0].get("profile_id", "unknown") if plan.get("campaigns") else "unknown",
            "answer_rate_benchmark": report.answer_rate,
            "conversion_rate_benchmark": report.conversion_rate,
            "drift_count": len(drift_items),
        }

        return report

    def write_drift_report(self, report: DriftReport) -> Dict[str, Any]:
        return {
            "plan_id": report.plan_id,
            "date": report.date,
            "reconciled_at": report.reconciled_at,
            "calls_attempted": report.calls_attempted,
            "calls_answered": report.calls_answered,
            "voicemails": report.voicemails,
            "interested": report.interested,
            "converted": report.converted,
            "total_duration_minutes": report.total_duration_minutes,
            "answer_rate": report.answer_rate,
            "conversion_rate": report.conversion_rate,
            "total_cost": report.total_cost,
            "drift_items": report.drift_items,
            "corrective_actions": report.corrective_actions,
            "learning_inputs": report.learning_inputs,
        }

    def emit_learning_inputs(self, report: DriftReport, plan: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "timestamp": report.reconciled_at,
            "plan_id": report.plan_id,
            "answer_rate": report.answer_rate,
            "conversion_rate": report.conversion_rate,
            "total_cost": report.total_cost,
            "drift_count": len(report.drift_items),
            "corrective_actions": report.corrective_actions,
        }
