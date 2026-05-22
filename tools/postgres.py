"""PostgreSQL connection pool for distributed mode.

Provides a singleton ThreadedConnectionPool that all components
use when DISTRIBUTED_MODE=1. Graceful fallback when unavailable.
"""
from __future__ import annotations
import os
import json
import threading
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DISTRIBUTED = os.environ.get("DISTRIBUTED_MODE", "").lower() in ("1", "true", "yes")


class PostgresPool:
    """Thread-safe PostgreSQL connection pool with auto-schema init.

    When DISTRIBUTED_MODE=1, connects to PostgreSQL on init.
    When unavailable or DISTRIBUTED_MODE=0, available() returns False.
    """

    def __init__(self):
        self._pool = None
        self._available = False

    def connect(self, dsn: Optional[str] = None) -> bool:
        """Initialize connection pool. Returns True if successful."""
        if not _DISTRIBUTED:
            return False
        try:
            import psycopg2
            from psycopg2.pool import ThreadedConnectionPool
            dsn = dsn or os.environ.get("PG_DSN")
            if not dsn:
                logger.warning("PG_DSN not set; PostgreSQL unavailable")
                return False
            min_conn = int(os.environ.get("PG_MIN_CONN", "2"))
            max_conn = int(os.environ.get("PG_MAX_CONN", "20"))
            self._pool = ThreadedConnectionPool(min_conn, max_conn, dsn=dsn)
            self._init_schema()
            self._available = True
            logger.info("PostgreSQL pool ready: %s", dsn)
            return True
        except Exception as e:
            logger.warning("PostgreSQL unavailable, using SQLite fallback: %s", e)
            return False

    def _init_schema(self) -> None:
        """Create schemas and tables if they don't exist."""
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                # Traces schema
                cur.execute("CREATE SCHEMA IF NOT EXISTS pg_traces")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pg_traces.events (
                        id BIGSERIAL PRIMARY KEY,
                        ts DOUBLE PRECISION,
                        event TEXT,
                        data JSONB
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_events_session
                    ON pg_traces.events ((data->>'session_id'))
                """)
                # State schema
                cur.execute("CREATE SCHEMA IF NOT EXISTS pg_state")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pg_state.sessions (
                        session_id TEXT PRIMARY KEY,
                        data JSONB,
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                # Scheduler schema
                cur.execute("CREATE SCHEMA IF NOT EXISTS pg_scheduler")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pg_scheduler.tasks (
                        name TEXT PRIMARY KEY,
                        data JSONB,
                        enabled BOOLEAN DEFAULT true
                    )
                """)
                # Sovereign schema
                cur.execute("CREATE SCHEMA IF NOT EXISTS pg_sovereign")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pg_sovereign.store (
                        key TEXT PRIMARY KEY,
                        value JSONB,
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                # Cache schema (for PostgreSQL-based cache fallback)
                cur.execute("CREATE SCHEMA IF NOT EXISTS pg_cache")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pg_cache.entries (
                        key TEXT PRIMARY KEY,
                        value JSONB,
                        expires_at TIMESTAMPTZ
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cache_expires
                    ON pg_cache.entries (expires_at)
                """)
            conn.commit()
        finally:
            self._pool.putconn(conn)

    @property
    def available(self) -> bool:
        return self._available

    def execute(self, query: str, params: tuple = ()) -> List[tuple]:
        """Execute a query and return all rows."""
        if not self._available:
            raise RuntimeError("PostgreSQL not available")
        conn = self._pool.getconn()
        committed = False
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if cur.description:
                    return cur.fetchall()
                conn.commit()
                committed = True
                return []
        finally:
            if not committed:
                conn.rollback()
            self._pool.putconn(conn)

    def execute_many(self, query: str, params_list: List[tuple]) -> None:
        """Execute a query for multiple parameter sets."""
        if not self._available:
            raise RuntimeError("PostgreSQL not available")
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                for params in params_list:
                    cur.execute(query, params)
            conn.commit()
        finally:
            self._pool.putconn(conn)

    def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool is not None:
            self._pool.closeall()
            self._available = False


_pg_pool: Optional[PostgresPool] = None
_pg_lock = threading.Lock()


def get_pg_pool() -> PostgresPool:
    """Get or create the global PostgreSQL pool singleton."""
    global _pg_pool
    if _pg_pool is None:
        with _pg_lock:
            if _pg_pool is None:
                _pg_pool = PostgresPool()
                _pg_pool.connect()
    return _pg_pool


def reset_pg_pool() -> None:
    """Reset the pool singleton (for testing)."""
    global _pg_pool
    if _pg_pool is not None:
        _pg_pool.close()
    _pg_pool = None
