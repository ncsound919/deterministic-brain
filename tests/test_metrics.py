"""Comprehensive tests for tools/metrics.py — MetricsCollector singleton."""

from __future__ import annotations
import time
import pytest
from tools.metrics import get_metrics, reset_metrics


def _fresh() -> "MetricsCollector":
    reset_metrics()
    return get_metrics()


class TestRecordRequest:
    def test_increments_count(self):
        m = _fresh()
        m.record_request("/api/test", 10.0, 200)
        snap = m.snapshot()
        assert snap["routes"]["/api/test"]["count"] == 1
        assert snap["total_requests"] == 1

    def test_records_multiple_routes(self):
        m = _fresh()
        m.record_request("/a", 5.0, 200)
        m.record_request("/b", 8.0, 200)
        snap = m.snapshot()
        assert set(snap["routes"]) == {"/a", "/b"}
        assert snap["total_requests"] == 2

    def test_records_errors_on_4xx(self):
        m = _fresh()
        m.record_request("/err", 10.0, 400)
        snap = m.snapshot()
        assert snap["routes"]["/err"]["errors"] == 1

    def test_records_errors_on_5xx(self):
        m = _fresh()
        m.record_request("/err", 10.0, 500)
        snap = m.snapshot()
        assert snap["routes"]["/err"]["errors"] == 1

    def test_2xx_is_not_error(self):
        m = _fresh()
        m.record_request("/ok", 5.0, 200)
        m.record_request("/ok", 5.0, 204)
        snap = m.snapshot()
        assert snap["routes"]["/ok"]["errors"] == 0

    def test_3xx_is_not_error(self):
        m = _fresh()
        m.record_request("/redir", 5.0, 301)
        m.record_request("/redir", 5.0, 302)
        snap = m.snapshot()
        assert snap["routes"]["/redir"]["errors"] == 0


class TestRecordCache:
    def test_cache_hit(self):
        m = _fresh()
        m.record_cache_hit()
        assert m._cache_hits == 1

    def test_cache_miss(self):
        m = _fresh()
        m.record_cache_miss()
        assert m._cache_misses == 1

    def test_both_counted_in_snapshot(self):
        m = _fresh()
        m.record_cache_hit()
        m.record_cache_hit()
        m.record_cache_hit()
        m.record_cache_miss()
        snap = m.snapshot()
        assert snap["cache"]["hits"] == 3
        assert snap["cache"]["misses"] == 1


class TestRecordSqlite:
    def test_tracks_cumulative_ms_and_calls(self):
        m = _fresh()
        m.record_sqlite(100.0)
        m.record_sqlite(50.0)
        snap = m.snapshot()
        assert snap["sqlite"]["total_ms"] == 150.0
        assert snap["sqlite"]["calls"] == 2

    def test_avg_ms(self):
        m = _fresh()
        m.record_sqlite(100.0)
        m.record_sqlite(200.0)
        snap = m.snapshot()
        assert snap["sqlite"]["avg_ms"] == 150.0


class TestLatencyPercentiles:
    def test_empty_route_returns_zeros(self):
        m = _fresh()
        assert m.get_latency_percentiles("/nonexistent") == {
            "p50": 0, "p95": 0, "p99": 0, "count": 0
        }

    def test_single_sample(self):
        m = _fresh()
        m.record_request("/route", 42.0, 200)
        assert m.get_latency_percentiles("/route") == {
            "p50": 42.0, "p95": 42.0, "p99": 42.0, "count": 1
        }

    def test_p50_p95_p99_correct(self):
        m = _fresh()
        for i in range(1, 101):
            m.record_request("/route", float(i), 200)
        lat = m.get_latency_percentiles("/route")
        assert lat["count"] == 100
        assert lat["p50"] == 51.0
        assert lat["p95"] == 96.0
        assert lat["p99"] == 100.0

    def test_different_routes_independent(self):
        m = _fresh()
        for i in range(1, 101):
            m.record_request("/fast", float(i), 200)
        for i in range(1, 201):
            m.record_request("/slow", float(i * 2), 200)
        fast = m.get_latency_percentiles("/fast")
        slow = m.get_latency_percentiles("/slow")
        assert fast["count"] == 100
        assert slow["count"] == 200
        assert slow["p50"] > fast["p50"]


