"""COO Brain State — core domain models, no I/O."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import hashlib
import time
from contextlib import closing
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

DATA_DIR = Path(os.environ.get("COO_DATA_DIR", Path(__file__).parent.parent / "data"))
DB_PATH = DATA_DIR / "coo_state.db"

PROHIBITED_DIRS = frozenset(["auth", "billing", "legal", "security", "internal"])

DB_SCHEMA_VERSION = "1.0"

logger = logging.getLogger(__name__)


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


class DecisionStore:
    """SQLite-backed persistence for DecisionCards."""

    _instance: Optional["DecisionStore"] = None
    _lock = Lock()

    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self._ensure_schema()

    def _wal_conn(self):
        conn = sqlite3.connect(str(self._db_path), timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @classmethod
    def get_instance(cls) -> "DecisionStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _ensure_schema(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._wal_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS decision_cards (
                event_id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                zone TEXT NOT NULL,
                summary TEXT,
                diagnosis TEXT,
                proposed_fix TEXT,
                code_change TEXT,
                github_issue_number INTEGER,
                github_pr_number INTEGER,
                created_ts REAL NOT NULL,
                resolved_ts REAL,
                outcome TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                ts REAL NOT NULL,
                FOREIGN KEY (event_id) REFERENCES decision_cards(event_id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_zone ON decision_cards(product_id, zone)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_resolved ON decision_cards(resolved_ts)
        """)
        conn.commit()
        conn.close()

    def save_card(self, card: DecisionCard) -> None:
        with closing(self._wal_conn()) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO decision_cards
                (event_id, product_id, zone, summary, diagnosis, proposed_fix,
                 code_change, github_issue_number, github_pr_number,
                 created_ts, resolved_ts, outcome)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                card.event_id, card.product_id, card.zone.value, card.summary,
                card.diagnosis, card.proposed_fix, card.code_change,
                card.github_issue_number, card.github_pr_number,
                card.created_ts, card.resolved_ts, card.outcome,
            ))
            conn.commit()

    def load_card(self, event_id: str) -> Optional[DecisionCard]:
        with closing(self._wal_conn()) as conn:
            row = conn.execute(
                "SELECT * FROM decision_cards WHERE event_id = ?", (event_id,)
            ).fetchone()
        if row is None:
            return None
        return DecisionCard(
            event_id=row[0], product_id=row[1], zone=TrafficLightZone(row[2]),
            summary=row[3], diagnosis=row[4], proposed_fix=row[5],
            code_change=row[6], github_issue_number=row[7], github_pr_number=row[8],
            created_ts=row[9], resolved_ts=row[10], outcome=row[11],
        )

    def load_pending(self) -> List[DecisionCard]:
        with closing(self._wal_conn()) as conn:
            rows = conn.execute(
                "SELECT * FROM decision_cards WHERE resolved_ts IS NULL ORDER BY created_ts"
            ).fetchall()
        return [
            DecisionCard(
                event_id=row[0], product_id=row[1], zone=TrafficLightZone(row[2]),
                summary=row[3], diagnosis=row[4], proposed_fix=row[5],
                code_change=row[6], github_issue_number=row[7], github_pr_number=row[8],
                created_ts=row[9], resolved_ts=row[10], outcome=row[11],
            )
            for row in rows
        ]

    def load_log(self, limit: int = 100) -> List[DecisionCard]:
        with closing(self._wal_conn()) as conn:
            rows = conn.execute(
                "SELECT * FROM decision_cards ORDER BY created_ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            DecisionCard(
                event_id=row[0], product_id=row[1], zone=TrafficLightZone(row[2]),
                summary=row[3], diagnosis=row[4], proposed_fix=row[5],
                code_change=row[6], github_issue_number=row[7], github_pr_number=row[8],
                created_ts=row[9], resolved_ts=row[10], outcome=row[11],
            )
            for row in rows
        ]

    def log_execution(self, event_id: str, action: str, status: str, result: str) -> None:
        with closing(self._wal_conn()) as conn:
            conn.execute("""
                INSERT INTO execution_log (event_id, action, status, result, ts)
                VALUES (?, ?, ?, ?, ?)
            """, (event_id, action, status, result, time.time()))
            conn.commit()

    def get_execution_log(self, event_id: str) -> List[Dict[str, Any]]:
        with closing(self._wal_conn()) as conn:
            rows = conn.execute(
                "SELECT action, status, result, ts FROM execution_log WHERE event_id = ? ORDER BY ts",
                (event_id,)
            ).fetchall()
        return [{"action": r[0], "status": r[1], "result": r[2], "ts": r[3]} for r in rows]


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