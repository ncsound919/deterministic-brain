"""Tests for tools/tracing.py — SQLite audit log."""
import json
import threading
import time

import pytest

from tools.tracing import (
    log_event,
    list_sessions,
    get_trace,
    checkpoint_state,
    _get_conn,
    _close_connections,
    _all_connections,
)


@pytest.fixture(autouse=True)
def reset_tracing_state(monkeypatch, tmp_path):
    """Reset all module-level state before each test and point TRACE_DB at a temp file."""
    import tools.tracing as tracing_mod

    db_path = tmp_path / "test_traces.db"
    monkeypatch.setenv("TRACE_DB", str(db_path))
    tracing_mod._DB_PATH = None
    tracing_mod._schema_initialized = False
    _close_connections()
    if hasattr(tracing_mod._local, "conn"):
        del tracing_mod._local.conn
    yield
    _close_connections()
    tracing_mod._DB_PATH = None
    tracing_mod._schema_initialized = False
    if hasattr(tracing_mod._local, "conn"):
        del tracing_mod._local.conn


class TestTracingCore:
    """Core CRUD operations for the tracing module."""

    def test_log_and_get_trace(self):
        session = "session-a"
        log_event("test_event", {"session_id": session, "key": "val"})
        trace = get_trace(session)
        assert len(trace) == 1
        assert trace[0]["event"] == "test_event"
        assert trace[0]["data"]["key"] == "val"
        assert trace[0]["data"]["session_id"] == session

    def test_log_event_serializes_complex_dict(self):
        session = "session-b"
        data = {"session_id": session, "nested": {"a": [1, 2, 3]}, "flag": True}
        log_event("complex", data)
        trace = get_trace(session)
        assert trace[0]["data"]["nested"] == {"a": [1, 2, 3]}
        assert trace[0]["data"]["flag"] is True

    def test_get_trace_empty_session(self):
        assert get_trace("nonexistent") == []

    def test_get_trace_ordering(self):
        session = "ordered"
        log_event("first", {"session_id": session, "idx": 1})
        time.sleep(0.01)
        log_event("second", {"session_id": session, "idx": 2})
        time.sleep(0.01)
        log_event("third", {"session_id": session, "idx": 3})
        trace = get_trace(session)
        assert [e["event"] for e in trace] == ["first", "second", "third"]

    def test_log_event_timestamp_monotonic(self):
        session = "ts-test"
        t0 = time.time()
        log_event("e1", {"session_id": session})
        t1 = time.time()
        trace = get_trace(session)
        assert t0 <= trace[0]["ts"] <= t1

    def test_list_sessions(self):
        log_event("ev", {"session_id": "s1"})
        log_event("ev", {"session_id": "s2"})
        log_event("ev", {"session_id": "s1"})
        sessions = list_sessions()
        assert sorted(sessions) == ["s1", "s2"]

    def test_list_sessions_empty(self):
        assert list_sessions() == []

    def test_list_sessions_ignores_nulls(self):
        log_event("no_session", {"foo": "bar"})
        assert list_sessions() == []

    def test_get_trace_returns_all_fields(self):
        session = "all-fields"
        log_event("my_event", {"session_id": session, "msg": "hello"})
        trace = get_trace(session)
        ev = trace[0]
        assert "ts" in ev
        assert "event" in ev
        assert "data" in ev
        assert isinstance(ev["ts"], float)
        assert ev["event"] == "my_event"
        assert ev["data"]["msg"] == "hello"

    def test_checkpoint_state(self):
        state = {
            "session_id": "chk-sess",
            "node": "thinker",
            "confidence": 0.85,
            "lane": "main",
            "reasoning": {"chosen_skill": "research"},
            "status": "completed",
            "history": [{"step": 1}],
            "final_output": "hello world",
        }
        checkpoint_state("thinker", state)
        trace = get_trace("chk-sess")
        assert len(trace) == 1
        ev = trace[0]
        assert ev["event"] == "checkpoint:thinker"
        assert ev["data"]["node"] == "thinker"
        assert ev["data"]["confidence"] == 0.85
        assert ev["data"]["lane"] == "main"

    def test_checkpoint_state_none(self):
        checkpoint_state("thinker", None)
        assert get_trace("any") == []

    def test_checkpoint_state_without_reasoning(self):
        state = {"session_id": "cr-sess", "node": "critic", "status": "done"}
        checkpoint_state("critic", state)
        trace = get_trace("cr-sess")
        assert len(trace) == 1
        assert trace[0]["data"]["node"] == "critic"

    def test_checkpoint_non_dict_reasoning(self):
        state = {"session_id": "bd", "reasoning": "just a string", "node": "n"}
        checkpoint_state("n", state)
        trace = get_trace("bd")
        assert trace[0]["data"]["node"] == "n"

    def test_log_event_with_otel_disabled_does_not_crash(self):
        session = "otel-off"
        log_event("plain_event", {"session_id": session})
        trace = get_trace(session)
        assert len(trace) == 1
        assert trace[0]["event"] == "plain_event"


