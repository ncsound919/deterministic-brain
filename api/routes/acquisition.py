"""Acquisition Tracker - REST API Routes"""
from __future__ import annotations
from fastapi import APIRouter
from typing import Dict, Any, Optional
from pydantic import BaseModel
from pathlib import Path

router = APIRouter(prefix="/api/acquisition", tags=["acquisition"])

_bridge = None

def _get_bridge():
    global _bridge
    if _bridge is None:
        from acquisition_bridge import AcquisitionBridge
        _bridge = AcquisitionBridge()
    return _bridge


class DailyLogRequest(BaseModel):
    brain_state: str = "unknown"
    tasks_executed: int = 0
    trends_detected: int = 0
    portfolio_pulse: str = "stable"


class ProgressRequest(BaseModel):
    assets: Dict[str, Dict[str, Any]]


class InsightRequest(BaseModel):
    signal_type: str
    signal: str
    implication: str
    action: str


class MetricsRequest(BaseModel):
    scores: Dict[str, float]


@router.get("/status")
def get_status() -> Dict:
    bridge = _get_bridge()
    return bridge.get_status()


@router.get("/daily-log")
def get_daily_log() -> Dict:
    bridge = _get_bridge()
    log_file = bridge.tracker_dir / "DAILY-LOG.md"
    content = bridge._safe_read(log_file)
    return {"content": content}


@router.post("/daily-log")
def post_daily_log(req: DailyLogRequest) -> Dict:
    bridge = _get_bridge()
    data = {
        "brain_state": req.brain_state,
        "tasks_executed": req.tasks_executed,
        "trends_detected": req.trends_detected,
        "portfolio_pulse": req.portfolio_pulse,
    }
    bridge.log_autonomous_session(data)
    return {"status": "ok"}


@router.get("/progress")
def get_progress() -> Dict:
    bridge = _get_bridge()
    progress_file = bridge.tracker_dir / "PROGRESS.md"
    content = bridge._safe_read(progress_file)
    return {"content": content}


@router.post("/progress")
def post_progress(req: ProgressRequest) -> Dict:
    bridge = _get_bridge()
    bridge.update_portfolio_progress(dict(req.assets))
    return {"status": "ok"}


@router.get("/insights")
def get_insights() -> Dict:
    bridge = _get_bridge()
    insights_file = bridge.tracker_dir / "INSIGHTS.md"
    content = bridge._safe_read(insights_file)
    return {"content": content}


@router.post("/insights")
def post_insight(req: InsightRequest) -> Dict:
    bridge = _get_bridge()
    bridge.record_insight(req.signal_type, req.signal, req.implication, req.action)
    return {"status": "ok"}


@router.get("/metrics")
def get_metrics() -> Dict:
    bridge = _get_bridge()
    metrics_file = bridge.tracker_dir / "METRICS.md"
    content = bridge._safe_read(metrics_file)
    return {"content": content}


@router.post("/metrics")
def post_metrics(req: MetricsRequest) -> Dict:
    bridge = _get_bridge()
    bridge.refresh_metrics(dict(req.scores))
    return {"status": "ok"}
