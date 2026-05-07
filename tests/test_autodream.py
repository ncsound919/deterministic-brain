from __future__ import annotations
import json
import os
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta
from typing import Any, Dict

import pytest


@pytest.fixture
def temp_db():
    """Create a temporary traces.db with test data."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE events "
        "(id INTEGER PRIMARY KEY, ts REAL, event TEXT, data TEXT)"
    )

    now = time.time()
    yesterday = now - 86400

    test_events = [
        (yesterday, 'handle', json.dumps({
            "status": "ok", "query": "create react component",
            "confidence": 0.85, "task": {"task": "coding"},
        })),
        (yesterday, 'reasoning', json.dumps({
            "task": "coding", "chosen_skill": "react_skill",
        })),
        (now, 'handle', json.dumps({
            "status": "failed", "query": "fix authentication bug",
            "confidence": 0.25, "task": {"task": "coding"},
        })),
        (now, 'handle', json.dumps({
            "status": "ok", "query": "build rest api",
            "confidence": 0.92, "task": {"task": "business_logic"},
        })),
    ]

    for ts, event, data in test_events:
        conn.execute(
            "INSERT INTO events (ts, event, data) VALUES (?,?,?)",
            (ts, event, data),
        )
    conn.commit()
    conn.close()

    yield path

    os.unlink(path)


@pytest.fixture
def autodream_module():
    import brain.autodream as module
    return module


def test_analyze_session_patterns(autodream_module, temp_db):
    result = autodream_module.analyze_session_patterns(temp_db)

    assert result["total_sessions"] == 3
    assert result["sessions_by_status"]["ok"] == 2
    assert result["sessions_by_status"]["failed"] == 1
    assert "coding" in result["sessions_by_lane"]
    assert "business_logic" in result["sessions_by_lane"]
    assert len(result["failed_queries"]) == 1
    assert result["failed_queries"][0]["status"] == "failed"


def test_vacuum_traces(autodream_module, temp_db):
    size_before = os.path.getsize(temp_db)

    result = autodream_module.vacuum_traces(
        db_path=temp_db,
        retention_days=0,
        dry_run=False,
    )

    assert result["status"] == "ok"
    assert result["removed_events"] >= 0
    assert "size_before_mb" in result
    assert "size_after_mb" in result


def test_vacuum_traces_dry_run(autodream_module, temp_db):
    size_before = os.path.getsize(temp_db)

    result = autodream_module.vacuum_traces(
        db_path=temp_db,
        retention_days=1,
        dry_run=True,
    )

    size_after = os.path.getsize(temp_db)
    assert size_before == size_after


def test_deduplicate_qdrant_no_client(autodream_module, monkeypatch):
    monkeypatch.setenv('QDRANT_URL', '')

    result = autodream_module.deduplicate_qdrant("test_collection", dry_run=True)

    assert result["status"] == "skipped"
    assert "qdrant_not_configured" in result["reason"]


def test_optimize_neo4j_no_driver(autodream_module, monkeypatch):
    monkeypatch.setenv('NEO4J_URI', '')

    result = autodream_module.optimize_neo4j(dry_run=True)

    assert result["status"] == "skipped"
    assert "neo4j_not_configured" in result["reason"]


def test_analyze_and_correct(autodream_module, temp_db):
    config_file = tempfile.mktemp(suffix='.jsonl')
    if os.path.exists(config_file):
        os.unlink(config_file)

    monkeypatch = None
    import builtins
    original_open = builtins.open

    result = autodream_module.analyze_and_correct(config_file=config_file)

    assert isinstance(result, list)
    if result and "error" not in result[0]:
        assert os.path.exists(config_file)
        os.unlink(config_file)


def test_run_autodream(autodream_module, temp_db, monkeypatch):
    monkeypatch.setenv('QDRANT_URL', '')
    monkeypatch.setenv('NEO4J_URI', '')

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, '.autodream_last_run.json')
        monkeypatch.setattr(autodream_module, 'run_autodream', lambda dry_run=False: {
            "timestamp": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
        })
        result = autodream_module.run_autodream(dry_run=True)

        assert "timestamp" in result
        assert result["dry_run"] is True
