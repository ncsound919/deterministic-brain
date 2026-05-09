"""Central event bus — connects KAIROS ↔ DevPet ↔ AutoDream ↔ Dashboard.

Thread-safe pub/sub so each subsystem can emit and subscribe independently.
"""

from __future__ import annotations
import threading
import time
from typing import Any, Callable, Dict, List


class EventBus:
    """In-memory pub/sub event bus with optional persistent logging."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
        self._event_log: List[Dict[str, Any]] = []

    def subscribe(self, event_type: str, callback: Callable) -> None:
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    c for c in self._subscribers[event_type] if c != callback
                ]

    def emit(self, event_type: str, **data: Any) -> None:
        event = {"type": event_type, "ts": time.time(), "data": data}
        with self._lock:
            self._event_log.append(event)
            if len(self._event_log) > 5000:
                self._event_log = self._event_log[-2500:]
            callbacks = list(self._subscribers.get(event_type, []))

        for cb in callbacks:
            try:
                cb(**data)
            except Exception:
                pass  # never let one subscriber break others

    def recent_events(self, limit: int = 100) -> List[Dict]:
        with self._lock:
            return list(self._event_log[-limit:])

    def clear(self) -> None:
        self._event_log.clear()


# Singleton
event_bus = EventBus()


# ── Default cross-system wiring ────────────────────────────────

def connect_evolution_listeners(evolver):
    """Wire skill success/failure events to SkillEvolver."""
    event_bus.subscribe("skill_success",
        lambda **kw: evolver.track(
            kw.get("skill_id", "unknown"), True,
            kw.get("latency_ms", 0), kw.get("confidence", 0)))
    event_bus.subscribe("skill_failure",
        lambda **kw: evolver.track(
            kw.get("skill_id", "unknown"), False,
            kw.get("latency_ms", 0), 0))


def connect_healer_listeners(healer):
    """Wire failure events to RuntimeHealer circuit breaker."""
    event_bus.subscribe("skill_failure",
        lambda **kw: healer.record_failure(kw.get("skill_id", "unknown")))
    event_bus.subscribe("skill_success",
        lambda **kw: healer.record_success(kw.get("skill_id", "unknown")))


def connect_devpet_listeners(tracker=None):
    """Wire maintenance events to DevPet tracker."""
    def _on_maintenance(**kw):
        if tracker:
            try:
                tracker.process_events()
            except Exception:
                pass
    event_bus.subscribe("autodream_run", _on_maintenance)


def connect_bandit_listeners(bandit=None):
    """Wire reward/outcome events to the contextual bandit learner."""
    try:
        from reasoning.contextual_bandit import get_bandit, connect_bandit_listeners as _cb
        _cb(bandit)
    except ImportError:
        pass


def connect_reward_tracker_listeners(tracker=None):
    """Wire action/conversion events to the reward tracker."""
    try:
        from evolution.reward_tracker import get_reward_tracker, connect_tracker_listeners as _ct
        _ct(tracker)
    except ImportError:
        pass


def connect_all_learning():
    """One-call wiring of the full learning loop: bandit + tracker + evolver + healer.

    Call this once at boot to activate the closed-loop learning system:
      Decision → Execute → Observe → Evolve → Repeat
    """
    try:
        from reasoning.contextual_bandit import get_bandit
        connect_bandit_listeners(get_bandit())
    except ImportError:
        pass
    try:
        from evolution.reward_tracker import get_reward_tracker
        connect_reward_tracker_listeners(get_reward_tracker())
    except ImportError:
        pass
    try:
        from evolution.skill_evolver import SkillEvolver
        connect_evolution_listeners(SkillEvolver())
    except ImportError:
        pass
    try:
        from orchestration.runtime_healer import runtime_healer
        connect_healer_listeners(runtime_healer)
    except ImportError:
        pass
