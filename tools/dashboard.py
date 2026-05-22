"""dashboard.py — replaces Social-Media-Dashboard as a lean Python telemetry tool.
Exposes /dashboard API endpoints. The UI (ui/index.html) reads from these.
No React, no Next.js, no build step required for the data layer.
"""
from __future__ import annotations
import json
import os
import sqlite3
import time
from contextlib import closing
from typing import Dict, List

DB_PATH = os.environ.get("TRACE_DB", "traces.db")

_DISTRIBUTED = os.environ.get("DISTRIBUTED_MODE", "").lower() in ("1", "true", "yes")

_global_conn: sqlite3.Connection = None
_conn_lock: object = None


def _get_lock():
    global _conn_lock
    if _conn_lock is None:
        import threading
        _conn_lock = threading.Lock()
    return _conn_lock


def _get_conn():
    global _global_conn
    if _global_conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        _global_conn = conn
    return _global_conn


class Dashboard:
    """
    Reads from traces.db (written by tools/tracing.py).
    Provides:
      recent_events(n)    → last n events
      bundle_stats()      → per-bundle success/fail counts
      skill_stats()       → per-skill execution counts + avg score
      audit_feed()        → recent audit pass/fail events
      health()            → uptime, event count, last event
    """

    def recent_events(self, n: int = 50) -> List[Dict]:
        if _DISTRIBUTED:
            try:
                from tools.postgres import get_pg_pool
                pg = get_pg_pool()
                if pg.available:
                    rows = pg.execute(
                        "SELECT ts, event, data FROM pg_traces.events ORDER BY ts DESC LIMIT %s", (n,)
                    )
                    return [{"ts": r[0], "event": r[1], "data": r[2] if isinstance(r[2], dict) else (json.loads(r[2]) if r[2] else {})} for r in rows]
            except Exception:
                pass
        try:
            conn = _get_conn()
            with _get_lock():
                rows = conn.execute(
                    "SELECT ts, event, data FROM events ORDER BY ts DESC LIMIT ?", (n,)
                ).fetchall()
            return [{"ts": r["ts"], "event": r["event"],
                     "data": json.loads(r["data"])} for r in rows]
        except Exception:
            return []

    def events_count(self) -> int:
        if _DISTRIBUTED:
            try:
                from tools.postgres import get_pg_pool
                pg = get_pg_pool()
                if pg.available:
                    rows = pg.execute("SELECT COUNT(*) FROM pg_traces.events")
                    return rows[0][0] if rows else 0
            except Exception:
                pass
        try:
            conn = _get_conn()
            with _get_lock():
                row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
                return row[0] if row else 0
        except Exception:
            return 0

    def bundle_stats(self) -> Dict:
        events = self.recent_events(500)
        stats: Dict[str, Dict] = {}
        for e in events:
            name = e["data"].get("bundle") or e["data"].get("task")
            if not name:
                continue
            s = stats.setdefault(name, {"ok": 0, "failed": 0, "total": 0})
            s["total"] += 1
            if e["data"].get("status") == "ok":
                s["ok"] += 1
            else:
                s["failed"] += 1
        return stats

    def skill_stats(self) -> List[Dict]:
        events = [e for e in self.recent_events(500) if e["event"] == "step"]
        skills: Dict[str, List[float]] = {}
        for e in events:
            skill = e["data"].get("skill", "unknown")
            score = e["data"].get("score", 0)
            skills.setdefault(skill, []).append(float(score))
        return [
            {"skill": k, "runs": len(v),
             "avg_score": round(sum(v) / len(v), 2) if v else 0}
            for k, v in skills.items()
        ]

    def audit_feed(self) -> List[Dict]:
        return [
            e for e in self.recent_events(100)
            if e["event"] in ("audit_repo", "handle", "step")
        ]

    def clear_events(self) -> None:
        """Delete all events from traces.db."""
        if _DISTRIBUTED:
            try:
                from tools.postgres import get_pg_pool
                pg = get_pg_pool()
                if pg.available:
                    pg.execute("DELETE FROM pg_traces.events")
            except Exception:
                pass
        try:
            conn = _get_conn()
            with _get_lock():
                conn.execute("DELETE FROM events")
                conn.commit()
        except Exception:
            pass

    def health(self) -> Dict:
        events = self.recent_events(1)
        try:
            conn = _get_conn()
            with _get_lock():
                count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        except Exception:
            count = 0
        return {
            "status":      "ok",
            "llm":         False,
            "deterministic": True,
            "event_count": count,
            "last_event":  events[0] if events else None,
            "uptime_ts":   time.time(),
        }


_dash = Dashboard()