class TestConnectionPool:
    """Verify connection reuse and lifecycle."""

    def test_connection_reuse_in_same_thread(self):
        conn1 = _get_conn()
        conn2 = _get_conn()
        assert conn1 is conn2

    def test_connections_tracked_globally(self):
        _get_conn()
        assert len(_all_connections) == 1
        _get_conn()
        assert len(_all_connections) == 1

    def test_different_threads_different_connections(self):
        conns = []

        def capture():
            conns.append(_get_conn())

        t = threading.Thread(target=capture)
        t.start()
        t.join()

        main_conn = _get_conn()
        assert main_conn is not conns[0]

    def test_close_connections_clears_set(self):
        _get_conn()
        _close_connections()
        assert len(_all_connections) == 0

    def test_after_close_new_connection_works(self):
        import tools.tracing as tracing_mod

        _get_conn()
        _close_connections()
        if hasattr(tracing_mod._local, "conn"):
            del tracing_mod._local.conn
        conn = _get_conn()
        assert conn is not None
        log_event("after_close", {"session_id": "test"})
        assert len(get_trace("test")) == 1


class TestConcurrentWrites:
    """Multiple threads writing to the same DB simultaneously."""

    TOTAL = 100
    THREADS = 5

    def test_concurrent_writes(self):
        session = "concurrent"

        def writer(offset):
            for i in range(self.TOTAL // self.THREADS):
                log_event("conc", {"session_id": session, "index": offset + i})

        threads = []
        for t_id in range(self.THREADS):
            start = t_id * (self.TOTAL // self.THREADS)
            t = threading.Thread(target=writer, args=(start,))
            threads.append(t)
            t.start()
            time.sleep(0.05)  # stagger to avoid SQLite WAL stampede on Windows
        for t in threads:
            t.join()

        trace = get_trace(session)
        assert len(trace) == self.TOTAL
        indices = sorted(e["data"]["index"] for e in trace)
        assert indices == list(range(self.TOTAL))

    def test_concurrent_writes_multiple_sessions(self):
        def writer(session, count):
            for i in range(count):
                log_event("ev", {"session_id": session, "i": i})

        threads = [
            threading.Thread(target=writer, args=("sess-A", 50)),
            threading.Thread(target=writer, args=("sess-B", 50)),
        ]
        for t in threads:
            t.start()
            time.sleep(0.05)
        for t in threads:
            t.join()

        assert len(get_trace("sess-A")) == 50
        assert len(get_trace("sess-B")) == 50
        assert sorted(list_sessions()) == ["sess-A", "sess-B"]

    def test_concurrent_writes_no_data_corruption(self):
        session = "corruption-test"

        def writer(idx):
            log_event("ev", {"session_id": session, "idx": idx, "payload": "x" * 100})

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
            time.sleep(0.05)
        for t in threads:
            t.join()

        trace = get_trace(session)
        assert len(trace) == 5
        for ev in trace:
            assert ev["data"]["payload"] == "x" * 100
            assert isinstance(ev["data"]["idx"], int)
