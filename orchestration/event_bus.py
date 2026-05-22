"""Central event bus — connects KAIROS ↔ DevPet ↔ AutoDream ↔ Dashboard.

Thread-safe pub/sub so each subsystem can emit and subscribe independently.
"""

from __future__ import annotations
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

_DISTRIBUTED = os.environ.get("DISTRIBUTED_MODE", "").lower() in ("1", "true", "yes")


class EventBus:
    """In-memory pub/sub event bus with optional persistent logging."""

    def __init__(self, log_path: str = ".event_bus_log.jsonl"):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
        self._log_lock = threading.Lock()
        self._event_log: List[Dict[str, Any]] = []
        self._log_path = log_path
        self._load_log()

    def _load_log(self) -> None:
        import os
        if not os.path.exists(self._log_path):
            return
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines[-5000:]:
                line = line.strip()
                if line:
                    import json
                    self._event_log.append(json.loads(line))
        except Exception as e:
            logger.warning("EventBus: failed to load event log: %s", e)

    def _append_log(self, event: Dict[str, Any]) -> None:
        if not self._log_path:
            return
        try:
            import json
            with self._log_lock:
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event, default=str) + "\n")
        except Exception as e:
            logger.warning("EventBus: failed to append event log: %s", e)

    def subscribe(self, event_type: str, callback: Callable) -> None:
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(callback)
        if _DISTRIBUTED:
            try:
                from tools.redis_client import get_redis
                r = get_redis()
                if r.available:
                    import json
                    def redis_callback(message: str) -> None:
                        try:
                            data = json.loads(message)
                            callback(**data)
                        except Exception:
                            pass
                    r.subscribe(f"event:{event_type}", redis_callback)
            except Exception:
                pass

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
        self._append_log(event)

        for cb in callbacks:
            try:
                cb(**data)
            except Exception as exc:
                logger.warning("EventBus subscriber %s failed: %s", cb, exc)

        if _DISTRIBUTED:
            try:
                from tools.redis_client import get_redis
                r = get_redis()
                if r.available:
                    import json
                    r.publish(f"event:{event_type}", json.dumps({"ts": time.time(), **data}, default=str))
            except Exception:
                pass

    def recent_events(self, limit: int = 100) -> List[Dict]:
        with self._lock:
            return list(self._event_log[-limit:])

    def clear(self) -> None:
        with self._lock:
            self._event_log.clear()
        try:
            import os
            if os.path.exists(self._log_path):
                os.remove(self._log_path)
        except Exception as e:
            logger.warning("EventBus: failed to clear event log: %s", e)


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
            except Exception as e:
                logger.warning("DevPet process_events failed: %s", e)
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
