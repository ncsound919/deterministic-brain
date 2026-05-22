# Wave 1: Distributed Mode Infrastructure + Test Coverage

## Overview
Two parallel workstreams to close out the remediation plan.

---

## Workstream A: Distributed Mode (Phase 5)

**Status:** PG/Redis infrastructure code exists (`tools/postgres.py`, `tools/redis_client.py`, `tools/tracing.py`, `tools/task_queue.py`, `orchestration/event_bus.py`, `tools/metrics.py`) but:
- State manager still SQLite-only (no PG backend)
- No startup wiring to auto-connect PG/Redis
- No Docker Compose for local distributed dev

### A1 — State Manager PG Backend
**Files:** `brain/state_manager.py`, `tools/postgres.py`
- Add `PostgresStateManager` class or distributed-mode path to `StateManager`
- When `DISTRIBUTED_MODE=1` and PG available, use PG for session persistence
- Keep SQLite path as fallback
- **Verify:** `python -c "from brain.state_manager import get_state_manager; sm = get_state_manager(); print(sm.list_sessions())"` works

### A2 — Lifespan Startup Hook
**Files:** `api/server.py`, `main.py`, optionally `brain/lifespan.py`
- Add lifespan event handler in FastAPI to connect PG + Redis on startup
- Wire CLI `--serve` to also connect PG/Redis when `DISTRIBUTED_MODE=1`
- Log connection status clearly
- **Verify:** Server starts without errors; logs show PG/Redis connection status

### A3 — Docker Compose
**Files:** `docker-compose.distributed.yml`
- PostgreSQL 16 service with persistent volume
- Redis 7 service
- App service with `DISTRIBUTED_MODE=1`, depends on pg + redis
- Health checks for all services
- **Verify:** `docker compose -f docker-compose.distributed.yml up -d` starts cleanly

---

## Workstream B: Test Gap Coverage

### B1 — `test_circuit_breaker.py`
**File:** `tests/test_circuit_breaker.py`
- Test state transitions: closed → open → half_open → closed
- Test threshold, cooldown, window expiration
- Test retry/backoff behavior
- Test decorator `@circuit_breaker`

### B2 — `test_task_queue.py`
**File:** `tests/test_task_queue.py`
- Test register_handler + enqueue synchronous execution
- Test handler not found error
- Test worker start/stop lifecycle
- Test singleton pattern

### B3 — `test_confidence_routing.py`
**File:** `tests/test_confidence_routing.py`
- Test register_route + execute finds route
- Test fallback triggers on low confidence
- Test weight adaptation
- Test status_summary structure

### B4 — `test_session_replay.py`
**File:** `tests/test_session_replay.py`
- Test capture_session with mock trace data
- Test replay yields nodes in order
- Test describe returns expected schema
- Test list_sessions returns list

### B5 — `test_postgres_pool.py`
**File:** `tests/test_postgres_pool.py`
- Test singleton pattern
- Test connect returns False when DISTRIBUTED_MODE=0
- Test available property

### B6 — `test_redis_client.py`
**File:** `tests/test_redis_client.py`
- Test in-memory fallback cache operations
- Test TTL expiration
- Test enqueue/dequeue in fallback mode

### B7 — `test_knowledge_routes.py`
**File:** `tests/test_knowledge_routes.py`
- Test with FastAPI TestClient
- Test GET /knowledge/stats returns 200
- Test POST /knowledge/search with mock

---

## Dependency Graph
```
A2 (lifespan) ─depends on─→ A1 (state manager PG)
A3 (docker-compose) ─independent─
B1–B7 (tests) ─independent, can run in parallel─
```

## Execution Order
1. **B1–B7** first (no infra deps, immediate value)
2. **A1** (state manager PG backend)
3. **A2** (lifespan startup hook)
4. **A3** (Docker Compose)
