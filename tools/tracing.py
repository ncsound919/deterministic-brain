"""Audit log / session tracing — SQLite, no external service.

Functions:
    log_event: Record a trace event.
    list_sessions: List all distinct session IDs.
    get_trace: Retrieve all events for a session.
    checkpoint_state: Persist a LangGraph node checkpoint.
"""
import os
import json
import sqlite3
import threading
import time
import atexit
from typing import Optional, Any

_DB_PATH = None
_db_init_lock = threading.Lock()
_local = threading.local()
_all_connections: set[sqlite3.Connection] = set()
_all_conn_lock = threading.Lock()
_schema_initialized = False

# Optional OpenTelemetry support — gated by TOOLS_OTEL_ENABLED=1
_OTEL_ENABLED = os.environ.get("TOOLS_OTEL_ENABLED", "").lower() in ("1", "true", "yes")

if _OTEL_ENABLED:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        _otel_available = True
    except ImportError:
        _otel_available = False
else:
    _otel_available = False

_DISTRIBUTED = os.environ.get("DISTRIBUTED_MODE", "").lower() in ("1", "true", "yes")

def _setup_otel_tracer() -> Optional[Any]:
    """Initialize OpenTelemetry tracer provider if enabled and available."""
    if not _OTEL_ENABLED or not _otel_available:
        return None
    provider = TracerProvider()
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("deterministic-brain")

_tracer = _setup_otel_tracer()

def _get_db_path():
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = os.environ.get("TRACE_DB", "traces.db")
    return _DB_PATH

def _get_conn() -> sqlite3.Connection:
    """Get or create a thread-local SQLite connection."""
    if not hasattr(_local, 'conn') or _local.conn is None:
        conn = sqlite3.connect(_get_db_path(), timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        global _schema_initialized
        if not _schema_initialized:
            with _db_init_lock:
                if not _schema_initialized:
                    conn.execute(
                        "CREATE TABLE IF NOT EXISTS events "
                        "(id INTEGER PRIMARY KEY, ts REAL, event TEXT, data TEXT)"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_events_session "
                        "ON events(json_extract(data, '$.session_id'))"
                    )
                    conn.commit()
                    _schema_initialized = True
        with _all_conn_lock:
            _all_connections.add(conn)
        _local.conn = conn
    return _local.conn


def _close_connections() -> None:
    """Close all tracked connections on shutdown."""
    with _all_conn_lock:
        for conn in list(_all_connections):
            try:
                conn.close()
            except Exception:
                pass
        _all_connections.clear()

atexit.register(_close_connections)

def log_event(event: str, data: dict) -> None:
    """Record a trace event. Creates an OpenTelemetry span when tracing is enabled."""
    if _tracer is not None:
        with _tracer.start_as_current_span(event) as span:
            for k, v in data.items():
                span.set_attribute(k, str(v))
            span.set_attribute("event_type", event)
    if _DISTRIBUTED:
        try:
            from tools.postgres import get_pg_pool
            pg = get_pg_pool()
            if pg.available:
                pg.execute(
                    "INSERT INTO pg_traces.events (ts, event, data) VALUES (%s, %s, %s::jsonb)",
                    (time.time(), event, json.dumps(data, default=str)),
                )
                return
        except Exception:
            pass
    conn = _get_conn()
    conn.execute(
        "INSERT INTO events (ts, event, data) VALUES (?,?,?)",
        (time.time(), event, json.dumps(data, default=str)),
    )
    conn.commit()

def list_sessions() -> list:
    if _DISTRIBUTED:
        try:
            from tools.postgres import get_pg_pool
            pg = get_pg_pool()
            if pg.available:
                rows = pg.execute(
                    "SELECT DISTINCT data->>'session_id' FROM pg_traces.events "
                    "WHERE data->>'session_id' IS NOT NULL"
                )
                return [r[0] for r in rows if r[0]]
        except Exception:
            pass
    conn = _get_conn()
    rows = conn.execute(
        "SELECT DISTINCT json_extract(data,'$.session_id') FROM events "
        "WHERE json_extract(data,'$.session_id') IS NOT NULL"
    ).fetchall()
    return [r[0] for r in rows if r[0]]

def get_trace(session_id: str) -> list:
    if _DISTRIBUTED:
        try:
            from tools.postgres import get_pg_pool
            pg = get_pg_pool()
            if pg.available:
                rows = pg.execute(
                    "SELECT ts, event, data FROM pg_traces.events "
                    "WHERE data->>'session_id' = %s ORDER BY ts",
                    (session_id,),
                )
                return [{"ts": r[0], "event": r[1], "data": r[2]} for r in rows]
        except Exception:
            pass
    conn = _get_conn()
    rows = conn.execute(
        "SELECT ts, event, data FROM events "
        "WHERE json_extract(data, '$.session_id') = ? ORDER BY ts",
        (session_id,),
    ).fetchall()
    return [{"ts": r[0], "event": r[1], "data": json.loads(r[2])} for r in rows]

def checkpoint_state(node: str, state: dict) -> None:
    """Persist a LangGraph node checkpoint as a trace event.

    Called by each node in langgraph_app.py after execution.
    Stores a snapshot of the state relevant to the given node.
    """
    if state is None:
        return
    reasoning = state.get("reasoning") or {}
    if not isinstance(reasoning, dict):
        reasoning = {}
    log_event(f"checkpoint:{node}", {
        "session_id": state.get("session_id"),
        "node": node,
        "confidence": state.get("confidence"),
        "lane": state.get("lane"),
        "chosen_skill": reasoning.get("chosen_skill"),
        "status": state.get("status"),
        "history": state.get("history", [])[-5:],
        "final_output_preview": str(state.get("final_output", ""))[:200],
    })
