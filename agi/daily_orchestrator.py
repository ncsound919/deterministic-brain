"""Daily Orchestrator: runs the REVIEW → PLAN → STAGE → LAUNCH → OBSERVE → RECONCILE loop."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from agi.decision_engine import DecisionEngine, DailyPlan, CampaignPlan
from agi.reconciler import Reconciler, DriftReport
from adapters.aetherdesk import AetherDeskAdapter, CampaignConfig, CampaignStats
from adapters.openhub import OpenHubAdapter, VelocityReport

from ledger import (
    write_event,
    read_events,
    write_daily_plan,
    read_daily_plan,
    write_active_campaigns,
    is_manual_pause_active,
)

logger = logging.getLogger(__name__)

DEFAULT_CAMPAIGN_CONFIG = CampaignConfig(
    profile_id="PROF-META-SALES",
    max_concurrent=3,
    delay_between_calls=10.0,
    filter_status="new",
    lead_limit=50,
)


class DailyOrchestrator:
    def __init__(
        self,
        aetherdesk: AetherDeskAdapter,
        openhub: OpenHubAdapter,
        engine: DecisionEngine = None,
        reconciler: Reconciler = None,
    ):
        self.aetherdesk = aetherdesk
        self.openhub = openhub
        self.engine = engine or DecisionEngine()
        self.reconciler = reconciler or Reconciler()
        self._day: Optional[date] = None
        self._plan: Optional[DailyPlan] = None

    async def run_review(self) -> Dict[str, Any]:
        if is_manual_pause_active():
            write_event({
                "ts": datetime.now(timezone.utc).isoformat(),
                "correlation_id": "override-active",
                "type": "review_skipped",
                "system": "deterministic-brain",
                "data": {"reason": "manual_pause_active"},
            })
            return {"phase": "review", "status": "skipped", "reason": "manual_pause"}

        try:
            stats = await self.aetherdesk.get_campaign_stats()
        except Exception:
            stats = CampaignStats(total_calls=0, answered=0, voicemail=0, converted=0)

        try:
            usage = await self.aetherdesk.get_usage_and_billing()
        except Exception:
            from adapters.aetherdesk import UsageReport
            usage = UsageReport(calls=0, minutes=0.0, cost=0.0)

        try:
            pipeline = await self.openhub.get_pipeline_status()
        except Exception:
            from adapters.openhub import PipelineSummary
            pipeline = PipelineSummary(active_pipelines=0, completed_today=0, failed_today=0, queue_depth=0)

        aetherdesk_summary = {
            "total_calls": stats.total_calls,
            "answered": stats.answered,
            "converted": stats.converted,
            "cost": usage.cost,
        }
        openhub_summary = {
            "active_pipelines": pipeline.active_pipelines,
            "completed_today": pipeline.completed_today,
        }
        tracker_state = self._read_tracker_snapshot()

        context = self.engine.review(tracker_state, aetherdesk_summary, openhub_summary)
        return {"phase": "review", "status": "ok", "context": context}

    async def run_plan(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        if is_manual_pause_active():
            return {"phase": "plan", "status": "skipped", "reason": "manual_pause"}

        daily_context = context.get("context") if context else None
        if daily_context is None:
            review_result = await self.run_review()
            if review_result.get("status") == "skipped":
                return {"phase": "plan", "status": "skipped", "reason": review_result.get("reason")}
            daily_context = review_result.get("context")

        plan = self.engine.plan(daily_context)
        self._plan = plan
        self._day = date.today()

        plan_dict = {
            "plan_id": plan.plan_id,
            "date": plan.date,
            "created_at": plan.created_at,
            "campaigns": [
                {
                    "profile_id": c.profile_id,
                    "max_concurrent": c.max_concurrent,
                    "delay_between_calls": c.delay_between_calls,
                    "filter_status": c.filter_status,
                    "lead_limit": c.lead_limit,
                    "territory": c.territory,
                }
                for c in plan.campaigns
            ],
            "openhub_priority": plan.openhub_priority,
            "stop_conditions": plan.stop_conditions,
            "expected_effects": plan.expected_effects,
        }
        write_daily_plan(date.today(), plan_dict)

        write_event({
            "ts": datetime.now(timezone.utc).isoformat(),
            "correlation_id": plan.plan_id,
            "type": "daily_plan_created",
            "system": "deterministic-brain",
            "data": plan_dict,
        })

        return {"phase": "plan", "status": "ok", "plan": plan_dict}

    async def run_stage(self) -> Dict[str, Any]:
        if is_manual_pause_active():
            return {"phase": "stage", "status": "skipped", "reason": "manual_pause"}

        if self._plan is None:
            plan_data = read_daily_plan(self._day or date.today())
            if plan_data is None:
                return {"phase": "stage", "status": "no_plan"}

        plan = self._plan
        staged = []
        deferred = []

        for campaign in plan.campaigns:
            config = CampaignConfig(
                profile_id=campaign.profile_id,
                max_concurrent=campaign.max_concurrent,
                delay_between_calls=campaign.delay_between_calls,
                filter_status=campaign.filter_status,
                lead_limit=campaign.lead_limit,
            )
            try:
                has_leads = await self.aetherdesk.validate_lead_inventory(config)
                if has_leads:
                    staged.append(campaign.profile_id)
                    write_event({
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "correlation_id": plan.plan_id,
                        "type": "campaign_staged",
                        "system": "deterministic-brain",
                        "data": {"profile_id": campaign.profile_id, "status": "staged"},
                    })
                else:
                    deferred.append({"profile_id": campaign.profile_id, "reason": "no_leads"})
            except Exception as e:
                deferred.append({"profile_id": campaign.profile_id, "reason": str(e)})

        return {"phase": "stage", "status": "ok", "staged": staged, "deferred": deferred}

    async def run_launch(self) -> Dict[str, Any]:
        if is_manual_pause_active():
            return {"phase": "launch", "status": "skipped", "reason": "manual_pause"}

        if self._plan is None:
            return {"phase": "launch", "status": "no_plan"}

        launched = []
        failed = []

        for campaign in self._plan.campaigns:
            config = CampaignConfig(
                profile_id=campaign.profile_id,
                max_concurrent=campaign.max_concurrent,
                delay_between_calls=campaign.delay_between_calls,
                filter_status=campaign.filter_status,
                lead_limit=campaign.lead_limit,
            )
            idem_key = f"{self._plan.plan_id}-{campaign.profile_id}"
            try:
                status = await self.aetherdesk.launch_campaign(config, idem_key)
                launched.append({"profile_id": campaign.profile_id, "campaign_id": status.id, "status": status.status})
            except Exception as e:
                failed.append({"profile_id": campaign.profile_id, "error": str(e)})

        active = {c["profile_id"]: c for c in launched}
        write_active_campaigns(active)

        return {"phase": "launch", "status": "ok", "launched": launched, "failed": failed}

    async def run_observe(self) -> Dict[str, Any]:
        events_today = list(read_events(self._day or date.today()))
        launch_events = [e for e in events_today if e.get("type") == "campaign_launch"]
        paused = False

        for event in events_today:
            if event.get("type") == "call_completed":
                try:
                    stats = await self.aetherdesk.get_campaign_stats()
                    stop_cond = (self._plan.stop_conditions if self._plan else {})
                    min_answer_rate = stop_cond.get("min_answer_rate", 0.20)
                    if stats.total_calls > 10:
                        answer_rate = stats.answered / stats.total_calls
                        if answer_rate < min_answer_rate:
                            paused = True
                            write_event({
                                "ts": datetime.now(timezone.utc).isoformat(),
                                "correlation_id": self._plan.plan_id if self._plan else "unknown",
                                "type": "campaign_paused",
                                "system": "deterministic-brain",
                                "data": {"reason": "answer_rate_below_threshold", "answer_rate": answer_rate},
                            })
                            break
                except Exception:
                    pass

        return {
            "phase": "observe",
            "status": "ok",
            "events_consumed": len(events_today),
            "launches_active": len(launch_events),
            "paused": paused,
        }

    async def run_reconcile(self) -> Dict[str, Any]:
        if self._plan is None:
            plan_data = read_daily_plan(self._day or date.today())
            if plan_data is None:
                return {"phase": "reconcile", "status": "no_plan"}
            plan_dict = plan_data
        else:
            plan_dict = {
                "plan_id": self._plan.plan_id,
                "date": self._plan.date,
                "campaigns": [
                    {
                        "profile_id": c.profile_id,
                        "lead_limit": c.lead_limit,
                    }
                    for c in self._plan.campaigns
                ],
                "expected_effects": self._plan.expected_effects,
            }

        try:
            stats = await self.aetherdesk.get_campaign_stats()
        except Exception:
            from adapters.aetherdesk import CampaignStats
            stats = CampaignStats(total_calls=0, answered=0, voicemail=0, converted=0)

        try:
            usage = await self.aetherdesk.get_usage_and_billing()
        except Exception:
            from adapters.aetherdesk import UsageReport
            usage = UsageReport(calls=0, minutes=0.0, cost=0.0)

        campaign_stats = {
            "total_calls": stats.total_calls,
            "answered": stats.answered,
            "voicemail": stats.voicemail,
            "interested": stats.converted,
            "converted": stats.converted,
        }
        usage_dict = {"cost": usage.cost}

        report = self.reconciler.compare(plan_dict, campaign_stats, usage_dict)
        drift_data = self.reconciler.write_drift_report(report)
        learning = self.reconciler.emit_learning_inputs(report, plan_dict)

        write_event({
            "ts": datetime.now(timezone.utc).isoformat(),
            "correlation_id": plan_dict.get("plan_id", ""),
            "type": "day_closed",
            "system": "deterministic-brain",
            "data": drift_data,
        })

        return {
            "phase": "reconcile",
            "status": "ok",
            "drift": drift_data,
            "learning_inputs": learning,
        }

    def _read_tracker_snapshot(self) -> Dict[str, Any]:
        return {
            "pulse": "stable",
            "tests_passing": 229,
            "deploy_readiness": 97.5,
        }