class TestErrorRate:
    def test_no_errors_returns_zero(self):
        m = _fresh()
        m.record_request("/route", 10.0, 200)
        assert m.get_error_rate("/route") == 0.0

    def test_errors_in_window(self):
        m = _fresh()
        m.record_request("/route", 10.0, 500)
        m.record_request("/route", 10.0, 200)
        rate = m.get_error_rate("/route", window_sec=300.0)
        assert rate == 0.5

    def test_all_errors(self):
        m = _fresh()
        for _ in range(5):
            m.record_request("/route", 10.0, 500)
        assert m.get_error_rate("/route", window_sec=300.0) == 1.0

    def test_no_requests_returns_zero(self):
        m = _fresh()
        assert m.get_error_rate("/empty") == 0.0

    def test_errors_outside_window_excluded(self):
        m = _fresh()
        m.record_request("/route", 10.0, 500)
        rate = m.get_error_rate("/route", window_sec=0.0)
        assert rate == 0.0


class TestCacheRatio:
    def test_no_activity_returns_zero(self):
        m = _fresh()
        assert m.get_cache_ratio() == 0.0

    def test_all_hits(self):
        m = _fresh()
        m.record_cache_hit()
        m.record_cache_hit()
        m.record_cache_hit()
        assert m.get_cache_ratio() == 1.0

    def test_mixed(self):
        m = _fresh()
        m.record_cache_hit()
        m.record_cache_hit()
        m.record_cache_hit()
        m.record_cache_miss()
        assert m.get_cache_ratio() == 0.75

    def test_no_hits(self):
        m = _fresh()
        m.record_cache_miss()
        m.record_cache_miss()
        assert m.get_cache_ratio() == 0.0

    def test_matches_snapshot(self):
        m = _fresh()
        m.record_cache_hit()
        m.record_cache_miss()
        m.record_cache_miss()
        m.record_cache_miss()
        assert m.get_cache_ratio() == 0.25
        assert m.snapshot()["cache"]["hit_ratio"] == 0.25


class TestPrune:
    def test_prune_does_not_remove_few_samples(self):
        m = _fresh()
        for _ in range(50):
            m.record_request("/route", 10.0, 200)
        m.prune()
        assert m.get_latency_percentiles("/route")["count"] == 50

    def test_prune_trims_buckets_to_max(self):
        m = _fresh()
        n = m.MAX_SAMPLES_PER_ROUTE + 500
        for i in range(n):
            m.record_request("/route", float(i), 200)
        m.prune()
        assert m.get_latency_percentiles("/route")["count"] == m.MAX_SAMPLES_PER_ROUTE
        # Should have kept the newest values
        lat = m.get_latency_percentiles("/route")
        assert lat["p99"] > float(m.MAX_SAMPLES_PER_ROUTE)


class TestSnapshot:
    def test_initial_snapshot_structure(self):
        m = _fresh()
        snap = m.snapshot()
        assert "uptime_sec" in snap
        assert "uptime_str" in snap
        assert snap["routes"] == {}
        assert snap["total_requests"] == 0
        assert snap["total_errors"] == 0
        assert snap["cache"] == {"hits": 0, "misses": 0, "hit_ratio": 0.0}
        assert snap["sqlite"] == {"total_ms": 0.0, "calls": 0, "avg_ms": 0.0}

    def test_snapshot_after_activity(self):
        m = _fresh()
        m.record_request("/api/status", 25.0, 200)
        m.record_request("/api/status", 50.0, 500)
        m.record_cache_hit()
        m.record_cache_miss()
        m.record_sqlite(30.0)
        snap = m.snapshot()
        assert snap["total_requests"] == 2
        assert snap["total_errors"] == 1
        assert snap["routes"]["/api/status"]["count"] == 2
        assert snap["routes"]["/api/status"]["errors"] == 1
        assert snap["routes"]["/api/status"]["latency_ms"]["count"] == 2
        assert snap["cache"]["hits"] == 1
        assert snap["cache"]["misses"] == 1
        assert snap["cache"]["hit_ratio"] == 0.5
        assert snap["sqlite"]["total_ms"] == 30.0
        assert snap["sqlite"]["calls"] == 1
        assert snap["sqlite"]["avg_ms"] == 30.0

    def test_uptime_increases(self):
        m = _fresh()
        snap1 = m.snapshot()
        time.sleep(0.01)
        snap2 = m.snapshot()
        assert snap2["uptime_sec"] >= snap1["uptime_sec"]


