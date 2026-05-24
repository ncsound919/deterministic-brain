# Phase 5 — Full Distributed Mode

**Date:** 2026-05-22
**Status:** Draft
**Version:** 1.0

## Overview

Transform the deterministic brain from a single-process, file-backed monolith into a horizontally scalable distributed system. Add PostgreSQL for shared persistent storage, Redis for caching/pub-sub/task-queue, and multi-worker uvicorn for concurrent request handling.

Cutover is gated by `DISTRIBUTED_MODE=1` env var. When unset, the system falls back to existing SQLite/memory behavior — zero config change for local development.

---

## Architecture

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ Uvicorn     │  │ Uvicorn     │  │ Uvicorn     │
│ Worker 1    │  │ Worker 2    │  │ Worker N    │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────┬───┴────────────────┘
                    │
          ┌─────────▼─────────┐
          │   Load Balancer   │
          │   (nginx/haproxy) │
          └─────────┬─────────┘
                    │
       ┌────────────┼────────────┐
       │            │            │
┌──────▼─────┐ ┌───▼────┐ ┌────▼──────┐
│ PostgreSQL │ │ Redis  │ │ File      │
│ (storage)  │ │(cache, │ │ System    │
│            │ │ pubsub,│ │ (fallback)│
│            │ │ queue) │ │           │
└────────────┘ └────────┘ └───────────┘
```

### Services

| Service | Image | Purpose | When Needed |
|---------|-------|---------|-------------|
| PostgreSQL 16 | `postgres:16-alpine` | Persistent storage (traces, sessions, tasks, sovereign state) | `DISTRIBUTED_MODE=1` |
| Redis 7 | `redis:7-alpine` | Cache, pub/sub event bus, task queue, cross-worker metrics | `DISTRIBUTED_MODE=1` |
| Uvicorn (N workers) | `deterministic-brain` | API server, multiple workers for concurrency | Always |

---

## Pillar 5A — PostgreSQL Backend

### New File: `tools/postgres.py`

Central PostgreSQL connection pool manager.

```python
"""PostgreSQL connection pool for distributed mode.

Provides a singleton ThreadedConnectionPool that all components
use when DISTRIBUTED_MODE=1. Graceful fallback when unavailable.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_DISTRIBUTED = os.environ.get("DISTRIBUTED_MODE", "").lower() in ("1", "true", "yes")

class PostgresPool:
    """Thread-safe PostgreSQL connection pool with auto-schema init."""

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
            dsn = dsn or os.environ.get(
                "PG_DSN",
                "postgresql://brain:brain@localhost:5432/braindb"
            )
            self._pool = ThreadedConnectionPool(2, 20, dsn=dsn)
            self._init_schema()
            self._available = True
            logger.info("PostgreSQL pool ready: %s", dsn)
            return True
        except Exception as e:
            logger.warning("PostgreSQL unavailable, using SQLite fallback: %s", e)
            return False

    def _init_schema(self):
        """Create schemas and tables if they don't exist."""
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
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
                cur.execute("CREATE SCHEMA IF NOT EXISTS pg_state")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pg_state.sessions (
                        session_id TEXT PRIMARY KEY,
                        data JSONB,
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute("CREATE SCHEMA IF NOT EXISTS pg_scheduler")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pg_scheduler.tasks (
                        name TEXT PRIMARY KEY,
                        data JSONB,
                        enabled BOOLEAN DEFAULT true
                    )
                """)
                cur.execute("CREATE SCHEMA IF NOT EXISTS pg_sovereign")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pg_sovereign.store (
                        key TEXT PRIMARY KEY,
                        value JSONB,
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
            conn.commit()
        finally:
            self._pool.putconn(conn)

    @property
    def available(self) -> bool:
        return self._available

    def execute(self, query: str, params: tuple = ()) -> list:
        """Execute a query and return all rows."""
        if not self._available:
            raise RuntimeError("PostgreSQL not available")
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if cur.description:
                    return cur.fetchall()
                conn.commit()
                return []
        finally:
            self._pool.putconn(conn)

    def execute_many(self, query: str, params_list: list) -> None:
        """Execute a query for multiple parameter sets."""
        if not self._available:
            raise RuntimeError("PostgreSQL not available")
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                from psycopg2.extras import execute_values
                execute_values(cur, query, params_list)
            conn.commit()
        finally:
            self._pool.putconn(conn)


_pg_pool: Optional[PostgresPool] = None

def get_pg_pool() -> PostgresPool:
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = PostgresPool()
        _pg_pool.connect()
    return _pg_pool
```

### 5A.1 — Tracing Backend (`tools/tracing.py`)

Replace SQLite `_get_conn()` with PostgreSQL when available:

```python
def _get_backend():
    """Get the appropriate backend (PostgreSQL or SQLite)."""
    if _DISTRIBUTED:
        pg = get_pg_pool()
        if pg.available:
            return pg
    return _get_sqlite_conn()
```

`log_event()` becomes:
```python
def log_event(event: str, data: dict) -> None:
    backend = _get_backend()
    if isinstance(backend, PostgresPool):
        backend.execute(
            "INSERT INTO pg_traces.events (ts, event, data) VALUES (%s, %s, %s)",
            (time.time(), event, json.dumps(data, default=str)),
        )
    else:
        # existing SQLite path
        backend.execute(...)
```

`get_trace()` and `list_sessions()` follow the same pattern — try PostgreSQL first, fall back to SQLite.

### 5A.2 — State Manager Backend (`brain/state_manager.py`)

Add a PostgreSQL-backed implementation alongside existing file-based:

```python
def _save_state_pg(self, session_id: str, data: dict) -> bool:
    pg = get_pg_pool()
    pg.execute(
        """INSERT INTO pg_state.sessions (session_id, data, updated_at)
           VALUES (%s, %s::jsonb, NOW())
           ON CONFLICT (session_id)
           DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()""",
        (session_id, json.dumps(data, default=str)),
    )
    return True
```

CRUD operations check `_DISTRIBUTED` flag and route to PostgreSQL or file backend.

### 5A.3 — Scheduler Backend (`features/scheduler.py`)

Replace JSON file persistence with PostgreSQL when available:

```python
def _save_pg(self):
    if not _DISTRIBUTED:
        return
    pg = get_pg_pool()
    for name, task in self._tasks.items():
        pg.execute(
            "INSERT INTO pg_scheduler.tasks (name, data, enabled) VALUES (%s, %s::jsonb, %s) "
            "ON CONFLICT (name) DO UPDATE SET data = EXCLUDED.data, enabled = EXCLUDED.enabled",
            (name, json.dumps(task.to_dict()), task.enabled),
        )
```

### 5A.4 — Dashboard Backend (`tools/dashboard.py`)

Read from PostgreSQL when available instead of SQLite:

```python
def recent_events(self, n=50):
    if _DISTRIBUTED:
        pg = get_pg_pool()
        rows = pg.execute(
            "SELECT ts, event, data FROM pg_traces.events ORDER BY ts DESC LIMIT %s", (n,)
        )
        return [{"ts": r[0], "event": r[1], "data": r[2]} for r in rows]
    # existing SQLite path
    ...
```

---

## Pillar 5B — Redis Integration

### New File: `tools/redis_client.py`

```python
"""Redis client for distributed caching, pub/sub, and task queue.

Gated by DISTRIBUTED_MODE=1. Graceful fallback to in-memory.
"""
import os
import json
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_DISTRIBUTED = os.environ.get("DISTRIBUTED_MODE", "").lower() in ("1", "true", "yes")

class RedisClient:
    """Redis connection manager with in-memory fallback."""

    def __init__(self):
        self._redis = None
        self._available = False
        # In-memory fallback
        self._cache: Dict[str, Any] = {}
        self._pubsub_callbacks: Dict[str, List[Callable]] = {}

    def connect(self, url: Optional[str] = None) -> bool:
        if not _DISTRIBUTED:
            return False
        try:
            import redis as redis_mod
            url = url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            self._redis = redis_mod.from_url(url, decode_responses=True)
            self._redis.ping()
            self._available = True
            logger.info("Redis connected: %s", url)
            return True
        except Exception as e:
            logger.warning("Redis unavailable, using in-memory fallback: %s", e)
            return False

    @property
    def available(self) -> bool:
        return self._available

    # Cache operations
    def cache_get(self, key: str) -> Optional[str]:
        if self._available:
            return self._redis.get(key)
        return self._cache.get(key)

    def cache_set(self, key: str, value: str, ttl: int = 60) -> None:
        if self._available:
            self._redis.setex(key, ttl, value)
        else:
            self._cache[key] = value

    def cache_delete(self, key: str) -> None:
        if self._available:
            self._redis.delete(key)
        else:
            self._cache.pop(key, None)

    def cache_scan_delete(self, prefix: str) -> None:
        """Delete all keys with a given prefix."""
        if self._available:
            for key in self._redis.scan_iter(f"{prefix}*"):
                self._redis.delete(key)
        else:
            self._cache = {k: v for k, v in self._cache.items() if not k.startswith(prefix)}

    # Pub/Sub operations
    def publish(self, channel: str, message: str) -> None:
        if self._available:
            self._redis.publish(channel, message)
        for cb in self._pubsub_callbacks.get(channel, []):
            try:
                cb(message)
            except Exception:
                pass

    def subscribe(self, channel: str, callback: Callable) -> None:
        if self._available:
            pubsub = self._redis.pubsub()
            pubsub.subscribe(**{channel: lambda m: callback(m["data"])})
        self._pubsub_callbacks.setdefault(channel, []).append(callback)

    # Task queue operations
    def enqueue(self, queue: str, task: dict) -> None:
        payload = json.dumps(task)
        if self._available:
            self._redis.lpush(queue, payload)

    def dequeue(self, queue: str, timeout: int = 5) -> Optional[dict]:
        if self._available:
            result = self._redis.brpop(queue, timeout=timeout)
            if result:
                return json.loads(result[1])
        return None


_redis_client: Optional[RedisClient] = None

def get_redis() -> RedisClient:
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
        _redis_client.connect()
    return _redis_client
```

### 5B.1 — Cache Backend (`api/server.py`)

Modify `CacheManager` to delegate to Redis when available:

```python
class CacheManager:
    def __init__(self, max_size: int = 500):
        self._store: Dict[str, Dict] = {}
        self._max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        redis = get_redis()
        if redis.available:
            val = redis.cache_get(key)
            return json.loads(val) if val else None
        # fallback to in-memory
        ...

    def set(self, key: str, data: Any, ttl: int = 60):
        redis = get_redis()
        if redis.available:
            redis.cache_set(key, json.dumps(data, default=str), ttl)
            return
        # fallback to in-memory
        ...

    def invalidate_prefix(self, prefix: str):
        redis = get_redis()
        if redis.available:
            redis.cache_scan_delete(prefix)
            return
        # fallback to in-memory
        ...
```

### 5B.2 — Event Bus Backend (`orchestration/event_bus.py`)

Modify `EventBus.emit()` to publish to Redis when available:

```python
def emit(self, event_type: str, **data) -> None:
    # Always do in-memory publish
    ...
    # Also publish to Redis for cross-worker delivery
    redis = get_redis()
    if redis.available:
        redis.publish(f"event:{event_type}", json.dumps(data, default=str))
```

### 5B.3 — Metrics Backend (`tools/metrics.py`)

Collect cross-worker metrics via Redis sorted sets:

```python
def record_request(self, route: str, elapsed_ms: float, status_code: int) -> None:
    redis = get_redis()
    if redis.available:
        redis.cache_set(f"metric:count:{route}:{int(time.time() / 60)}", "1", ttl=120)
    # Also keep in-memory for local aggregation
    ...
```

### 5B.4 — Task Queue (`tools/task_queue.py`)

New module for background task processing:

```python
class TaskQueue:
    """Distributed task queue using Redis lists."""

    def enqueue(self, queue_name: str, task: Callable, *args, **kwargs) -> None:
        redis = get_redis()
        payload = {"task": task.__name__, "args": args, "kwargs": kwargs}
        redis.enqueue(queue_name, payload)

    def worker(self, queue_name: str):
        """Run in a background thread: polls for tasks and executes them."""
        redis = get_redis()
        while True:
            task_data = redis.dequeue(queue_name, timeout=5)
            if task_data:
                self._execute(task_data)
```

---

## Pillar 5C — Multi-Worker State

### 5C.1 — Uvicorn Workers (`main.py`)

```python
if args.serve:
    import uvicorn
    import os
    port = int(os.environ.get("API_PORT", 8000))
    workers = int(os.environ.get("UVICORN_WORKERS", "1"))
    if workers > 1 and not os.environ.get("DISTRIBUTED_MODE"):
        logger.warning("Multiple workers require DISTRIBUTED_MODE=1")
        workers = 1
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=port,
        workers=workers,
        reload=False,
    )
```

### 5C.2 — Distributed Locking (`brain/state_manager.py`)

Use `SELECT ... FOR UPDATE` for safe concurrent session writes:

```python
def update_state(self, updates: Dict[str, Any]) -> bool:
    if _DISTRIBUTED:
        pg = get_pg_pool()
        if pg.available:
            # Lock the session row, update, release
            pg.execute("BEGIN")
            pg.execute("SELECT data FROM pg_state.sessions WHERE session_id = %s FOR UPDATE", (sid,))
            pg.execute("UPDATE pg_state.sessions SET data = %s::jsonb, updated_at = NOW() WHERE session_id = %s",
                       (json.dumps(new_data), sid))
            pg.execute("COMMIT")
            return True
    # fallback to file-based
    ...
```

---

## Pillar 5D — Infrastructure

### 5D.1 — Docker Compose (`docker-compose.yml`)

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: brain
      POSTGRES_PASSWORD: brain
      POSTGRES_DB: braindb
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U brain"]
      interval: 5s

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s

  brain:
    build: .
    environment:
      DISTRIBUTED_MODE: "1"
      PG_DSN: "postgresql://brain:brain@postgres:5432/braindb"
      REDIS_URL: "redis://redis:6379/0"
      UVICORN_WORKERS: "4"
    ports: ["8000:8000"]
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
```

### 5D.2 — Migration Script (`scripts/migrate_to_distributed.py`)

```python
"""Migration script: transfer SQLite/JSON data to PostgreSQL.

Idempotent — safe to re-run.
"""
def migrate_traces():
    """Copy all trace events from SQLite to PostgreSQL."""
    from tools.tracing import list_sessions, get_trace
    pg = get_pg_pool()
    sessions = list_sessions()
    for sid in sessions:
        events = get_trace(sid)
        for ev in events:
            pg.execute(
                "INSERT INTO pg_traces.events (ts, event, data) VALUES (%s, %s, %s::jsonb) "
                "ON CONFLICT DO NOTHING",
                (ev["ts"], ev["event"], json.dumps(ev["data"])),
            )

def migrate_sessions():
    """Copy session state JSON files to PostgreSQL."""
    from brain.state_manager import get_state_manager
    sm = get_state_manager()
    sessions = sm.list_sessions(limit=10000)
    pg = get_pg_pool()
    for s in sessions:
        data = sm.load_session(s["session_id"])
        if data:
            pg.execute(
                "INSERT INTO pg_state.sessions (session_id, data) VALUES (%s, %s::jsonb) "
                "ON CONFLICT (session_id) DO NOTHING",
                (s["session_id"], json.dumps(data)),
            )
```

### 5D.3 — Health Checks

In `api/server.py`, add a startup check that probes PostgreSQL + Redis:

```python
@app.on_event("startup")
async def check_distributed_services():
    if os.environ.get("DISTRIBUTED_MODE"):
        pg = get_pg_pool()
        redis = get_redis()
        if not pg.available:
            logger.warning("DISTRIBUTED_MODE=1 but PostgreSQL unavailable — falling back to SQLite")
        if not redis.available:
            logger.warning("DISTRIBUTED_MODE=1 but Redis unavailable — falling back to in-memory")
```

Add `GET /system/backends` endpoint showing current backend status.

---

## Execution Order & Task Breakdown

```
Pillar 5A (PostgreSQL)
├── 5A.0: Create tools/postgres.py — connection pool + schema init
├── 5A.1: Wire tracing.py → pg_traces.events (read/write)
├── 5A.2: Wire state_manager.py → pg_state.sessions (CRUD)
├── 5A.3: Wire scheduler.py → pg_scheduler.tasks (persist/load)
└── 5A.4: Wire dashboard.py → pg_traces.events (read)

Pillar 5B (Redis)
├── 5B.0: Create tools/redis_client.py — connection + cache/pubsub/queue
├── 5B.1: Wire CacheManager → Redis cache
├── 5B.2: Wire EventBus → Redis pub/sub
├── 5B.3: Wire MetricsCollector → Redis counters
└── 5B.4: Create tools/task_queue.py — background task worker

Pillar 5C (Multi-Worker)
├── 5C.1: Update main.py — multi-worker uvicorn config
└── 5C.2: Add distributed locking to state_manager

Pillar 5D (Infrastructure)
├── 5D.1: Update docker-compose.yml — postgres + redis services
├── 5D.2: Create scripts/migrate_to_distributed.py
└── 5D.3: Add health check endpoint + startup probes
```

## Success Criteria

1. All 162 existing tests pass unchanged (`DISTRIBUTED_MODE` unset)
2. With `DISTRIBUTED_MODE=1` + PostgreSQL/Redis configured:
   - `log_event()` → stored in `pg_traces.events`
   - `get_trace()` → reads from `pg_traces.events`
   - State manager CRUD → `pg_state.sessions`
   - Scheduler tasks → `pg_scheduler.tasks`
   - Cache operations → Redis
   - EventBus emit → Redis pub/sub channels
3. Multi-worker uvicorn serves concurrent requests without session conflicts
4. Migration script copies all SQLite data to PostgreSQL
5. System starts gracefully when PostgreSQL/Redis are unavailable
6. New `GET /system/backends` shows active backend configuration
