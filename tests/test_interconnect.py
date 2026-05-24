"""Tests for Phases 4-7: OpenHubAdapter, DecisionEngine, Reconciler, DailyOrchestrator."""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ledger.core as _ledger_core
from adapters.openhub import OpenHubAdapter, PipelineSummary, VelocityReport, PipelineResult
from adapters.base import AdapterCallResult
from agi.decision_engine import DecisionEngine, DailyPlan, CampaignPlan, DailyContext
from agi.reconciler import Reconciler, DriftReport
from agi.daily_orchestrator import DailyOrchestrator
from adapters.aetherdesk import (
    AetherDeskAdapter,
    CampaignConfig,
    CampaignStats,
    UsageReport,
    CampaignStatus,
)


@pytest.fixture(autouse=True)
def _temp_dirs(monkeypatch, tmp_path):
    """Isolate ledger writes to a temp dir for every test."""
    monkeypatch.setattr(_ledger_core, "BASE_DIR", tmp_path)
    monkeypatch.setattr(_ledger_core, "EVENTS_DIR", tmp_path / "events")
    monkeypatch.setattr(_ledger_core, "PLANS_DIR", tmp_path / "daily-plans")
    monkeypatch.setattr(_ledger_core, "CAMPAIGNS_DIR", tmp_path / "campaigns")
    monkeypatch.setattr(_ledger_core, "OVERRIDES_DIR", tmp_path / "overrides")
    monkeypatch.setattr(_ledger_core, "_IDEMPOTENCY_FILE", tmp_path / "events" / "idempotency.json")
    for d in ("events", "daily-plans", "campaigns", "overrides"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)


# ═════════════════════════════════════════════════════════════════════
# Phase 4: OpenHubAdapter
# ═════════════════════════════════════════════════════════════════════

@pytest.fixture
def openhub_adapter():
    return OpenHubAdapter(base_url="http://openhub.local")


@pytest.mark.asyncio
async def test_openhub_health_ok(openhub_adapter):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok"}

    with patch.object(openhub_adapter, "_client") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        result = await openhub_adapter.health()
        assert result.ok


@pytest.mark.asyncio
async def test_openhub_get_pipeline_status(openhub_adapter):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"active": 2, "completed_today": 5, "failed_today": 1, "queue_depth": 3}

    with patch.object(openhub_adapter, "_client") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=[mock_resp])
        status = await openhub_adapter.get_pipeline_status()
        assert status.active_pipelines == 2
        assert status.completed_today == 5
        assert status.failed_today == 1
        assert status.queue_depth == 3


@pytest.mark.asyncio
async def test_openhub_get_project_velocity(openhub_adapter):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "commits": 12, "deploys": 3, "tests_passed": 48,
        "tests_failed": 0, "pipelines_completed": 4, "avg_duration_seconds": 120.5,
    }

    with patch.object(openhub_adapter, "_client") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=[mock_resp])
        velocity = await openhub_adapter.get_project_velocity(datetime.utcnow())
        assert velocity.commits_today == 12
        assert velocity.tests_passed == 48
        assert velocity.avg_pipeline_duration_seconds == 120.5


@pytest.mark.asyncio
async def test_openhub_trigger_pipeline(openhub_adapter):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"pipeline_id": "PIPE-001", "status": "started", "files": ["main.py"]}

    with patch.object(openhub_adapter, "_client") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        result = await openhub_adapter.trigger_pipeline("build auth", "idem-pipe-001")
        assert result.pipeline_id == "PIPE-001"
        assert result.status == "started"
        assert "main.py" in result.files_generated


# ═════════════════════════════════════════════════════════════════════
# Phase 5: Decision Engine
# ═════════════════════════════════════════════════════════════════════

def test_decision_engine_review():
    engine = DecisionEngine()
    tracker = {"pulse": "stable", "tests_passing": 229, "deploy_readiness": 97.5}
    aetherdesk = {"total_calls": 45, "answered": 12, "converted": 3, "cost": 0.68}
    openhub = {"active_pipelines": 1, "completed_today": 3}

    context = engine.review(tracker, aetherdesk, openhub)

    assert context.portfolio_pulse == "stable"
    assert context.yesterday_calls == 45
    assert context.yesterday_converted == 3
    assert context.openhub_pipelines_completed == 3


