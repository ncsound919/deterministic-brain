#!/usr/bin/env python3
"""Migration script: transfer existing SQLite/JSON data to PostgreSQL.

Idempotent — safe to re-run. Skips records that already exist in PostgreSQL.

Usage:
    python scripts/migrate_to_distributed.py

Requires DISTRIBUTED_MODE=1 and PostgreSQL to be running.
"""
import os
import json
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def check_prerequisites() -> bool:
    """Verify DISTRIBUTED_MODE=1 and PostgreSQL is reachable."""
    if os.environ.get("DISTRIBUTED_MODE", "").lower() not in ("1", "true", "yes"):
        logger.error("DISTRIBUTED_MODE must be set to 1")
        return False
    from tools.postgres import get_pg_pool
    pg = get_pg_pool()
    if not pg.available:
        logger.error("PostgreSQL is not available. Check PG_DSN.")
        return False
    logger.info("PostgreSQL connection OK")
    return True


def migrate_traces():
    """Copy trace events from SQLite to PostgreSQL."""
    from tools.tracing import list_sessions, get_trace
    from tools.postgres import get_pg_pool
    pg = get_pg_pool()
    sessions = list_sessions()
    logger.info("Migrating %d sessions of trace data...", len(sessions))
    total = 0
    for sid in sessions:
        events = get_trace(sid)
        for ev in events:
            try:
                pg.execute(
                    "INSERT INTO pg_traces.events (ts, event, data) VALUES (%s, %s, %s::jsonb) "
                    "ON CONFLICT DO NOTHING",
                    (ev["ts"], ev["event"], json.dumps(ev["data"], default=str)),
                )
                total += 1
            except Exception as e:
                logger.warning("Failed to migrate trace event: %s", e)
    logger.info("Migrated %d trace events", total)
    return total


def migrate_sessions():
    """Copy session state from JSON files to PostgreSQL."""
    from brain.state_manager import get_state_manager
    from tools.postgres import get_pg_pool
    pg = get_pg_pool()
    sm = get_state_manager()
    sessions = sm.list_sessions(limit=10000)
    logger.info("Migrating %d sessions...", len(sessions))
    total = 0
    for s in sessions:
        try:
            session_id = s["session_id"]
            data = sm.load_session(session_id)
            if data:
                pg.execute(
                    "INSERT INTO pg_state.sessions (session_id, data) VALUES (%s, %s::jsonb) "
                    "ON CONFLICT (session_id) DO NOTHING",
                    (session_id, json.dumps(data, default=str)),
                )
                total += 1
        except Exception as e:
            logger.warning("Failed to migrate session %s: %s", s.get("session_id", "?"), e)
    logger.info("Migrated %d sessions", total)
    return total


def migrate_scheduler_tasks():
    """Copy scheduler tasks from JSON file to PostgreSQL."""
    import json as _json
    from pathlib import Path
    from tools.postgres import get_pg_pool
    pg = get_pg_pool()
    storage_path = os.environ.get("SCHEDULER_STORAGE_PATH", ".scheduler_tasks.json")
    path = Path(storage_path)
    if not path.exists():
        logger.info("No scheduler tasks file found at %s", storage_path)
        return 0
    with open(path) as f:
        tasks_data = _json.load(f)
    total = 0
    for task_dict in tasks_data:
        try:
            name = task_dict.get("name", "")
            if not name:
                continue
            pg.execute(
                "INSERT INTO pg_scheduler.tasks (name, data, enabled) VALUES (%s, %s::jsonb, %s) "
                "ON CONFLICT (name) DO NOTHING",
                (name, _json.dumps(task_dict), task_dict.get("enabled", True)),
            )
            total += 1
        except Exception as e:
            logger.warning("Failed to migrate task: %s", e)
    logger.info("Migrated %d scheduler tasks", total)
    return total


def main():
    logger.info("Starting migration to distributed mode...")
    if not check_prerequisites():
        sys.exit(1)

    trace_count = migrate_traces()
    session_count = migrate_sessions()
    task_count = migrate_scheduler_tasks()

    logger.info("Migration complete!")
    logger.info("  Traces:     %d", trace_count)
    logger.info("  Sessions:   %d", session_count)
    logger.info("  Tasks:      %d", task_count)
    logger.info("\nSet DISTRIBUTED_MODE=1 and restart the brain to use PostgreSQL/Redis.")


if __name__ == "__main__":
    main()
