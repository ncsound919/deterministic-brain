"""Audit log / session tracing — SQLite, no external service."""
from __future__ import annotations
import json
import os
import sqlite3
import time

DB_PATH = os.environ.get("TRACE_DB", "traces.db")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS events "
        "(id INTEGER PRIMARY KEY, ts REAL, event TEXT, data TEXT)"
    )
    conn.commit()
    return conn


def log_event(event: str, data: dict) -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO events (ts, event, data) VALUES (?,?,?)",
        (time.time(), event, json.dumps(data, default=str)),
    )
    conn.commit()
    conn.close()


def list_sessions() -> list:
    conn = _conn()
    rows = conn.execute(
        "SELECT DISTINCT json_extract(data,'$.session_id') FROM events "
        "WHERE json_extract(data,'$.session_id') IS NOT NULL"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


def get_trace(session_id: str) -> list:
    conn = _conn()
    rows = conn.execute(
        "SELECT ts, event, data FROM events "
        "WHERE data LIKE ? ORDER BY ts",
        (f'%{session_id}%',),
    ).fetchall()
    conn.close()
    return [{"ts": r[0], "event": r[1], "data": json.loads(r[2])} for r in rows]
