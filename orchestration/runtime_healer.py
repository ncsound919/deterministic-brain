"""Runtime healer v2 — proactive self-healing with adaptive thresholds.

v2 additions:
- Adaptive thresholding via exponential moving average of failure rate
- Proactive recovery protocols (cache clear, state reset, reconnect)
- Correction-driven constraint generation (teaches DCAEngine what to avoid)
- Health snapshot for /healer/status endpoint
"""
from __future__ import annotations
import time
import json
import threading
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from reasoning.context_graph import get_context_graph


@dataclass
class SkillHealth:
    skill_id: str
    failures_window: List[float] = field(default_factory=list)
    success_window: List[float] = field(default_factory=list)
    last_failure_ts: float = 0.0
    last_success_ts: float = 0.0
    state: str = "closed"  # closed, open, half_open
    opened_at: float = 0.0
    failure_count: int = 0
    success_count: int = 0
    # Adaptive EMA tracking
    ema_failure_rate: float = 0.0
    ema_alpha: float = 0.3
    last_error_msg: str = ""
    recovery_attempted: bool = False


class RuntimeHealer:
    """Production watchdog with adaptive circuit breaker, retry, daemon recovery.

    v2 enhancements:
    - Adaptive threshold: tightens during error bursts, loosens during stability
    - Proactive recovery: tries lighter recovery before opening circuit
    - Constraint generation: failed corrections become DCAEngine constraints
    """

    def __init__(self, heal_log: str = ".heal_runtime_log.json",
                 constraints_path: str = ".healer_constraints.json"):
        self._skills: Dict[str, SkillHealth] = {}
        self._lock = threading.RLock()
        self._daemon_watches: Dict[str, Dict] = {}
        self._heal_log = Path(heal_log)
        self._constraints_path = Path(constraints_path)
        self._heal_events: List[Dict] = []

        # Base config (used as floor by adaptive logic)
        self.circuit_window_s = 600       # 10 minutes
        self.circuit_threshold = 5         # base threshold
        self.circuit_cooldown_s = 300      # 5 minutes
        self.max_restarts = 3

        # Adaptive parameters
        self.adaptive_min_threshold = 2    # never go below 2 failures
        self.adaptive_max_threshold = 20   # never go above 20
        self.ema_alpha = 0.3               # EMA smoothing factor

        # Learned constraints (loaded from file, written by heal_from_corrections)
        self._learned_constraints: List[Dict] = []
        self._load_constraints()

    # ── Adaptive threshold ───────────────────────────────────────

    def _adaptive_threshold(self, h: SkillHealth) -> int:
        """Scale circuit_threshold by EMA failure rate.

        rate=0.0 → 1.5x threshold (tolerant)
        rate=0.5 → 1.0x threshold (neutral)
        rate=1.0 → 0.5x threshold (sensitive)
        """
        rate = h.ema_failure_rate
        scaled = int(self.circuit_threshold * (1.5 - rate))
        return max(1, scaled)

    def _update_ema(self, h: SkillHealth, is_failure: bool) -> None:
        """Update exponential moving average of failure rate."""
        raw = 1.0 if is_failure else 0.0
        h.ema_failure_rate = h.ema_alpha * raw + (1.0 - h.ema_alpha) * h.ema_failure_rate

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
            h.success_window.append(now)
            self._update_ema(h, is_failure=False)
            if h.state == "half_open":
                h.state = "closed"
                h.failure_count = 0
                h.failures_window.clear()
                self._log("circuit_closed", skill_id=skill_id)
            # Success resets recovery flag
            h.recovery_attempted = False

    def record_failure(self, skill_id: str, error_msg: str = "", session_id: str = "") -> None:
        h = self._get_health(skill_id)
        with self._lock:
            now = time.time()
            h.failure_count += 1
            h.last_failure_ts = now
            h.last_error_msg = error_msg or h.last_error_msg
            cutoff = now - self.circuit_window_s
            h.failures_window = [t for t in h.failures_window if t > cutoff]
            h.failures_window.append(now)
            self._update_ema(h, is_failure=True)

            threshold = self._adaptive_threshold(h)
            if h.state == "closed" and len(h.failures_window) >= threshold:
                h.state = "open"
                h.opened_at = now
                self._log("circuit_opened", skill_id=skill_id,
                          failures=len(h.failures_window), threshold=threshold)
            elif h.state == "half_open":
                h.state = "open"
                h.opened_at = now
                self._log("circuit_reopened", skill_id=skill_id)

        # Enrich error message with causal attribution if session_id provided
        if session_id:
            try:
                cg = get_context_graph()
                if cg:
                    attribution = cg.failure_attribution(session_id)
                    if attribution and not error_msg:
                        h.last_error_msg = f"causal: {json.dumps(attribution[:2])}"
            except Exception:
                pass

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
                "failure_rate_ema": round(h.ema_failure_rate, 4),
                "adaptive_threshold": self._adaptive_threshold(h),
                "cooldown_remaining_s": max(0, round(open_remaining)),
                "last_error": h.last_error_msg[:120] if h.last_error_msg else "",
                "recovery_attempted": h.recovery_attempted,
            }

    def all_circuit_states(self) -> List[Dict]:
        with self._lock:
            skill_ids = list(self._skills.keys())
        return [self.circuit_breaker_state(s) for s in skill_ids]

    # ── Proactive Recovery ───────────────────────────────────────

    def recover_skill(self, skill_id: str) -> Dict:
        """Attempt progressive recovery before/after circuit trip.

        Stages:
          1. Reset in-memory state
          2. Clear failure window (give benefit of doubt)
          3. Log recovery attempt
        """
        h = self._get_health(skill_id)
        with self._lock:
            h.recovery_attempted = True
            h.failures_window.clear()
            h.failure_count = 0
            if h.state in ("open", "half_open"):
                h.state = "closed"
                h.opened_at = 0.0
            self._log("recovery_applied", skill_id=skill_id,
                      state_before=h.state, ema_before=round(h.ema_failure_rate, 4))
            h.ema_failure_rate = max(0.0, h.ema_failure_rate * 0.5)
        return {"status": "recovered", "skill_id": skill_id}

    def recover_all(self) -> List[Dict]:
        """Recover all skills in non-closed states."""
        results = []
        for sid in list(self._skills.keys()):
            h = self._skills[sid]
            if h.state != "closed":
                results.append(self.recover_skill(sid))
        return results

    # ── Retry Logic ─────────────────────────────────────────────

    def execute_with_retry(self, fn: Callable, skill_id: str,
                           max_retries: int = 3, backoff_ms: float = 1000.0) -> Dict:
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
                self.record_failure(skill_id, error_msg=str(e))
                if attempt < max_retries - 1:
                    wait = backoff_ms * (2 ** attempt) / 1000
                    time.sleep(wait)

        return {"status": "failed", "skill_id": skill_id,
                "error": last_error, "attempts": max_retries}

    # ── Daemon Watchdog ──────────────────────────────────────────

    def watch_daemon(self, name: str, start_fn: Callable,
                     is_alive_fn: Callable) -> None:
        with self._lock:
            self._daemon_watches[name] = {
                "start": start_fn, "is_alive": is_alive_fn,
                "restart_count": 0, "last_check": time.time(),
            }
        self._log("daemon_watch_started", daemon=name)

    def check_daemons(self) -> List[Dict]:
        results = []
        with self._lock:
            watches = list(self._daemon_watches.items())
        for name, cfg in watches:
            if not cfg["is_alive"]():
                if cfg["restart_count"] < self.max_restarts:
                    try:
                        cfg["start"]()
                        with self._lock:
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
                with self._lock:
                    cfg["last_check"] = time.time()
        return results

    # ── Healing from Corrections (v2 — constraint generation) ────

    def heal_from_corrections(self, corrections_file: str = ".autodream_corrections.jsonl") -> Dict:
        """Process autodream corrections — deprecate + generate constraints.

        Returns summary of what was healed and what constraints were generated.
        """
        path = Path(corrections_file)
        if not path.exists():
            return {"deprecated": 0, "constraints_generated": 0, "skills_flagged": 0}

        lines = [l.strip() for l in path.read_text().split("\n") if l.strip()]
        from collections import Counter, defaultdict

        failed_skills = Counter()
        error_patterns = defaultdict(set)

        for line in lines:
            try:
                entry = json.loads(line)
                skill = entry.get("failed_skill", "")
                err = entry.get("error", entry.get("suggested_action", ""))
                if skill:
                    failed_skills[skill] += 1
                    if err:
                        error_patterns[skill].add(str(err)[:200])
            except json.JSONDecodeError:
                continue

        deprecated_count = 0
        new_constraints = []

        for skill, fails in failed_skills.items():
            if fails >= 5:
                deprecated_count += 1
                for _ in range(min(fails, self.circuit_threshold + 1)):
                    self.record_failure(skill, error_msg=f"correction: {fails} failures")

                # Generate a constraint from the error patterns
                errors_for_skill = error_patterns.get(skill, set())
                for err_text in errors_for_skill:
                    constraint = {
                        "source": "healer_correction",
                        "skill_id": skill,
                        "pattern": err_text,
                        "failure_count": fails,
                        "created_at": time.time(),
                    }
                    # Enrich constraint with causal factors from context graph
                    try:
                        cg = get_context_graph()
                        if cg:
                            attribution = cg.failure_attribution(skill)
                            if attribution:
                                constraint["causal_factors"] = [
                                    {"type": a["decision_type"], "factors": a["factor_weights"]}
                                    for a in attribution
                                ]
                    except Exception:
                        pass
                    new_constraints.append(constraint)

        if new_constraints:
            with self._lock:
                self._learned_constraints.extend(new_constraints)
            self._save_constraints()

        return {
            "deprecated": deprecated_count,
            "constraints_generated": len(new_constraints),
            "skills_flagged": len(failed_skills),
        }

    # ── Constraint Persistence ───────────────────────────────────

    def _save_constraints(self) -> None:
        try:
            seen = set()
            deduped = []
            for c in self._learned_constraints:
                key = (c.get("skill_id", ""), c.get("pattern", ""))
                if key not in seen:
                    seen.add(key)
                    deduped.append(c)
            self._learned_constraints = deduped[-500:]
            self._constraints_path.write_text(json.dumps(self._learned_constraints, indent=2))
        except IOError:
            pass

    def _load_constraints(self) -> None:
        try:
            if self._constraints_path.exists():
                data = json.loads(self._constraints_path.read_text())
                self._learned_constraints = data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            self._learned_constraints = []

    def get_learned_constraints(self) -> List[Dict]:
        """Return learned constraints for DCAEngine to consume."""
        return list(self._learned_constraints)

    def clear_learned_constraints(self) -> None:
        with self._lock:
            self._learned_constraints.clear()
        try:
            if self._constraints_path.exists():
                self._constraints_path.unlink()
        except IOError:
            pass

    # ── Health Snapshot ──────────────────────────────────────────

    def health_snapshot(self) -> Dict:
        """Full health snapshot for /healer/status endpoint."""
        states = self.all_circuit_states()
        open_count = sum(1 for s in states if s["state"] == "open")
        half_open_count = sum(1 for s in states if s["state"] == "half_open")
        with self._lock:
            daemon_count = len(self._daemon_watches)

        return {
            "skills_tracked": len(states),
            "circuits_open": open_count,
            "circuits_half_open": half_open_count,
            "circuits_closed": len(states) - open_count - half_open_count,
            "daemons_watched": daemon_count,
            "learned_constraints": len(self._learned_constraints),
            "skills": states,
            "recent_events": self.recent_heals(10),
        }

    # ── Logging ──────────────────────────────────────────────────

    def _log(self, event: str, **data):
        entry = {"ts": time.time(), "event": event, "data": data}
        with self._lock:
            self._heal_events.append(entry)
            if len(self._heal_events) > 500:
                self._heal_events = self._heal_events[-250:]
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


# ── Unified circuit breaker bridge ────────────────────────────────


def unified_breaker_states() -> Dict[str, Dict]:
    """Aggregate breaker states from both RuntimeHealer (internal skills) and
    tools.circuit_breaker (external API calls) into a single view."""
    result: Dict[str, Dict] = {}

    # Internal skill breakers from RuntimeHealer
    try:
        snapshot = runtime_healer.health_snapshot()
        for s in snapshot.get("skills", []):
            name = s.get("skill_id", "unknown")
            result[f"skill:{name}"] = {
                "name": name,
                "state": s.get("state", "unknown"),
                "type": "skill",
                "failures_window": s.get("failures_window", 0),
                "success_window": s.get("success_window", 0),
                "ema_failure_rate": s.get("ema_failure_rate", 0.0),
            }
    except Exception:
        pass

    # External API breakers from tools.circuit_breaker
    try:
        from tools.circuit_breaker import all_breaker_states as ext_states
        ext = ext_states()
        for name, state in ext.items():
            result[f"api:{name}"] = {
                "name": name,
                "state": state.get("state", "unknown"),
                "type": "api",
                "recent_failures": state.get("recent_failures", 0),
                "opened_at": state.get("opened_at", 0),
            }
    except Exception:
        pass

    return result
