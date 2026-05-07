"""Runtime healer — watchdog, circuit breaker, retry logic for production.

Monitors daemon health, skill failures, and applies circuit-breaking
with automatic recovery. Subscribes to event_bus for real-time healing.
"""

from __future__ import annotations
import time
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set


@dataclass
class SkillHealth:
    skill_id: str
    failures_window: List[float] = field(default_factory=list)
    last_failure_ts: float = 0.0
    last_success_ts: float = 0.0
    state: str = "closed"  # closed, open, half_open
    opened_at: float = 0.0
    failure_count: int = 0
    success_count: int = 0


class RuntimeHealer:
    """Production watchdog with circuit breaker, retry, and daemon recovery."""

    def __init__(self, heal_log: str = ".heal_runtime_log.json"):
        self._skills: Dict[str, SkillHealth] = {}
        self._lock = threading.Lock()
        self._daemon_watches: Dict[str, Dict] = {}
        self._heal_log = Path(heal_log)
        self._heal_events: List[Dict] = []
        self.circuit_window_s = 600  # 10 minutes
        self.circuit_threshold = 5   # failures before opening
        self.circuit_cooldown_s = 300  # 5 minutes
        self.max_restarts = 3

    # ── Circuit Breaker ──────────────────────────────────────────

    def _get_health(self, skill_id: str) -> SkillHealth:
        with self._lock:
            if skill_id not in self._skills:
                self._skills[skill_id] = SkillHealth(skill_id=skill_id)
            return self._skills[skill_id]

    def record_success(self, skill_id: str) -> None:
        h = self._get_health(skill_id)
        with self._lock:
            now = time.time()
            h.success_count += 1
            h.last_success_ts = now
            # Half-open → closed on success
            if h.state == "half_open":
                h.state = "closed"
                h.failure_count = 0
                h.failures_window.clear()
                self._log("circuit_closed", skill_id=skill_id)

    def record_failure(self, skill_id: str) -> None:
        h = self._get_health(skill_id)
        with self._lock:
            now = time.time()
            h.failure_count += 1
            h.last_failure_ts = now
            # Trim old failures outside window
            cutoff = now - self.circuit_window_s
            h.failures_window = [t for t in h.failures_window if t > cutoff]
            h.failures_window.append(now)

            # Check threshold
            if h.state == "closed" and len(h.failures_window) >= self.circuit_threshold:
                h.state = "open"
                h.opened_at = now
                self._log("circuit_opened", skill_id=skill_id,
                          failures=len(h.failures_window))
            elif h.state == "half_open":
                h.state = "open"
                h.opened_at = now
                self._log("circuit_reopened", skill_id=skill_id)

    def is_circuit_open(self, skill_id: str) -> bool:
        h = self._get_health(skill_id)
        with self._lock:
            if h.state == "open":
                if time.time() - h.opened_at >= self.circuit_cooldown_s:
                    h.state = "half_open"
                    self._log("circuit_half_open", skill_id=skill_id)
                    return False
                return True
            return False

    def circuit_breaker_state(self, skill_id: str) -> Dict:
        h = self._get_health(skill_id)
        with self._lock:
            open_remaining = 0
            if h.state == "open":
                open_remaining = self.circuit_cooldown_s - (time.time() - h.opened_at)
            return {
                "skill_id": skill_id,
                "state": h.state,
                "failure_count": h.failure_count,
                "success_count": h.success_count,
                "recent_failures": len(h.failures_window),
                "cooldown_remaining_s": max(0, round(open_remaining)),
            }

    def all_circuit_states(self) -> List[Dict]:
        return [self.circuit_breaker_state(s) for s in list(self._skills.keys())]

    # ── Retry Logic ─────────────────────────────────────────────

    def execute_with_retry(self, fn: Callable, skill_id: str,
                           max_retries: int = 3, backoff_ms: float = 1000.0) -> Dict:
        """Execute a function with retry and circuit breaker check."""
        if self.is_circuit_open(skill_id):
            return {"status": "circuit_open", "skill_id": skill_id,
                    "message": f"Circuit breaker is open for {skill_id}"}

        last_error = None
        for attempt in range(max_retries):
            try:
                result = fn()
                self.record_success(skill_id)
                return result
            except Exception as e:
                last_error = str(e)
                self.record_failure(skill_id)
                if attempt < max_retries - 1:
                    wait = backoff_ms * (2 ** attempt) / 1000
                    time.sleep(wait)

        return {"status": "failed", "skill_id": skill_id,
                "error": last_error, "attempts": max_retries}

    # ── Daemon Watchdog ──────────────────────────────────────────

    def watch_daemon(self, name: str, start_fn: Callable,
                     is_alive_fn: Callable) -> None:
        """Register a daemon for watchdog monitoring."""
        self._daemon_watches[name] = {
            "start": start_fn, "is_alive": is_alive_fn,
            "restart_count": 0, "last_check": time.time(),
        }
        self._log("daemon_watch_started", daemon=name)

    def check_daemons(self) -> List[Dict]:
        """Check all watched daemons, restart dead ones."""
        results = []
        for name, cfg in self._daemon_watches.items():
            if not cfg["is_alive"]():
                if cfg["restart_count"] < self.max_restarts:
                    try:
                        cfg["start"]()
                        cfg["restart_count"] += 1
                        cfg["last_check"] = time.time()
                        self._log("daemon_restarted", daemon=name,
                                  restart_count=cfg["restart_count"])
                        results.append({"daemon": name, "action": "restarted",
                                        "restart_count": cfg["restart_count"]})
                    except Exception as e:
                        self._log("daemon_restart_failed", daemon=name, error=str(e))
                        results.append({"daemon": name, "action": "failed",
                                        "error": str(e)})
                else:
                    self._log("daemon_max_restarts", daemon=name)
                    results.append({"daemon": name, "action": "max_restarts"})
            else:
                cfg["last_check"] = time.time()
        return results

    # ── Healing from Corrections ─────────────────────────────────

    def heal_from_corrections(self, corrections_file: str = ".autodream_corrections.jsonl") -> int:
        """Process autodream corrections — deprecate hopeless skills."""
        path = Path(corrections_file)
        if not path.exists():
            return 0

        count = 0
        lines = path.read_text().strip().split("\n")
        from collections import Counter
        failed = Counter()
        for line in lines:
            try:
                entry = json.loads(line)
                skill = entry.get("failed_skill", "")
                if skill:
                    failed[skill] += 1
            except json.JSONDecodeError:
                continue

        for skill, fails in failed.items():
            if fails >= 10:
                # Too many corrections — deprecate
                self._log("skill_deprecated", skill_id=skill, failures=fails)
                count += 1
                # Record many failures so circuit breaker opens
                for _ in range(min(fails, self.circuit_threshold + 1)):
                    self.record_failure(skill)

        return count

    # ── Logging ──────────────────────────────────────────────────

    def _log(self, event: str, **data):
        entry = {"ts": time.time(), "event": event, "data": data}
        self._heal_events.append(entry)
        if len(self._heal_events) > 500:
            self._heal_events = self._heal_events[-250:]
        # Persist periodically
        if len(self._heal_events) % 10 == 0:
            self._persist_log()

    def _persist_log(self):
        try:
            self._heal_log.parent.mkdir(parents=True, exist_ok=True)
            self._heal_log.write_text(json.dumps(self._heal_events[-200:], indent=2))
        except IOError:
            pass

    def recent_heals(self, limit: int = 20) -> List[Dict]:
        return self._heal_events[-limit:]


# Singleton
runtime_healer = RuntimeHealer()
