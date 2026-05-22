"""Tests for runtime_healer.py — circuit breaker, retry, watchdog."""
import json


from orchestration.runtime_healer import RuntimeHealer


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        rh = RuntimeHealer()
        state = rh.circuit_breaker_state("skill_a")
        assert state["state"] == "closed"
        assert state["failure_count"] == 0

    def test_opens_after_threshold(self):
        rh = RuntimeHealer()
        rh.circuit_threshold = 3
        rh.circuit_window_s = 999  # wide window
        for _ in range(3):
            rh.record_failure("skill_a")
        assert rh.is_circuit_open("skill_a") is True
        assert rh.circuit_breaker_state("skill_a")["state"] == "open"

    def test_closed_under_threshold(self):
        rh = RuntimeHealer()
        rh.circuit_threshold = 5
        for _ in range(3):
            rh.record_failure("skill_a")
        assert rh.is_circuit_open("skill_a") is False

    def test_adaptive_tightens_on_burst(self):
        rh = RuntimeHealer()
        rh.circuit_threshold = 10
        for _ in range(3):
            rh.record_failure("skill_b")
        sk = rh._skills["skill_b"]
        assert sk.ema_failure_rate > 0.5
        assert rh._adaptive_threshold(sk) < 10

    def test_half_open_on_cooldown(self):
        rh = RuntimeHealer()
        rh.circuit_threshold = 2
        rh.circuit_window_s = 999
        rh.circuit_cooldown_s = 0  # immediate cooldown
        rh.record_failure("skill_a")
        rh.record_failure("skill_a")
        assert rh.is_circuit_open("skill_a") is False  # cooldown passed
        state = rh.circuit_breaker_state("skill_a")
        assert state["state"] == "half_open"

    def test_half_open_to_closed_on_success(self):
        rh = RuntimeHealer()
        rh.circuit_threshold = 2
        rh.circuit_window_s = 999
        rh.circuit_cooldown_s = 0
        rh.record_failure("skill_a")
        rh.record_failure("skill_a")
        rh.is_circuit_open("skill_a")  # triggers half_open
        rh.record_success("skill_a")
        assert rh.circuit_breaker_state("skill_a")["state"] == "closed"

    def test_half_open_to_open_on_failure(self):
        rh = RuntimeHealer()
        rh.circuit_threshold = 2
        rh.circuit_window_s = 999
        rh.circuit_cooldown_s = 0
        rh.record_failure("skill_a")
        rh.record_failure("skill_a")
        rh.is_circuit_open("skill_a")  # triggers half_open
        rh.record_failure("skill_a")
        assert rh.circuit_breaker_state("skill_a")["state"] == "open"

    def test_success_resets_counter(self):
        rh = RuntimeHealer()
        rh.circuit_threshold = 3
        rh.record_failure("skill_a")
        rh.record_failure("skill_a")
        rh.record_success("skill_a")
        rh.record_success("skill_a")
        state = rh.circuit_breaker_state("skill_a")
        assert state["success_count"] == 2

    def test_old_failures_expire(self):
        rh = RuntimeHealer()
        rh.circuit_threshold = 4
        rh.circuit_window_s = 0  # immediate expiry
        # Add 3 failures, they expire, then add 1 more
        for _ in range(3):
            rh.record_failure("skill_a")
        # Window is 0 so all expire immediately
        rh.record_failure("skill_a")  # only 1 fresh failure (below threshold of 4)
        assert rh.is_circuit_open("skill_a") is False

    def test_all_circuit_states(self):
        rh = RuntimeHealer()
        rh.record_failure("skill_a")
        rh.record_failure("skill_b")
        states = rh.all_circuit_states()
        assert len(states) == 2


class TestRetry:
    def test_success_on_first_attempt(self):
        rh = RuntimeHealer()
        call_count = [0]

        def fn():
            call_count[0] += 1
            return {"status": "ok"}

        result = rh.execute_with_retry(fn, "skill_a", max_retries=3)
        assert result["status"] == "ok"
        assert call_count[0] == 1

    def test_retry_on_failure_then_succeed(self):
        rh = RuntimeHealer()
        call_count = [0]

        def fn():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("transient")
            return {"status": "ok"}

        result = rh.execute_with_retry(fn, "skill_a", max_retries=3, backoff_ms=10)
        assert result["status"] == "ok"
        assert call_count[0] == 2

    def test_circuit_open_blocks(self):
        rh = RuntimeHealer()
        rh.circuit_threshold = 1
        rh.circuit_window_s = 999
        rh.record_failure("skill_b")
        rh.is_circuit_open("skill_b")  # opens it
        # should still be open (cooldown not passed)
        rh.circuit_cooldown_s = 999

        def fn():
            return {"status": "ok"}

        result = rh.execute_with_retry(fn, "skill_b", max_retries=3)
        assert result["status"] == "circuit_open"

    def test_all_retries_exhausted(self, rh=None):
        rh = rh or RuntimeHealer()
        # Reset circuit breaker threshold high to avoid opening
        rh.circuit_threshold = 999

        def fn():
            raise RuntimeError("persistent failure")

        result = rh.execute_with_retry(fn, "skill_c", max_retries=2, backoff_ms=1)
        assert result["status"] == "failed"
        assert result["attempts"] == 2


class TestHealFromCorrections:
    def test_empty_file(self, tmp_path):
        rh = RuntimeHealer()
        p = tmp_path / "corrections.jsonl"
        p.write_text("")
        result = rh.heal_from_corrections(str(p))
        assert result["deprecated"] == 0

    def test_deprecates_high_failure_skill(self, tmp_path):
        rh = RuntimeHealer()
        rh.circuit_threshold = 5
        p = tmp_path / "corrections.jsonl"
        lines = []
        for _ in range(10):
            lines.append(json.dumps({
                "failed_skill": "broken_skill",
                "confidence": 0.0,
                "suggested_action": "review_skill_selection",
            }))
        p.write_text("\n".join(lines))
        result = rh.heal_from_corrections(str(p))
        assert result["deprecated"] == 1  # one skill deprecated
        # Circuit should be open now (5+ failures recorded)
        assert rh.circuit_breaker_state("broken_skill")["state"] == "open"

    def test_below_threshold_no_deprecation(self, tmp_path):
        rh = RuntimeHealer()
        p = tmp_path / "corrections.jsonl"
        lines = []
        for _ in range(3):
            lines.append(json.dumps({
                "failed_skill": "minor_skill",
                "confidence": 0.1,
            }))
        p.write_text("\n".join(lines))
        result = rh.heal_from_corrections(str(p))
        assert result["deprecated"] == 0


class TestRecentHeals:
    def test_logs_events(self):
        rh = RuntimeHealer()
        rh._log("test_event", key="value")
        heals = rh.recent_heals(10)
        assert len(heals) == 1
        assert heals[0]["event"] == "test_event"

    def test_prunes_old_events(self):
        rh = RuntimeHealer()
        for i in range(600):
            rh._log("event", index=i)
        assert len(rh._heal_events) <= 500
