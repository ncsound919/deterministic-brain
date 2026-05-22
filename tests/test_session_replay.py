"""Tests for orchestration/session_replay.py."""
import time
from orchestration.session_replay import SessionReplayEngine, ReplaySession, NodeSnapshot


class TestSessionReplayEngine:
    def setup_method(self):
        self.engine = SessionReplayEngine()

    def test_capture_session_returns_none_for_unknown(self):
        result = self.engine.capture_session("nonexistent_session_12345")
        assert result is None

    def test_replay_returns_error_for_unknown(self):
        gen = self.engine.replay("nonexistent_session_12345")
        result = next(gen)
        assert "error" in result
        assert "not found" in result["error"]

    def test_list_sessions_returns_list(self):
        sessions = self.engine.list_sessions(limit=5)
        assert isinstance(sessions, list)

    def test_describe_returns_expected_schema(self):
        session = ReplaySession(
            session_id="test_sid",
            nodes=[
                NodeSnapshot(node_name="parse", timestamp=100.0, state_snapshot={"status": "ok"}, delta_from_previous={}),
                NodeSnapshot(node_name="execute", timestamp=200.0, state_snapshot={"status": "ok"}, delta_from_previous={"status": {"before": None, "after": "ok"}}),
            ],
            start_time=100.0,
            end_time=200.0,
            outcome="ok",
        )
        desc = self.engine.describe(session)
        assert desc["session_id"] == "test_sid"
        assert desc["duration_s"] == 100.0
        assert desc["nodes_visited"] == 2
        assert desc["node_sequence"] == ["parse", "execute"]
        assert desc["outcome"] == "ok"

    def test_compute_delta_detects_changes(self):
        prev = {"a": 1, "b": 2}
        curr = {"a": 1, "b": 3, "c": 4}
        delta = SessionReplayEngine._compute_delta(prev, curr)
        assert "b" in delta
        assert "c" in delta
        assert "a" not in delta
        assert delta["b"]["before"] == 2
        assert delta["b"]["after"] == 3
        assert delta["c"]["before"] is None
        assert delta["c"]["after"] == 4

    def test_compute_delta_empty_prev(self):
        delta = SessionReplayEngine._compute_delta({}, {"x": 1})
        assert delta["x"]["before"] is None
        assert delta["x"]["after"] == 1

    def test_compute_delta_empty_curr(self):
        delta = SessionReplayEngine._compute_delta({"x": 1}, {})
        assert delta["x"]["before"] == 1
        assert delta["x"]["after"] is None

    def test_node_snapshot_dataclass(self):
        ns = NodeSnapshot(node_name="test", timestamp=1.0, state_snapshot={"k": "v"}, delta_from_previous={"k": {"before": None, "after": "v"}})
        assert ns.node_name == "test"
        assert ns.state_snapshot["k"] == "v"

    def test_replay_session_dataclass(self):
        rs = ReplaySession(session_id="sid", nodes=[], start_time=0.0, end_time=1.0, outcome="ok")
        assert rs.session_id == "sid"
        assert rs.outcome == "ok"
