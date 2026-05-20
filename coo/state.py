"""COO Brain State — core domain models, no I/O."""
from __future__ import annotations

import os
import time
import json
import sqlite3
import hashlib
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from threading import Lock

DATA_DIR = Path(os.environ.get("COO_DATA_DIR", Path(__file__).parent.parent / "data"))
DB_PATH = DATA_DIR / "coo_state.db"

PROHIBITED_DIRS = frozenset(["auth", "billing", "legal", "security", "internal"])

DB_SCHEMA_VERSION = "1.0"


class TrafficLightZone(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"

    @property
    def autoaction(self) -> bool:
        return self == TrafficLightZone.GREEN

    @property
    def human_required(self) -> bool:
        return self in (TrafficLightZone.YELLOW, TrafficLightZone.RED)

    @property
    def requires_immediate(self) -> bool:
        return self == TrafficLightZone.RED

    @classmethod
    def from_event(cls, event_type: str, severity: float) -> "TrafficLightZone":
        event_type = event_type.lower()

        red_events = {
            "security_alert",
            "data_exfiltration",
            "database_connection_loss",
            "stripe_charge_failed",
            "prompt_injection",
            "pii_exposure",
        }
        yellow_events = {
            "exception",
            "build_failure",
            "dependency_vulnerability",
            "stripe_payment_failed",
            "high_exception_spike",
            "ci_failure",
            "deploy_failure",
        }
        green_events = {
            "cache_clear",
            "dependency_update",
            "server_restart",
            "lint_fix",
            "typo_fix",
            "read_only_check",
        }

        if event_type in red_events or severity > 0.7:
            return cls.RED
        if event_type in yellow_events or severity > 0.2:
            return cls.YELLOW
        return cls.GREEN


@dataclass
class ProductConfig:
    product_id: str
    tier: int
    name: str
    github_owner: str = "ncsound919"
    github_repo: str = ""
    stripe_price_ids: List[str] = field(default_factory=list)
    sentry_dsn: str = ""
    deploy_env: str = "staging"
    is_active: bool = True
    base_priority: int = 50

    def __post_init__(self):
        if not self.github_repo:
            self.github_repo = self.product_id


@dataclass
class HealthVector:
    healthy: bool = True
    error_rate: float = 0.0
    last_deploy_ts: float = 0.0
    build_status: str = "unknown"
    uptime_pct: float = 100.0


@dataclass
class EconomicVector:
    mrr: float = 0.0
    churn_rate: float = 0.0
    active_customers: int = 0
    daily_runrate: float = 0.0


@dataclass
class MomentumVector:
    open_bugs: int = 0
    pending_prs: int = 0
    deployment_status: str = "unknown"
    commit_frequency: float = 0.0


@dataclass
class CommitmentVector:
    target_metric: str = ""
    current_value: float = 0.0
    deadline: float = 0.0


@dataclass
class PortfolioState:
    products: Dict[str, ProductConfig] = field(default_factory=dict)
    health: Dict[str, HealthVector] = field(default_factory=dict)
    economics: Dict[str, EconomicVector] = field(default_factory=dict)
    momentum: Dict[str, MomentumVector] = field(default_factory=dict)
    version: str = DB_SCHEMA_VERSION

    def register_product(self, config: ProductConfig) -> None:
        self.products[config.product_id] = config
        if config.product_id not in self.health:
            self.health[config.product_id] = HealthVector()
        if config.product_id not in self.economics:
            self.economics[config.product_id] = EconomicVector()
        if config.product_id not in self.momentum:
            self.momentum[config.product_id] = MomentumVector()

    def get_health_vector(self, product_id: str) -> HealthVector:
        if product_id not in self.health:
            raise KeyError(f"Unknown product: {product_id}")
        return self.health[product_id]

    def get_economic_vector(self, product_id: str) -> EconomicVector:
        if product_id not in self.economics:
            raise KeyError(f"Unknown product: {product_id}")
        return self.economics[product_id]

    def get_momentum_vector(self, product_id: str) -> MomentumVector:
        if product_id not in self.momentum:
            raise KeyError(f"Unknown product: {product_id}")
        return self.momentum[product_id]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "products": {k: asdict(v) for k, v in self.products.items()},
            "health": {k: asdict(v) for k, v in self.health.items()},
            "economics": {k: asdict(v) for k, v in self.economics.items()},
            "momentum": {k: asdict(v) for k, v in self.momentum.items()},
            "version": self.version,
        }


@dataclass
class TelemetryEvent:
    product_id: str
    event_type: str
    raw_data: Dict[str, Any]
    zone: TrafficLightZone = TrafficLightZone.YELLOW
    severity: float = 0.0
    ts: float = field(default_factory=time.time)
    event_id: str = ""
    resolved: bool = False

    def __post_init__(self):
        if not self.event_id:
            raw = f"{self.product_id}:{self.event_type}:{self.ts}"
            self.event_id = hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class DecisionCard:
    event_id: str
    product_id: str
    zone: TrafficLightZone
    summary: str
    diagnosis: str
    proposed_fix: str
    code_change: Optional[str] = None
    github_issue_number: Optional[int] = None
    github_pr_number: Optional[int] = None
    created_ts: float = field(default_factory=time.time)
    resolved_ts: Optional[float] = None
    outcome: Optional[str] = None  # "approved", "rejected", "escalated", "expired"

    @property
    def resolved(self) -> bool:
        return self.resolved_ts is not None

    def is_approved(self, closed: bool = False, outcome: str = "") -> bool:
        if not closed:
            return False
        return outcome in ("approved", "merged")


class Constitution:
    """Immutable operational boundaries for the COO Brain."""

    PROHIBITED_DIRS = frozenset(["auth", "billing", "legal", "security", "internal"])
    NEVER_AUTONOMOUS = frozenset(["spend_money", "refund", "fire", "hire", "legal_communication"])
    CONDITIONAL_AUTONOMOUS = frozenset(["scripted_customer_email", "merge_pr", "database_write"])

    def check_path(self, file_path: str) -> bool:
        path_lower = file_path.lower()
        for prohibited in self.PROHIBITED_DIRS:
            if prohibited in path_lower or ".." in path_lower:
                return False
        return True

    def check_action(self, action: str, params: Optional[Dict[str, Any]] = None) -> bool:
        params = params or {}
        if action in self.NEVER_AUTONOMOUS:
            return False
        if action == "merge_pr":
            files = params.get("files", [])
            target = params.get("target", "")
            if target == "main":
                for f in files:
                    if not self.check_path(f):
                        return False
            return True
        if action == "scripted_customer_email":
            return bool(params.get("template_id"))
        if action == "spend_money":
            return False
        return True

    def get_summary(self) -> Dict[str, Any]:
        return {
            "prohibited_dirs": sorted(self.PROHIBITED_DIRS),
            "never_autonomous": sorted(self.NEVER_AUTONOMOUS),
            "conditional_autonomy": sorted(self.CONDITIONAL_AUTONOMOUS),
            "version": "1.0",
        }