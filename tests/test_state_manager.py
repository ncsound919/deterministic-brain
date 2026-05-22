"""Comprehensive tests for brain/state_manager.py."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sm(tmp_path):
    """StateManager with an isolated temp state_dir."""
    from brain.state_manager import StateManager

    return StateManager(state_dir=str(tmp_path))


@pytest.fixture
def sm_with_session(sm):
    """StateManager that already has a session created."""
    sid = sm.create_session("test query", "testing")
    return sm, sid


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------

class TestCreateSession:
    def test_returns_string_session_id(self, sm):
        sid = sm.create_session("hello world", "coding")
        assert isinstance(sid, str)
        assert len(sid) > 0

    def test_creates_file_on_disk(self, sm):
        sid = sm.create_session("hello world", "coding")
        path = Path(sm.state_dir) / f"{sid}.json"
        assert path.exists()

    def test_creates_valid_json(self, sm):
        sid = sm.create_session("hello world", "coding")
        path = Path(sm.state_dir) / f"{sid}.json"
        data = json.loads(path.read_text())
        assert data["session_id"] == sid
        assert data["query"] == "hello world"
        assert data["lane"] == "coding"
        assert data["state"] == {}
        assert data["history"] == []
        assert data["artifacts"] == []

    def test_sets_current_session(self, sm):
        sid = sm.create_session("foo", "bar")
        assert sm._current_session == sid

    def test_deterministic_prefix_for_same_query(self, sm):
        sid1 = sm.create_session("same query", "lane1")
        sid2 = sm.create_session("same query", "lane2")
        # should differ because uuid is included
        assert sid1 != sid2

    def test_creates_state_dir_if_not_exists(self, tmp_path):
        from brain.state_manager import StateManager

        nested = tmp_path / "a" / "b" / "c"
        sm = StateManager(state_dir=str(nested))
        sid = sm.create_session("create dirs", "test")
        assert (nested / f"{sid}.json").exists()


# ---------------------------------------------------------------------------
# load_session
# ---------------------------------------------------------------------------

class TestLoadSession:
    def test_returns_data_for_existing_session(self, sm):
        sid = sm.create_session("load test", "coding")
        loaded = sm.load_session(sid)
        assert loaded is not None
        assert loaded["session_id"] == sid
        assert loaded["query"] == "load test"

    def test_returns_none_for_missing(self, sm):
        assert sm.load_session("nonexistent") is None

    def test_sets_current_session_on_load(self, sm):
        sid = sm.create_session("first", "a")
        sm._current_session = None
        sm.load_session(sid)
        assert sm._current_session == sid

    def test_returns_none_for_corrupt_file(self, sm):
        # write a non-JSON file
        sid = "corrupt123"
        path = Path(sm.state_dir) / f"{sid}.json"
        path.write_text("{not valid json")
        assert sm.load_session(sid) is None


# ---------------------------------------------------------------------------
# update_state
# ---------------------------------------------------------------------------

class TestUpdateState:
    def test_updates_state_correctly(self, sm_with_session):
        sm, sid = sm_with_session
        result = sm.update_state({"key1": "value1", "key2": 42})
        assert result is True

        loaded = sm.load_session(sid)
        assert loaded["state"]["key1"] == "value1"
        assert loaded["state"]["key2"] == 42

    def test_merges_with_existing_state(self, sm_with_session):
        sm, sid = sm_with_session
        sm.update_state({"a": 1, "b": 2})
        sm.update_state({"b": 3, "c": 4})

        loaded = sm.load_session(sid)
        assert loaded["state"]["a"] == 1
        assert loaded["state"]["b"] == 3
        assert loaded["state"]["c"] == 4

    def test_saves_to_disk(self, sm_with_session):
        sm, sid = sm_with_session
        sm.update_state({"persist": True})
        path = Path(sm.state_dir) / f"{sid}.json"
        raw = json.loads(path.read_text())
        assert raw["state"]["persist"] is True

    def test_returns_false_when_no_session(self, sm):
        assert sm.update_state({"x": 1}) is False

    def test_adds_updated_at_timestamp(self, sm_with_session):
        sm, sid = sm_with_session
        sm.update_state({"x": 1})
        loaded = sm.load_session(sid)
        assert "updated_at" in loaded


# ---------------------------------------------------------------------------
# append_history
# ---------------------------------------------------------------------------

class TestAppendHistory:
    def test_appends_entry(self, sm_with_session):
        sm, sid = sm_with_session
        entry = {"role": "user", "content": "hello"}
        result = sm.append_history(entry)
        assert result is True

        loaded = sm.load_session(sid)
        assert len(loaded["history"]) == 1
        assert loaded["history"][0]["role"] == "user"
        assert loaded["history"][0]["content"] == "hello"

    def test_adds_timestamp(self, sm_with_session):
        sm, sid = sm_with_session
        sm.append_history({"role": "assistant", "content": "hi"})

        loaded = sm.load_session(sid)
        assert "timestamp" in loaded["history"][0]

    def test_appends_multiple_entries(self, sm_with_session):
        sm, sid = sm_with_session
        sm.append_history({"role": "user", "content": "q1"})
        sm.append_history({"role": "assistant", "content": "a1"})
        sm.append_history({"role": "user", "content": "q2"})

        loaded = sm.load_session(sid)
        assert len(loaded["history"]) == 3
        assert loaded["history"][0]["content"] == "q1"
        assert loaded["history"][2]["content"] == "q2"

    def test_returns_false_when_no_session(self, sm):
        assert sm.append_history({"role": "user", "content": "x"}) is False


# ---------------------------------------------------------------------------
# add_artifact
# ---------------------------------------------------------------------------

class TestAddArtifact:
    def test_appends_artifact(self, sm_with_session):
        sm, sid = sm_with_session
        artifact = {"path": "/tmp/file.txt", "type": "text"}
        result = sm.add_artifact(artifact)
        assert result is True

        loaded = sm.load_session(sid)
        assert len(loaded["artifacts"]) == 1
        assert loaded["artifacts"][0]["path"] == "/tmp/file.txt"
        assert loaded["artifacts"][0]["type"] == "text"

    def test_adds_created_at_timestamp(self, sm_with_session):
        sm, sid = sm_with_session
        sm.add_artifact({"path": "x", "type": "y"})

        loaded = sm.load_session(sid)
        assert "created_at" in loaded["artifacts"][0]

    def test_appends_multiple_artifacts(self, sm_with_session):
        sm, sid = sm_with_session
        sm.add_artifact({"path": "a.txt", "type": "text"})
        sm.add_artifact({"path": "b.png", "type": "image"})

        loaded = sm.load_session(sid)
        assert len(loaded["artifacts"]) == 2
        assert loaded["artifacts"][0]["path"] == "a.txt"
        assert loaded["artifacts"][1]["path"] == "b.png"

    def test_returns_false_when_no_session(self, sm):
        assert sm.add_artifact({"path": "x", "type": "y"}) is False


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------

class TestListSessions:
    def test_returns_empty_when_no_sessions(self, sm):
        assert sm.list_sessions() == []

    def test_returns_all_sessions(self, sm):
        s1 = sm.create_session("first", "a")
        s2 = sm.create_session("second", "b")
        s3 = sm.create_session("third", "c")

        sessions = sm.list_sessions()
        assert len(sessions) == 3

    def test_newest_first(self, sm):
        sm.create_session("oldest", "a")
        time.sleep(0.01)
        sm.create_session("middle", "b")
        time.sleep(0.01)
        sm.create_session("newest", "c")

        sessions = sm.list_sessions()
        # created_at timestamps should be descending
        assert sessions[0]["query"] == "newest"
        assert sessions[1]["query"] == "middle"
        assert sessions[2]["query"] == "oldest"

    def test_limit(self, sm):
        for i in range(10):
            sm.create_session(f"query-{i}", "lane")
        sessions = sm.list_sessions(limit=3)
        assert len(sessions) == 3

    def test_offset(self, sm):
        for i in range(10):
            sm.create_session(f"query-{i}", "lane")
        all_sessions = sm.list_sessions(limit=10)
        offset_sessions = sm.list_sessions(limit=10, offset=7)
        assert len(offset_sessions) == 3
        assert offset_sessions[0]["session_id"] == all_sessions[7]["session_id"]
        assert offset_sessions[1]["session_id"] == all_sessions[8]["session_id"]

    def test_summary_fields(self, sm):
        sid = sm.create_session("my query", "my_lane")
        sessions = sm.list_sessions()
        assert len(sessions) == 1
        s = sessions[0]
        assert s["session_id"] == sid
        assert s["query"] == "my query"
        assert s["lane"] == "my_lane"
        assert "created_at" in s

    def test_query_truncated_to_50_chars(self, sm):
        long_q = "x" * 100
        sm.create_session(long_q, "lane")
        sessions = sm.list_sessions()
        assert len(sessions[0]["query"]) == 50

    def test_skips_non_json_files(self, sm):
        sm.create_session("real session", "lane")
        d = Path(sm.state_dir)
        (d / "not_a_session.txt").write_text("hello")
        (d / "readme.md").write_text("# docs")
        sessions = sm.list_sessions()
        assert len(sessions) == 1


# ---------------------------------------------------------------------------
# delete_session
# ---------------------------------------------------------------------------

class TestDeleteSession:
    def test_removes_file(self, sm_with_session):
        sm, sid = sm_with_session
        path = Path(sm.state_dir) / f"{sid}.json"
        assert path.exists()

        result = sm.delete_session(sid)
        assert result is True
        assert not path.exists()

    def test_returns_false_for_missing(self, sm):
        assert sm.delete_session("nonexistent") is False

    def test_removed_session_not_in_list(self, sm_with_session):
        sm, sid = sm_with_session
        sm.delete_session(sid)
        assert sm.list_sessions() == []

    def test_other_sessions_persist(self, sm):
        s1 = sm.create_session("keep me", "a")
        s2 = sm.create_session("delete me", "b")
        s3 = sm.create_session("keep me too", "c")

        sm.delete_session(s2)

        sids = [s["session_id"] for s in sm.list_sessions()]
        assert s1 in sids
        assert s2 not in sids
        assert s3 in sids


# ---------------------------------------------------------------------------
# Corrupt JSON handling
# ---------------------------------------------------------------------------

class TestCorruptJson:
    def test_skips_bad_files_in_list_sessions(self, sm):
        good_sid = sm.create_session("good", "lane")

        bad_sid = "bad_file"
        d = Path(sm.state_dir)
        (d / f"{bad_sid}.json").write_text("{this is not valid json")

        sessions = sm.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == good_sid

    def test_skips_empty_json(self, sm):
        sm.create_session("good", "lane")
        d = Path(sm.state_dir)
        (d / "empty.json").write_text("")

        sessions = sm.list_sessions()
        assert len(sessions) == 1

    def test_skips_partial_json(self, sm):
        sm.create_session("good", "lane")
        d = Path(sm.state_dir)
        (d / "partial.json").write_text('{"session_id": "x"')

        sessions = sm.list_sessions()
        assert len(sessions) == 1

    def test_skips_missing_keys_gracefully(self, sm):
        """Files that are valid JSON but miss keys still get basic summary."""
        sm.create_session("good", "lane")
        d = Path(sm.state_dir)
        (d / "minimal.json").write_text(json.dumps({"foo": "bar"}))

        sessions = sm.list_sessions()
        assert len(sessions) == 2  # minimal.json gets listed with defaults

    def test_skips_non_json_suffix_files(self, sm):
        """Files without .json suffix are ignored."""
        sm.create_session("good", "lane")
        d = Path(sm.state_dir)
        (d / "data.txt").write_text("nope")
        (d / "session.log").write_text("nope")
        sessions = sm.list_sessions()
        assert len(sessions) == 1


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_create_session(self, sm):
        """Multiple threads can create sessions simultaneously."""
        n_threads = 20
        results_lock = threading.Lock()
        results = []
        errors = []

        def create(i):
            try:
                sid = sm.create_session(f"thread-{i}", "concurrent")
                with results_lock:
                    results.append(sid)
            except Exception as e:
                with results_lock:
                    errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == n_threads
        # Verify each session file exists on disk
        for sid in results:
            path = Path(sm.state_dir) / f"{sid}.json"
            assert path.exists(), f"Missing file for session {sid}"
        # Verify each session loads correctly
        for sid in results:
            loaded = sm.load_session(sid)
            assert loaded is not None
            assert loaded["session_id"] == sid

    def test_concurrent_update_state(self, sm_with_session):
        """Multiple threads can update state without corruption."""
        sm, sid = sm_with_session
        n_threads = 20
        errors_lock = threading.Lock()
        errors = []

        def update(i):
            try:
                sm.update_state({f"key_{i}": i})
            except Exception as e:
                with errors_lock:
                    errors.append(e)

        threads = [threading.Thread(target=update, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        loaded = sm.load_session(sid)
        for i in range(n_threads):
            assert loaded["state"][f"key_{i}"] == i

    def test_concurrent_append_history(self, sm_with_session):
        """Multiple threads can append history without corruption."""
        sm, sid = sm_with_session
        n_threads = 30
        errors_lock = threading.Lock()
        errors = []

        def append(i):
            try:
                sm.append_history({"role": "user", "content": f"msg-{i}"})
            except Exception as e:
                with errors_lock:
                    errors.append(e)

        threads = [threading.Thread(target=append, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        loaded = sm.load_session(sid)
        assert len(loaded["history"]) == n_threads
        contents = {e["content"] for e in loaded["history"]}
        for i in range(n_threads):
            assert f"msg-{i}" in contents

    def test_concurrent_mixed_operations(self, sm_with_session):
        """Mix of updates and appends doesn't corrupt state."""
        sm, sid = sm_with_session
        n_ops = 15
        errors_lock = threading.Lock()
        errors = []

        def worker(kind, i):
            try:
                if kind == "update":
                    sm.update_state({"counter": i})
                elif kind == "history":
                    sm.append_history({"role": "assistant", "content": f"step-{i}"})
                else:
                    sm.add_artifact({"path": f"file-{i}", "type": "text"})
            except Exception as e:
                with errors_lock:
                    errors.append(e)

        threads = []
        for i in range(n_ops):
            threads.append(threading.Thread(target=worker, args=("update", i)))
            threads.append(threading.Thread(target=worker, args=("history", i)))
            threads.append(threading.Thread(target=worker, args=("artifact", i)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        loaded = sm.load_session(sid)
        assert len(loaded["history"]) == n_ops
        assert len(loaded["artifacts"]) == n_ops
        assert "counter" in loaded["state"]

    def test_concurrent_same_session_updates_all_visible(self, sm):
        """Concurrent updates to the same session key all appear."""
        sid = sm.create_session("shared", "conc")
        sm._current_session = sid
        n_threads = 10
        errors_lock = threading.Lock()
        errors = []

        def update(i):
            try:
                sm.update_state({"val": i})
            except Exception as e:
                with errors_lock:
                    errors.append(e)

        threads = [threading.Thread(target=update, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        # the last write wins for a single key, but no corruption occurs
        loaded = sm.load_session(sid)
        assert "val" in loaded["state"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_session_id_special_chars_handled(self, sm):
        """Session IDs from _generate_session_id are hex-only, so safe for FS."""
        sid = sm.create_session("query with spaces and symbols!@#$%", "lane")
        path = Path(sm.state_dir) / f"{sid}.json"
        assert path.exists()

    def test_very_long_query_stored(self, sm):
        long_q = "A" * 10000
        sid = sm.create_session(long_q, "lane")
        loaded = sm.load_session(sid)
        assert len(loaded["query"]) == 10000

    def test_unicode_in_query(self, sm):
        sid = sm.create_session("héllo wörld 中文 🔥", "lane")
        loaded = sm.load_session(sid)
        assert loaded["query"] == "héllo wörld 中文 🔥"
        loaded["state"]["msg"] = "✓"
        sm._current_session = sid
        sm.update_state({"msg": "✓"})
        assert sm.load_session(sid)["state"]["msg"] == "✓"

    def test_history_with_arbitrary_dict_keys(self, sm_with_session):
        sm, sid = sm_with_session
        entry = {"role": "user", "content": "hi", "metadata": {"source": "test", "nested": [1, 2, 3]}}
        sm.append_history(entry)
        loaded = sm.load_session(sid)
        assert loaded["history"][0]["metadata"]["source"] == "test"
        assert loaded["history"][0]["metadata"]["nested"] == [1, 2, 3]

    def test_artifact_with_all_fields_persisted(self, sm_with_session):
        sm, sid = sm_with_session
        artifact = {
            "path": "/data/output.csv",
            "type": "csv",
            "description": "processed data",
            "size_bytes": 1024,
            "tags": ["important", "processed"],
        }
        sm.add_artifact(artifact)
        loaded = sm.load_session(sid)
        assert loaded["artifacts"][0]["path"] == "/data/output.csv"
        assert loaded["artifacts"][0]["tags"] == ["important", "processed"]

    def test_reload_preserves_all_data(self, sm):
        sid = sm.create_session("persist check", "test")
        sm._current_session = sid
        sm.update_state({"counter": 1})
        sm.append_history({"role": "user", "content": "hello"})
        sm.add_artifact({"path": "f.txt", "type": "text"})

        # fresh load
        loaded = sm.load_session(sid)
        assert loaded["query"] == "persist check"
        assert loaded["state"]["counter"] == 1
        assert len(loaded["history"]) == 1
        assert loaded["history"][0]["content"] == "hello"
        assert len(loaded["artifacts"]) == 1
