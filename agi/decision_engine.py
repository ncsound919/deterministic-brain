"""Decision Engine: REVIEW → PLAN logic for the daily operational loop."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional


@dataclass
class DailyContext:
    portfolio_pulse: str
    total_tests: int
    deploy_readiness: float
    yesterday_calls: int
    yesterday_answered: int
    yesterday_converted: int
    yesterday_cost: float
    openhub_velocity: float
    openhub_pipelines_active: int
    openhub_pipelines_completed: int
    raw_tracker: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CampaignPlan:
    profile_id: str
    max_concurrent: int
    delay_between_calls: float
    filter_status: str
    lead_limit: int
    territory: str = "default"


@dataclass
class DailyPlan:
    plan_id: str
    date: str
    campaigns: List[CampaignPlan] = field(default_factory=list)
    openhub_priority: str = "maintenance"
    stop_conditions: Dict[str, Any] = field(default_factory=dict)
    expected_effects: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""


class DecisionEngine:
    def review(
        self,
        tracker_state: Dict[str, Any],
        aetherdesk_summary: Dict[str, Any],
        openhub_summary: Dict[str, Any],
    ) -> DailyContext:
        return DailyContext(
            portfolio_pulse=tracker_state.get("pulse", "stable"),
            total_tests=tracker_state.get("tests_passing", 0),
            deploy_readiness=tracker_state.get("deploy_readiness", 0.0),
            yesterday_calls=aetherdesk_summary.get("total_calls", 0),
            yesterday_answered=aetherdesk_summary.get("answered", 0),
            yesterday_converted=aetherdesk_summary.get("converted", 0),
            yesterday_cost=aetherdesk_summary.get("cost", 0.0),
            openhub_velocity=openhub_summary.get("pipelines_completed", 0),
            openhub_pipelines_active=openhub_summary.get("active_pipelines", 0),
            openhub_pipelines_completed=openhub_summary.get("completed_today", 0),
            raw_tracker={
                "tracker": tracker_state,
                "aetherdesk": aetherdesk_summary,
                "openhub": openhub_summary,
            },
        )

    def plan(self, context: DailyContext) -> DailyPlan:
        today = date.today().isoformat()
        plan = DailyPlan(
            plan_id=f"plan-{today}-001",
            date=today,
            created_at=datetime.utcnow().isoformat(),
        )

        if context.yesterday_converted > 0:
            plan.campaigns.append(CampaignPlan(
                profile_id="PROF-META-SALES",
                max_concurrent=3,
                delay_between_calls=10.0,
                filter_status="new",
                lead_limit=50,
                territory="us-east",
            ))

        if context.yesterday_calls == 0 and context.yesterday_converted == 0:
            plan.campaigns.append(CampaignPlan(
                profile_id="PROF-STARTER-OUTREACH",
                max_concurrent=2,
                delay_between_calls=15.0,
                filter_status="new",
                lead_limit=30,
                territory="us-east",
            ))

        if context.openhub_pipelines_completed > 0:
            plan.openhub_priority = "feature_development"
        elif context.openhub_pipelines_active > 0:
            plan.openhub_priority = "continue_current"

        plan.stop_conditions = {
            "min_answer_rate": 0.20,
            "max_concurrent_campaigns": 3,
            "max_attempts_per_lead": 3,
            "quiet_hours": {"dow": ["sun"], "start": "21:00", "end": "08:00"},
        }
        plan.expected_effects = {
            "calls_attempted": sum(c.lead_limit for c in plan.campaigns),
            "interested": max(1, int(sum(c.lead_limit for c in plan.campaigns) * 0.10)),
            "converted": max(1, int(sum(c.lead_limit for c in plan.campaigns) * 0.03)),
            "max_cost": sum(c.lead_limit for c in plan.campaigns) * 0.02,
        }

        return plan
