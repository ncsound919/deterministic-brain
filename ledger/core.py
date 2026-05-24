from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

BASE_DIR = Path(".acquisition-tracker")

EVENTS_DIR = BASE_DIR / "events"
PLANS_DIR = BASE_DIR / "daily-plans"
CAMPAIGNS_DIR = BASE_DIR / "campaigns"
OVERRIDES_DIR = BASE_DIR / "overrides"

_IDEMPOTENCY_FILE = EVENTS_DIR / "idempotency.json"


def _ensure_dirs() -> None:
    for path in (EVENTS_DIR, PLANS_DIR, CAMPAIGNS_DIR, OVERRIDES_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _to_jsonable(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


# --------- Events --------- #

def write_event(event: Dict[str, Any], day: Optional[date] = None) -> None:
    _ensure_dirs()
    if day is None:
        day = datetime.utcnow().date()
    events_file = EVENTS_DIR / f"{day.isoformat()}-events.jsonl"
    jsonable = {k: _to_jsonable(v) for k, v in event.items()}
    with events_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(jsonable, separators=(",", ":")) + "\n")


def read_events(day: date) -> Iterable[Dict[str, Any]]:
    _ensure_dirs()
    events_file = EVENTS_DIR / f"{day.isoformat()}-events.jsonl"
    if not events_file.exists():
        return []
    with events_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


# --------- Plans --------- #

def write_daily_plan(day: date, plan: Dict[str, Any]) -> None:
    _ensure_dirs()
    plan_file = PLANS_DIR / f"{day.isoformat()}-plan.json"
    jsonable = {k: _to_jsonable(v) for k, v in plan.items()}
    plan_file.write_text(json.dumps(jsonable, indent=2, sort_keys=True), encoding="utf-8")


def read_daily_plan(day: date) -> Optional[Dict[str, Any]]:
    _ensure_dirs()
    plan_file = PLANS_DIR / f"{day.isoformat()}-plan.json"
    if not plan_file.exists():
        return None
    return json.loads(plan_file.read_text(encoding="utf-8"))


# --------- Campaigns --------- #

def write_active_campaigns(data: Dict[str, Any]) -> None:
    _ensure_dirs()
    active_file = CAMPAIGNS_DIR / "active.json"
    active_file.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def read_active_campaigns() -> Dict[str, Any]:
    _ensure_dirs()
    active_file = CAMPAIGNS_DIR / "active.json"
    if not active_file.exists():
        return {}
    return json.loads(active_file.read_text(encoding="utf-8"))


# --------- Idempotency --------- #

def _read_idempotency_map() -> Dict[str, Any]:
    if not _IDEMPOTENCY_FILE.exists():
        return {}
    try:
        return json.loads(_IDEMPOTENCY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_idempotency_map(mapping: Dict[str, Any]) -> None:
    _ensure_dirs()
    _IDEMPOTENCY_FILE.write_text(json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8")


def get_cached_response(idempotency_key: str) -> Optional[Dict[str, Any]]:
    mapping = _read_idempotency_map()
    return mapping.get(idempotency_key)


def mark_response_seen(idempotency_key: str, response: Dict[str, Any]) -> None:
    mapping = _read_idempotency_map()
    mapping[idempotency_key] = response
    _write_idempotency_map(mapping)


# --------- Overrides --------- #

def manual_pause_flag_path() -> Path:
    _ensure_dirs()
    return OVERRIDES_DIR / "manual-pause.flag"


def is_manual_pause_active() -> bool:
    return manual_pause_flag_path().exists()
