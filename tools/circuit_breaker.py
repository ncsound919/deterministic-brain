"""Lightweight circuit breaker for external API calls.

Three-state: closed → open (on threshold failures) → half_open (after cooldown) → closed.
threading.Lock for thread safety. Logs transitions via tracing.log_event.
"""
from __future__ import annotations
import time
import threading
import logging
from functools import wraps
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(self, name: str, threshold: int = 3, window_s: float = 60.0,
                 cooldown_s: float = 60.0, retries: int = 0,
                 backoff_ms: float = 1000.0):
        self.name = name
        self.threshold = threshold
        self.window_s = window_s
        self.cooldown_s = cooldown_s
        self.retries = retries
        self.backoff_ms = backoff_ms
        self._lock = threading.Lock()
        self._state = "closed"
        self._failures: list = []
        self._opened_at: float = 0.0

    def _log(self, event: str, **data):
        try:
            from tools.tracing import log_event
            log_event(f"cb_{event}", {"breaker": self.name, **data})
        except Exception:
            logger.warning("Circuit breaker log_event failed for %s", self.name)

    def _is_expired(self, ts: float) -> bool:
        return time.time() - ts > self.window_s

    def _trim_failures(self):
        self._failures = [t for t in self._failures if not self._is_expired(t)]

    def _check(self) -> bool:
        with self._lock:
            if self._state == "open":
                if time.time() - self._opened_at >= self.cooldown_s:
                    self._state = "half_open"
                    self._log("half_open", cooldown_s=self.cooldown_s)
                    return True
                return False
            if self._state == "half_open":
                return True
            self._trim_failures()
            if len(self._failures) >= self.threshold:
                self._state = "open"
                self._opened_at = time.time()
                self._log("opened", failures=len(self._failures),
                          threshold=self.threshold, window_s=self.window_s)
                return False
            return True

    def _record_success(self):
        with self._lock:
            if self._state == "half_open":
                self._state = "closed"
                self._failures.clear()
                self._log("closed")

    def _record_failure(self):
        with self._lock:
            self._failures.append(time.time())
            self._trim_failures()
            if self._state == "half_open":
                self._state = "open"
                self._opened_at = time.time()
                self._log("reopened")
            elif self._state == "closed" and len(self._failures) >= self.threshold:
                self._state = "open"
                self._opened_at = time.time()
                self._log("opened", failures=len(self._failures),
                          threshold=self.threshold, window_s=self.window_s)

    def call(self, fn: Callable, *args, **kwargs):
        if not self._check():
            return {"status": "circuit_open", "breaker": self.name,
                    "message": f"Circuit breaker open for {self.name}"}
        last_error = None
        attempts = 0
        max_attempts = 1 + self.retries
        while attempts < max_attempts:
            attempts += 1
            try:
                result = fn(*args, **kwargs)
                self._record_success()
                return result
            except Exception as e:
                last_error = str(e)
                self._record_failure()
                if attempts < max_attempts:
                    wait = self.backoff_ms * (2 ** (attempts - 1)) / 1000.0
                    time.sleep(wait)
        return {"status": "failed", "breaker": self.name,
                "error": last_error, "attempts": attempts}


_BREAKERS: Dict[str, CircuitBreaker] = {}
_BREAKERS_LOCK = threading.RLock()


def get_breaker(name: str, threshold: int = 3, window_s: float = 60.0,
                cooldown_s: float = 60.0, retries: int = 0,
                backoff_ms: float = 1000.0) -> CircuitBreaker:
    with _BREAKERS_LOCK:
        if name not in _BREAKERS:
            _BREAKERS[name] = CircuitBreaker(
                name=name, threshold=threshold, window_s=window_s,
                cooldown_s=cooldown_s, retries=retries, backoff_ms=backoff_ms,
            )
        return _BREAKERS[name]


def circuit_breaker(name: str = None, threshold: int = 3, window_s: float = 60.0,
                    cooldown_s: float = 60.0, retries: int = 0,
                    backoff_ms: float = 1000.0):
    """Decorator: wrap a function with circuit breaker protection.

    Usage:
        @circuit_breaker(name="odds_api", threshold=3, cooldown_s=60)
        def fetch_odds(sport):
            ...
    """
    def decorator(func):
        breaker_name = name or func.__name__
        br = get_breaker(breaker_name, threshold=threshold, window_s=window_s,
                         cooldown_s=cooldown_s, retries=retries, backoff_ms=backoff_ms)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return br.call(func, *args, **kwargs)
        return wrapper
    return decorator


def breaker_state(name: str) -> Optional[Dict]:
    with _BREAKERS_LOCK:
        br = _BREAKERS.get(name)
        if br is None:
            return None
        with br._lock:
            return {
                "name": br.name,
                "state": br._state,
                "recent_failures": len([t for t in br._failures if not br._is_expired(t)]),
                "opened_at": br._opened_at,
            }


def all_breaker_states() -> Dict[str, Dict]:
    with _BREAKERS_LOCK:
        return {name: breaker_state(name) for name in list(_BREAKERS.keys())
                if breaker_state(name) is not None}
