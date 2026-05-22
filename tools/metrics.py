"""MetricsCollector — request latency, error rates, cache stats, SQLite timing.

Singleton accessible via get_metrics(). Thread-safe with minimal locking.
"""
from __future__ import annotations
import os
import time
import threading
from collections import defaultdict
from typing import Optional

_DISTRIBUTED = os.environ.get("DISTRIBUTED_MODE", "").lower() in ("1", "true", "yes")


class MetricsCollector:
    """Thread-safe singleton for runtime performance metrics."""

    MAX_SAMPLES_PER_ROUTE = 10000
    ERROR_WINDOW_SEC = 600

    def __init__(self):
        self._lock = threading.Lock()
        # Per-endpoint bucketed latency (ms)
        self._buckets: dict[str, list[int]] = defaultdict(list)
        # Per-endpoint hit count
        self._counts: dict[str, int] = defaultdict(int)
        # Per-endpoint error count
        self._errors: dict[str, int] = defaultdict(int)
        # Error rate sliding windows: {route: [timestamp, ...]}
        self._error_timeline: dict[str, list[float]] = defaultdict(list)
        # Cache hit/miss
        self._cache_hits = 0
        self._cache_misses = 0
        # SQLite cumulative ms
        self._sqlite_ms = 0.0
        self._sqlite_calls = 0
        # Start time
        self._start_ts = time.time()

    def record_request(self, route: str, elapsed_ms: float, status_code: int) -> None:
        if _DISTRIBUTED:
            try:
                from tools.redis_client import get_redis
                r = get_redis()
                if r.available:
                    r.counter_increment(f"route:{route}:count")
                    if status_code >= 400:
                        r.counter_increment(f"route:{route}:errors")
            except Exception:
                pass
        with self._lock:
            self._counts[route] += 1
            bucket = self._buckets[route]
            bucket.append(elapsed_ms)
            if len(bucket) > self.MAX_SAMPLES_PER_ROUTE:
                bucket.pop(0)
            if status_code >= 400:
                self._errors[route] += 1
                now = time.time()
                timeline = self._error_timeline[route]
                cutoff = now - self.ERROR_WINDOW_SEC
                self._error_timeline[route] = [t for t in timeline if t > cutoff]
                self._error_timeline[route].append(now)

    def record_cache_hit(self) -> None:
        if _DISTRIBUTED:
            try:
                from tools.redis_client import get_redis
                r = get_redis()
                if r.available:
                    r.counter_increment("cache:hits")
            except Exception:
                pass
        with self._lock:
            self._cache_hits += 1

    def record_cache_miss(self) -> None:
        if _DISTRIBUTED:
            try:
                from tools.redis_client import get_redis
                r = get_redis()
                if r.available:
                    r.counter_increment("cache:misses")
            except Exception:
                pass
        with self._lock:
            self._cache_misses += 1

    def record_sqlite(self, elapsed_ms: float) -> None:
        if _DISTRIBUTED:
            try:
                from tools.redis_client import get_redis
                r = get_redis()
                if r.available:
                    r.counter_increment("sqlite:calls")
            except Exception:
                pass
        with self._lock:
            self._sqlite_ms += elapsed_ms
            self._sqlite_calls += 1

    def get_latency_percentiles(self, route: str) -> dict:
        with self._lock:
            vals = sorted(self._buckets.get(route, []))
        if not vals:
            return {"p50": 0, "p95": 0, "p99": 0, "count": 0}
        n = len(vals)
        return {
            "p50": vals[n // 2],
            "p95": vals[int(n * 0.95)],
            "p99": vals[int(n * 0.99)],
            "count": n,
        }

    def get_cache_ratio(self) -> float:
        with self._lock:
            total = self._cache_hits + self._cache_misses
            return self._cache_hits / total if total > 0 else 0.0

    def get_error_rate(self, route: str, window_sec: float = 300.0) -> float:
        """Error rate over a sliding time window (default 5 min)."""
        now = time.time()
        cutoff = now - window_sec
        with self._lock:
            recent = [t for t in self._error_timeline.get(route, []) if t > cutoff]
            count = self._counts.get(route, 0)
        return len(recent) / max(count, 1)

    def prune(self) -> None:
        """Trim all buckets and error timelines to prevent unbounded growth."""
        with self._lock:
            for route in list(self._buckets.keys()):
                bucket = self._buckets[route]
                if len(bucket) > self.MAX_SAMPLES_PER_ROUTE:
                    self._buckets[route] = bucket[-self.MAX_SAMPLES_PER_ROUTE:]
            now = time.time()
            cutoff = now - self.ERROR_WINDOW_SEC
            for route in list(self._error_timeline.keys()):
                self._error_timeline[route] = [
                    t for t in self._error_timeline[route] if t > cutoff
                ]

    def _prune_unlocked(self) -> None:
        """Trim all buckets and error timelines (caller must hold self._lock)."""
        for route in list(self._buckets.keys()):
            bucket = self._buckets[route]
            if len(bucket) > self.MAX_SAMPLES_PER_ROUTE:
                self._buckets[route] = bucket[-self.MAX_SAMPLES_PER_ROUTE:]
        now = time.time()
        cutoff = now - self.ERROR_WINDOW_SEC
        for route in list(self._error_timeline.keys()):
            self._error_timeline[route] = [
                t for t in self._error_timeline[route] if t > cutoff
            ]

    def snapshot(self) -> dict:
        """Return a full metrics snapshot for the /metrics endpoint."""
        with self._lock:
            self._prune_unlocked()
            uptime = time.time() - self._start_ts
            routes = list(self._counts.keys())
            cache_ratio = self._get_cache_ratio_locked()
            sqlite_avg = self._sqlite_ms / max(self._sqlite_calls, 1)
            counts = dict(self._counts)
            errors = dict(self._errors)
            cache_hits = self._cache_hits
            cache_misses = self._cache_misses
            sqlite_ms = self._sqlite_ms
            sqlite_calls = self._sqlite_calls

        route_details = {}
        for route in routes:
            lat = self.get_latency_percentiles(route)
            err_rate_5m = self.get_error_rate(route, 300)
            route_details[route] = {
                "count": counts.get(route, 0),
                "errors": errors.get(route, 0),
                "error_rate_5m": round(err_rate_5m, 4),
                "latency_ms": lat,
            }

        return {
            "uptime_sec": round(uptime, 1),
            "uptime_str": self._format_uptime(uptime),
            "routes": route_details,
            "total_requests": sum(counts.values()),
            "total_errors": sum(errors.values()),
            "cache": {
                "hits": cache_hits,
                "misses": cache_misses,
                "hit_ratio": round(cache_ratio, 4),
            },
            "sqlite": {
                "total_ms": round(sqlite_ms, 1),
                "calls": sqlite_calls,
                "avg_ms": round(sqlite_avg, 2),
            },
        }

    def _get_cache_ratio_locked(self) -> float:
        total = self._cache_hits + self._cache_misses
        return self._cache_hits / total if total > 0 else 0.0

    @staticmethod
    def _format_uptime(sec: float) -> str:
        days, rem = divmod(int(sec), 86400)
        hours, rem = divmod(rem, 3600)
        mins, secs = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        parts.append(f"{mins}m")
        parts.append(f"{secs}s")
        return " ".join(parts)


_METRICS: Optional[MetricsCollector] = None
_METRICS_LOCK = threading.Lock()


def get_metrics() -> MetricsCollector:
    global _METRICS
    if _METRICS is None:
        with _METRICS_LOCK:
            if _METRICS is None:
                _METRICS = MetricsCollector()
    return _METRICS


def reset_metrics() -> None:
    global _METRICS
    with _METRICS_LOCK:
        _METRICS = None