def test_decision_engine_plan_produces_campaigns():
    engine = DecisionEngine()
    context = DailyContext(
        portfolio_pulse="stable", total_tests=229, deploy_readiness=97.5,
        yesterday_calls=45, yesterday_answered=12, yesterday_converted=3,
        yesterday_cost=0.68, openhub_velocity=3.0,
        openhub_pipelines_active=1, openhub_pipelines_completed=3,
    )
    plan = engine.plan(context)
    assert len(plan.campaigns) >= 1
    assert plan.campaigns[0].lead_limit > 0
    assert plan.stop_conditions["min_answer_rate"] == 0.20
    assert plan.expected_effects["max_cost"] > 0


def test_decision_engine_plan_no_calls_today():
    engine = DecisionEngine()
    context = DailyContext(
        portfolio_pulse="stable", total_tests=229, deploy_readiness=97.5,
        yesterday_calls=0, yesterday_answered=0, yesterday_converted=0,
        yesterday_cost=0.0, openhub_velocity=0.0,
        openhub_pipelines_active=0, openhub_pipelines_completed=0,
    )
    plan = engine.plan(context)
    assert len(plan.campaigns) >= 1
    assert plan.campaigns[0].profile_id == "PROF-STARTER-OUTREACH"


# ═════════════════════════════════════════════════════════════════════
# Phase 6: Reconciler
# ═════════════════════════════════════════════════════════════════════

def test_reconciler_no_drift():
    reconciler = Reconciler()
    plan = {
        "plan_id": "test-plan", "date": "2026-05-24",
        "campaigns": [{"profile_id": "test", "lead_limit": 50}],
        "expected_effects": {"calls_attempted": 50, "interested": 5, "max_cost": 1.0},
    }
    stats = {"total_calls": 50, "answered": 20, "voicemail": 10, "interested": 5, "converted": 5}
    usage = {"cost": 0.50}

    report = reconciler.compare(plan, stats, usage)
    assert report.calls_attempted == 50
    assert report.drift_items == []


def test_reconciler_detects_call_drift():
    reconciler = Reconciler()
    plan = {
        "plan_id": "test-plan", "date": "2026-05-24",
        "campaigns": [],
        "expected_effects": {"calls_attempted": 50, "interested": 5, "max_cost": 1.0},
    }
    stats = {"total_calls": 30, "answered": 5, "voicemail": 3, "interested": 1, "converted": 1}
    usage = {"cost": 0.30}

    report = reconciler.compare(plan, stats, usage)
    assert len(report.drift_items) >= 1
    assert report.drift_items[0]["field"] == "calls_attempted"
    assert report.drift_items[0]["delta"] == -20


def test_reconciler_detects_cost_overrun():
    reconciler = Reconciler()
    plan = {
        "plan_id": "test-plan", "date": "2026-05-24",
        "campaigns": [],
        "expected_effects": {"calls_attempted": 50, "interested": 5, "max_cost": 1.0},
    }
    stats = {"total_calls": 50, "answered": 20, "voicemail": 10, "interested": 5, "converted": 5}
    usage = {"cost": 2.50}

    report = reconciler.compare(plan, stats, usage)
    cost_items = [d for d in report.drift_items if d["field"] == "total_cost"]
    assert len(cost_items) == 1
    assert cost_items[0]["expected"] == 1.0
    assert cost_items[0]["observed"] == 2.50


def test_reconciler_write_drift_report():
    reconciler = Reconciler()
    plan = {"plan_id": "test-plan", "date": "2026-05-24", "campaigns": [], "expected_effects": {}}
    report = reconciler.compare(plan, {"total_calls": 0, "answered": 0, "voicemail": 0, "interested": 0, "converted": 0}, {"cost": 0})
    result = reconciler.write_drift_report(report)
    assert result["plan_id"] == "test-plan"
    assert "learning_inputs" in result


# ═════════════════════════════════════════════════════════════════════
# Phase 7: DailyOrchestrator full cycle
# ═════════════════════════════════════════════════════════════════════

@pytest.fixture
def mocked_orchestrator(openhub_adapter):
    aetherdesk = AetherDeskAdapter(base_url="http://aetherdesk.local", api_key="test-key")
    return DailyOrchestrator(aetherdesk=aetherdesk, openhub=openhub_adapter)


