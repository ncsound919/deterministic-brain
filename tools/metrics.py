"""MetricsCollector — request latency, error rates, cache stats, SQLite timing.

Singleton accessible via get_metrics(). Thread-safe with minimal locking.
Prometheus exposition is maintained in parallel via prometheus_client
(rendered by render_prometheus() for the /metrics endpoint); the JSON
snapshot() contract is unchanged.
"""
from __future__ import annotations
import os
import time
import threading
from collections import defaultdict
from typing import Optional

_DISTRIBUTED = os.environ.get("DISTRIBUTED_MODE", "").lower() in ("1", "true", "yes")

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter as _PmCounter,
        Gauge as _PmGauge,
        Histogram as _PmHistogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )

    class _PrometheusMirror:
        """Mirrors MetricsCollector state into a prometheus_client registry."""

        def __init__(self) -> None:
            self.registry = CollectorRegistry()
            self._counters: dict[str, any] = {}
            self._error_counters: dict[str, any] = {}
            self._latencies: dict[str, any] = {}
            self.requests_total = _PmCounter(
                "brain_requests_total", "Total requests", ["route"], registry=self.registry
            )
            self.errors_total = _PmCounter(
                "brain_request_errors_total", "Total errors (status >= 400)", ["route"], registry=self.registry
            )
            self.cache_hits = _PmCounter(
                "brain_cache_hits_total", "Cache hits", registry=self.registry
            )
            self.cache_misses = _PmCounter(
                "brain_cache_misses_total", "Cache misses", registry=self.registry
            )
            self.sqlite_seconds = _PmCounter(
                "brain_sqlite_seconds_total", "Cumulative time spent in SQLite", registry=self.registry
            )
            self.sqlite_calls = _PmCounter(
                "brain_sqlite_calls_total", "SQLite call count", registry=self.registry
            )
            self.uptime = _PmGauge(
                "brain_uptime_seconds", "Process uptime in seconds", registry=self.registry
            )
            self.uptime.set_function(lambda: time.time() - _START_TS)

        def _counter(self, route: str, table: dict, metric_cls, name: str, doc: str):
            c = table.get(route)
            if c is None:
                c = metric_cls(name, doc, ["route"], registry=self.registry)
                c = c.labels(route)
                table[route] = c
            return c

        def record_request(self, route: str, elapsed_ms: float, status_code: int) -> None:
            try:
                self._counter(
                    route, self._counters, _PmCounter, "brain_route_requests_total", "Requests per route"
                ).inc()
                h = self._latencies.get(route)
                if h is None:
                    h = _PmHistogram(
                        "brain_route_latency_seconds",
                        "Request latency per route",
                        ["route"],
                        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
                        registry=self.registry,
                    ).labels(route)
                    self._latencies[route] = h
                h.observe(max(elapsed_ms, 0.0) / 1000.0)
                if status_code >= 400:
                    self._counter(
                        route, self._error_counters, _PmCounter, "brain_route_errors_total", "Errors per route"
                    ).inc()
                    self.errors_total.labels(route).inc()
            except Exception:
                pass

        def record_cache_hit(self) -> None:
            try:
                self.cache_hits.inc()
            except Exception:
                pass

        def record_cache_miss(self) -> None:
            try:
                self.cache_misses.inc()
            except Exception:
                pass

        def record_sqlite(self, elapsed_ms: float) -> None:
            try:
                self.sqlite_calls.inc()
                self.sqlite_seconds.inc(max(elapsed_ms, 0.0) / 1000.0)
            except Exception:
                pass

    def _new_mirror():
        return _PrometheusMirror()

except ImportError:  # prometheus-client optional; JSON snapshot still works
    def _new_mirror():
        return None

_START_TS = time.time()
_PROM: Optional[_PrometheusMirror] = None


def get_prometheus_mirror():
    """Lazily created Prometheus mirror (None if prometheus-client missing)."""
    global _PROM
    if _DISTRIBUTED:
        return None  # Redis path owns counters in distributed mode
    if _PROM is None:
        with threading.Lock():
            if _PROM is None:
                _PROM = _new_mirror()
    return _PROM


class MetricsCollector:
    """Thread-safe singleton for runtime performance metrics."""

    MAX_SAMPLES_PER_ROUTE = 10000
    ERROR_WINDOW_SEC = 600

    def __init__(self):
        self._lock = threading.Lock()
        self._prom = get_prometheus_mirror()
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
        if self._prom is not None:
            self._prom.record_request(route, elapsed_ms, status_code)

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
        if self._prom is not None:
            self._prom.record_cache_hit()

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
        if self._prom is not None:
            self._prom.record_cache_miss()

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
        if self._prom is not None:
            self._prom.record_sqlite(elapsed_ms)

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


def render_prometheus() -> tuple[bytes, str]:
    """Render Prometheus text exposition format (for GET /metrics).

    Returns (body, content_type); (b'', '') when prometheus-client or the
    mirror is unavailable.
    """
    prom = get_prometheus_mirror()
    if prom is None:
        return b"", ""
    try:
        return generate_latest(prom.registry), CONTENT_TYPE_LATEST
    except Exception:
        return b"", ""
