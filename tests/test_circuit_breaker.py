"""Tests for tools/circuit_breaker.py."""
import time
from tools.circuit_breaker import CircuitBreaker, get_breaker, breaker_state, all_breaker_states


def _raise(msg):
    raise ValueError(msg)


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker("test")
        assert cb._state == "closed"

    def test_call_success_returns_result(self):
        cb = CircuitBreaker("test", threshold=2)
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb._state == "closed"

    def test_opens_on_threshold(self):
        cb = CircuitBreaker("test", threshold=2, window_s=60)
        r1 = cb.call(lambda: _raise("fail"))
        r2 = cb.call(lambda: _raise("fail"))
        assert r1["status"] == "failed"
        assert r2["status"] == "failed"
        assert cb._state == "open"

    def test_blocks_when_open(self):
        cb = CircuitBreaker("test", threshold=1, cooldown_s=300)
        cb.call(lambda: _raise("fail"))
        result = cb.call(lambda: "should_not_run")
        assert result["status"] == "circuit_open"

    def test_half_open_after_cooldown(self):
        cb = CircuitBreaker("test", threshold=1, cooldown_s=0.01, window_s=60)
        cb.call(lambda: _raise("fail"))
        assert cb._state == "open"
        time.sleep(0.02)
        assert cb._check() is True
        assert cb._state == "half_open"

    def test_half_open_success_closes(self):
        cb = CircuitBreaker("test", threshold=1, cooldown_s=0.01, window_s=60)
        cb.call(lambda: _raise("fail"))
        time.sleep(0.02)
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb._state == "closed"

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker("test", threshold=1, cooldown_s=0.01, window_s=60)
        cb.call(lambda: _raise("fail"))
        time.sleep(0.02)
        result = cb.call(lambda: _raise("fail2"))
        assert result["status"] == "failed"
        assert cb._state == "open"

    def test_retry_on_failure(self):
        attempts = []
        def flaky():
            attempts.append(1)
            if len(attempts) < 2:
                raise ValueError("not yet")
            return "ok"
        cb = CircuitBreaker("test", threshold=3, retries=2, backoff_ms=1)
        result = cb.call(flaky)
        assert result == "ok"
        assert len(attempts) == 2

    def test_window_expires_failures(self):
        cb = CircuitBreaker("test", threshold=2, window_s=0.01)
        cb.call(lambda: _raise("fail"))
        time.sleep(0.02)
        cb._trim_failures()
        cb.call(lambda: _raise("fail"))
        assert cb._state == "closed"

    def test_get_breaker_singleton(self):
        b1 = get_breaker("singleton_test")
        b2 = get_breaker("singleton_test")
        assert b1 is b2

    def test_breaker_state_returns_none_for_unknown(self):
        assert breaker_state("nonexistent") is None

    def test_all_breaker_states_returns_dict(self):
        get_breaker("state_test_a")
        get_breaker("state_test_b")
        states = all_breaker_states()
        assert isinstance(states, dict)
        assert "state_test_a" in states