class TestBoundedBuckets:
    def test_pops_oldest_when_over_max(self):
        m = _fresh()
        n = m.MAX_SAMPLES_PER_ROUTE + 100
        for i in range(n):
            m.record_request("/route", float(i), 200)
        lat = m.get_latency_percentiles("/route")
        assert lat["count"] == m.MAX_SAMPLES_PER_ROUTE
        # The first entries (0, 1, ...) should have been popped
        vals_sorted = sorted(m._buckets["/route"])
        assert vals_sorted[0] == 100.0

    def test_multiple_routes_independent_bounds(self):
        m = _fresh()
        n = m.MAX_SAMPLES_PER_ROUTE + 50
        for i in range(n):
            m.record_request("/a", float(i), 200)
        for i in range(10):
            m.record_request("/b", float(i), 200)
        assert m.get_latency_percentiles("/a")["count"] == m.MAX_SAMPLES_PER_ROUTE
        assert m.get_latency_percentiles("/b")["count"] == 10

    def test_errors_counted_on_bounded_buckets(self):
        m = _fresh()
        n = m.MAX_SAMPLES_PER_ROUTE + 50
        for i in range(n):
            m.record_request("/route", float(i), 500 if i % 2 == 0 else 200)
        snap = m.snapshot()
        assert snap["routes"]["/route"]["count"] == n
        assert snap["routes"]["/route"]["latency_ms"]["count"] == m.MAX_SAMPLES_PER_ROUTE


class TestResetMetrics:
    def test_get_metrics_returns_singleton(self):
        reset_metrics()
        a = get_metrics()
        b = get_metrics()
        assert a is b

    def test_reset_creates_fresh_state(self):
        reset_metrics()
        m1 = get_metrics()
        m1.record_request("/test", 5.0, 200)
        assert m1.snapshot()["total_requests"] == 1
        reset_metrics()
        m2 = get_metrics()
        assert m2.snapshot()["total_requests"] == 0
        assert m2 is not m1


class TestConcurrency:
    def test_record_request_thread_safe(self):
        import threading
        m = _fresh()
        n = 1000
        threads = []
        errors = []
        barrier = threading.Barrier(4)

        def worker(route: str, status: int):
            barrier.wait()
            for _ in range(n):
                try:
                    m.record_request(route, 10.0, status)
                except Exception as e:
                    errors.append(e)

        routes = [("/a", 200), ("/a", 500), ("/b", 200), ("/b", 400)]
        for route, status in routes:
            t = threading.Thread(target=worker, args=(route, status))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        assert not errors
        snap = m.snapshot()
        assert snap["total_requests"] == 4 * n

    def test_cache_thread_safe(self):
        import threading
        m = _fresh()
        n = 5000
        barrier = threading.Barrier(2)

        def hit_worker():
            barrier.wait()
            for _ in range(n):
                m.record_cache_hit()

        def miss_worker():
            barrier.wait()
            for _ in range(n):
                m.record_cache_miss()

        t1 = threading.Thread(target=hit_worker)
        t2 = threading.Thread(target=miss_worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert m._cache_hits == n
        assert m._cache_misses == n