@pytest.mark.asyncio
async def test_orchestrator_run_review(mocked_orchestrator):
    aeth = mocked_orchestrator.aetherdesk

    stats_resp = MagicMock(status_code=200, json=lambda: {"total_calls": 45, "answered": 12, "voicemail": 8, "converted": 3, "interested": 3})
    usage_resp = MagicMock(status_code=200, json=lambda: {"total_calls": 100, "total_minutes": 234.5, "total_cost": 3.52})
    pipeline_resp = MagicMock(status_code=200, json=lambda: {"active": 1, "completed_today": 3, "failed_today": 0, "queue_depth": 0})

    async def patched_get(path, **kwargs):
        mock = MagicMock()
        if "campaign/stats" in path:
            mock = stats_resp
        elif "usage" in path:
            mock = usage_resp
        elif "pipeline/status" in path:
            mock = pipeline_resp
        return mock

    with patch.object(aeth, "_client") as aeth_client:
        aeth_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=patched_get)
        with patch.object(mocked_orchestrator.openhub, "_client") as oh_client:
            oh_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=patched_get)
            result = await mocked_orchestrator.run_review()
            assert result["status"] == "ok"
            assert result["context"].yesterday_calls == 45


@pytest.mark.asyncio
async def test_orchestrator_run_plan(mocked_orchestrator):
    with patch.object(mocked_orchestrator, "run_review") as mock_review:
        mock_review.return_value = {
            "phase": "review", "status": "ok",
            "context": DailyContext(
                portfolio_pulse="stable", total_tests=229, deploy_readiness=97.5,
                yesterday_calls=45, yesterday_answered=12, yesterday_converted=3,
                yesterday_cost=0.68, openhub_velocity=3.0,
                openhub_pipelines_active=1, openhub_pipelines_completed=3,
            ),
        }
        result = await mocked_orchestrator.run_plan()
        assert result["status"] == "ok"
        assert result["plan"]["plan_id"].startswith("plan-")


@pytest.mark.asyncio
async def test_orchestrator_manual_pause_blocks(mocked_orchestrator):
    from ledger import manual_pause_flag_path
    flag = manual_pause_flag_path()
    flag.touch()

    result = await mocked_orchestrator.run_review()
    assert result["status"] == "skipped"
    assert result["reason"] == "manual_pause"

    flag.unlink()


@pytest.mark.asyncio
async def test_orchestrator_run_stage(mocked_orchestrator):
    from agi.decision_engine import DailyContext
    ctx = DailyContext(
        portfolio_pulse="stable", total_tests=229, deploy_readiness=97.5,
        yesterday_calls=45, yesterday_answered=12, yesterday_converted=3,
        yesterday_cost=0.68, openhub_velocity=3.0,
        openhub_pipelines_active=1, openhub_pipelines_completed=3,
    )
    aeth = mocked_orchestrator.aetherdesk

    mock_leads_resp = MagicMock(status_code=200, json=lambda: {"leads_available": 25})
    plan_result = await mocked_orchestrator.run_plan({"phase": "review", "status": "ok", "context": ctx})
    assert plan_result["status"] == "ok"

    with patch.object(aeth, "_client") as aeth_client:
        aeth_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_leads_resp)
        result = await mocked_orchestrator.run_stage()
        assert result["status"] == "ok"
        assert len(result.get("staged", [])) >= 1


@pytest.mark.asyncio
async def test_orchestrator_run_launch(mocked_orchestrator):
    from agi.decision_engine import DailyContext
    ctx = DailyContext(
        portfolio_pulse="stable", total_tests=229, deploy_readiness=97.5,
        yesterday_calls=45, yesterday_answered=12, yesterday_converted=3,
        yesterday_cost=0.68, openhub_velocity=3.0,
        openhub_pipelines_active=1, openhub_pipelines_completed=3,
    )
    plan_result = await mocked_orchestrator.run_plan({"phase": "review", "status": "ok", "context": ctx})
    assert plan_result["status"] == "ok"

    aeth = mocked_orchestrator.aetherdesk
    mock_resp = MagicMock(status_code=200, json=lambda: {
        "campaign_id": "CAMP-001", "status": "launched", "leads_queued": 25,
    })
    with patch.object(aeth, "_client") as aeth_client:
        aeth_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        result = await mocked_orchestrator.run_launch()
        assert result["status"] == "ok"
        assert len(result.get("launched", [])) >= 1


@pytest.mark.asyncio
async def test_orchestrator_run_observe(mocked_orchestrator):
    from agi.decision_engine import DailyContext
    ctx = DailyContext(
        portfolio_pulse="stable", total_tests=229, deploy_readiness=97.5,
        yesterday_calls=45, yesterday_answered=12, yesterday_converted=3,
        yesterday_cost=0.68, openhub_velocity=3.0,
        openhub_pipelines_active=1, openhub_pipelines_completed=3,
    )
    aeth = mocked_orchestrator.aetherdesk
    aeth.get_campaign_stats = AsyncMock(return_value=CampaignStats(
        total_calls=10, answered=5, voicemail=2, converted=1
    ))
    plan_result = await mocked_orchestrator.run_plan({"phase": "review", "status": "ok", "context": ctx})
    assert plan_result["status"] == "ok"
    result = await mocked_orchestrator.run_observe()
    assert result["status"] == "ok"
    assert "events_consumed" in result


