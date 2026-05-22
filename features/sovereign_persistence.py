import sqlite3
import json
import time
import os
import threading
from typing import Dict, Any, List, Optional

DB_PATH = "sovereign.db"

class SovereignPersistence:
    _instance = None
    _instance_lock = threading.RLock()

    def __new__(cls):
        with cls._instance_lock:
            if cls._instance is None:
                obj = super(SovereignPersistence, cls).__new__(cls)
                obj._conn_lock = threading.Lock()
                obj._init_db()
                cls._instance = obj
            return cls._instance

    def _init_db(self):
        try:
            self.conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=5)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at REAL
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL,
                    event_type TEXT,
                    data TEXT
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS skill_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_id TEXT,
                    session_id TEXT,
                    status TEXT,
                    input_data TEXT,
                    output_data TEXT,
                    logs TEXT,
                    ts REAL
                )
            """)
            self.conn.commit()
        except Exception as e:
            import sys
            print(f"SovereignPersistence init failed: {e}", file=sys.stderr, flush=True)
            self._conn = None

    def _ensure_conn(self):
        if not hasattr(self, 'conn') or self.conn is None:
            self._init_db()

    def set_state(self, key: str, value: Any):
        with self._conn_lock:
            self._ensure_conn()
            self.conn.execute(
                "INSERT OR REPLACE INTO state (key, value, updated_at) VALUES (?, ?, ?)",
                (key, json.dumps(value), time.time())
            )
            self.conn.commit()

    def get_state(self, key: str, default: Any = None) -> Any:
        self._ensure_conn()
        row = self.conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        if row:
            return json.loads(row["value"])
        return default

    def log_event(self, event_type: str, data: Dict):
        with self._conn_lock:
            self._ensure_conn()
            self.conn.execute(
                "INSERT INTO events (ts, event_type, data) VALUES (?, ?, ?)",
                (time.time(), event_type, json.dumps(data))
            )
            self.conn.commit()

    def log_skill_execution(self, skill_id: str, session_id: str, status: str, input_data: Dict, output_data: Dict, logs: List[str]):
        with self._conn_lock:
            self._ensure_conn()
            self.conn.execute(
                "INSERT INTO skill_executions (skill_id, session_id, status, input_data, output_data, logs, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (skill_id, session_id, status, json.dumps(input_data), json.dumps(output_data), json.dumps(logs), time.time())
            )
            self.conn.commit()

    def get_recent_events(self, limit: int = 50) -> List[Dict]:
        self._ensure_conn()
        rows = self.conn.execute("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_skill_history(self, skill_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        self._ensure_conn()
        if skill_id:
            rows = self.conn.execute("SELECT * FROM skill_executions WHERE skill_id = ? ORDER BY ts DESC LIMIT ?", (skill_id, limit)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM skill_executions ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

_PERSISTENCE = None

def get_persistence() -> SovereignPersistence:
    global _PERSISTENCE
    if _PERSISTENCE is None:
        _PERSISTENCE = SovereignPersistence()
    return _PERSISTENCE
