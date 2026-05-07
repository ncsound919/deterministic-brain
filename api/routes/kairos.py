"""KAIROS routes — daemon start/stop/status, daily logs, stats."""
from __future__ import annotations
from fastapi import APIRouter
from typing import Dict

from orchestration.kairos_daemon import (
    get_daemon, start_kairos, stop_kairos,
    kairos_status as _kairos_status,
)

router = APIRouter(prefix="/kairos", tags=["kairos"])


@router.post("/start")
def start() -> Dict:
    return start_kairos()


@router.post("/stop")
def stop() -> Dict:
    return stop_kairos()


@router.get("/status")
def status() -> Dict:
    return _kairos_status()


@router.get("/today")
def today() -> Dict:
    from features.kairos import get_today
    return get_today()


@router.get("/{date}")
def date_entry(date: str) -> Dict:
    from features.kairos import get_date
    return get_date(date)


@router.get("/stats")
def stats() -> Dict:
    from features.kairos import get_stats
    return get_stats()