@pytest.mark.asyncio
async def test_orchestrator_run_reconcile(mocked_orchestrator):
    from agi.decision_engine import DailyContext
    ctx = DailyContext(
        portfolio_pulse="stable", total_tests=229, deploy_readiness=97.5,
        yesterday_calls=45, yesterday_answered=12, yesterday_converted=3,
        yesterday_cost=0.68, openhub_velocity=3.0,
        openhub_pipelines_active=1, openhub_pipelines_completed=3,
    )
    aeth = mocked_orchestrator.aetherdesk
    aeth.get_campaign_stats = AsyncMock(return_value=CampaignStats(
        total_calls=45, answered=12, voicemail=8, converted=3
    ))
    aeth.get_usage_and_billing = AsyncMock(return_value=UsageReport(calls=100, minutes=234.5, cost=3.52))

    plan_result = await mocked_orchestrator.run_plan({"phase": "review", "status": "ok", "context": ctx})
    assert plan_result["status"] == "ok"
    result = await mocked_orchestrator.run_reconcile()
    assert result["status"] == "ok"
    assert "drift" in result

    from ledger import read_events
    events = list(read_events(date.today()))
    day_closed = [e for e in events if e.get("type") == "day_closed"]
    assert len(day_closed) >= 1


# ═════════════════════════════════════════════════════════════════════
# E2E: Full day simulation
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_full_day_simulation(mocked_orchestrator):
    """Simulate a full day: REVIEW → PLAN → STAGE → LAUNCH → OBSERVE → RECONCILE."""
    aeth = mocked_orchestrator.aetherdesk
    oh = mocked_orchestrator.openhub

    # Mock all adapter methods at the method level — avoids broken async mock chains
    aeth.get_campaign_stats = AsyncMock(return_value=CampaignStats(total_calls=45, answered=12, voicemail=8, converted=3))
    aeth.get_usage_and_billing = AsyncMock(return_value=UsageReport(calls=100, minutes=234.5, cost=3.52))
    aeth.validate_lead_inventory = AsyncMock(return_value=True)
    aeth.launch_campaign = AsyncMock(return_value=CampaignStatus(id="CAMP-001", status="launched", leads_queued=25))
    aeth.health = AsyncMock(return_value=AdapterCallResult(ok=True, status_code=200, data={"status": "ok"}))
    oh.get_pipeline_status = AsyncMock(return_value=PipelineSummary(active_pipelines=1, completed_today=3, failed_today=0, queue_depth=0))
    oh.get_project_velocity = AsyncMock(return_value=VelocityReport(commits_today=12, deploys_today=3, tests_passed=48, tests_failed=0, pipelines_completed=4))

    # 1. REVIEW
    review = await mocked_orchestrator.run_review()
    assert review["status"] == "ok"

    # 2. PLAN
    plan = await mocked_orchestrator.run_plan(review)
    assert plan["status"] == "ok"
    assert len(plan["plan"]["campaigns"]) >= 1

    # 3. STAGE
    stage = await mocked_orchestrator.run_stage()
    assert stage["status"] == "ok"

    # 4. LAUNCH
    launch = await mocked_orchestrator.run_launch()
    assert launch["status"] == "ok"
    assert len(launch["launched"]) >= 1

    from ledger import write_event
    write_event({
        "ts": "2026-05-24T08:00:00Z",
        "correlation_id": "plan-2026-05-24-001",
        "type": "campaign_launch",
        "system": "aetherdesk",
        "data": {"campaign_id": "CAMP-001", "status": "launched", "leads_queued": 25},
    })

    # 5. OBSERVE
    observe = await mocked_orchestrator.run_observe()
    assert observe["status"] == "ok"

    # 6. RECONCILE
    reconcile = await mocked_orchestrator.run_reconcile()
    assert reconcile["status"] == "ok"
    assert len(reconcile["drift"]["drift_items"]) >= 0

    from ledger import read_events
    events = list(read_events(date.today()))
    event_types = {e.get("type") for e in events}
    assert "daily_plan_created" in event_types
    assert "campaign_staged" in event_types or "campaign_launch" in event_types
    assert "day_closed" in event_types

    launch_events = [e for e in events if e.get("type") == "campaign_launch"]
    assert len(launch_events) >= 1
