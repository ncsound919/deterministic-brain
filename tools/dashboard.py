"""dashboard.py — replaces Social-Media-Dashboard as a lean Python telemetry tool.
Exposes /dashboard API endpoints. The UI (ui/index.html) reads from these.
No React, no Next.js, no build step required for the data layer.
"""
from __future__ import annotations
import json
import os
import sqlite3
import time
from typing import Dict, List

DB_PATH = os.environ.get("TRACE_DB", "traces.db")


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

    def _conn(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def recent_events(self, n: int = 50) -> List[Dict]:
        try:
            conn = self._conn()
            rows = conn.execute(
                "SELECT ts, event, data FROM events ORDER BY ts DESC LIMIT ?", (n,)
            ).fetchall()
            conn.close()
            return [{"ts": r["ts"], "event": r["event"],
                     "data": json.loads(r["data"])} for r in rows]
        except Exception:
            return []

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

    def health(self) -> Dict:
        events = self.recent_events(1)
        try:
            conn  = self._conn()
            count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            conn.close()
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
