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
        self._event_log.append(event)
        # Keep log bounded
        if len(self._event_log) > 5000:
            self._event_log = self._event_log[-2500:]

        with self._lock:
            callbacks = list(self._subscribers.get(event_type, []))

        for cb in callbacks:
            try:
                cb(**data)
            except Exception:
                pass  # never let one subscriber break others

    def recent_events(self, limit: int = 100) -> List[Dict]:
        return self._event_log[-limit:]

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
