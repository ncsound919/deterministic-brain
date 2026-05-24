"""State Manager — persistent state storage for agent sessions."""
from __future__ import annotations
import os
import json
import hashlib
import logging
import threading
import uuid
import tempfile
from typing import Any, Dict, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DISTRIBUTED = os.environ.get("DISTRIBUTED_MODE", "").lower() in ("1", "true", "yes")

DEFAULT_STATE_DIR = os.path.expanduser("~/.deterministic-brain/state")


class StateManager:
    """Manages persistent state for agent sessions."""

    def __init__(self, state_dir: Optional[str] = None):
        self.state_dir = state_dir or DEFAULT_STATE_DIR
        os.makedirs(self.state_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._current_session: Optional[str] = None

    def _get_session_path(self, session_id: str) -> Path:
        """Get file path for session state."""
        return Path(self.state_dir) / f"{session_id}.json"

    def create_session(self, query: str, lane: str) -> str:
        """Create a new session and return its ID.
        
        Args:
            query: Initial query for the session
            lane: Initial lane/route
        
        Returns:
            Session ID string
        """
        session_data = {
            "session_id": self._generate_session_id(query),
            "created_at": datetime.utcnow().isoformat(),
            "query": query,
            "lane": lane,
            "state": {},
            "history": [],
            "artifacts": [],
        }
        session_id = session_data["session_id"]
        if _DISTRIBUTED:
            try:
                from tools.postgres import get_pg_pool
                pg = get_pg_pool()
                if pg.available:
                    import json as _json
                    pg.execute(
                        "INSERT INTO pg_state.sessions (session_id, data) VALUES (%s, %s::jsonb) "
                        "ON CONFLICT (session_id) DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()",
                        (session_id, _json.dumps(session_data, default=str)),
                    )
                    self._current_session = session_id
                    logger.info(f"Created PG session: {session_id}")
                    return session_id
            except Exception:
                pass
        with self._lock:
            self._save_session(session_id, session_data)
            self._current_session = session_id
            logger.info(f"Created session: {session_id}")
            return session_id

    def _generate_session_id(self, query: str) -> str:
        """Generate deterministic session ID from query."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        raw = f"{query}:{timestamp}:{uuid.uuid4().hex}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _load_from_pg(self, session_id: str) -> Optional[Dict]:
        from tools.postgres import get_pg_pool
        pg = get_pg_pool()
        rows = pg.execute(
            "SELECT data FROM pg_state.sessions WHERE session_id = %s",
            (session_id,),
        )
        if rows:
            data = rows[0][0]
            return data if isinstance(data, dict) else json.loads(data)
        return None

    def _update_in_pg(self, session_id: str, update_fn) -> bool:
        """Lock, modify, and save a session in a single PG transaction."""
        try:
            from tools.postgres import get_pg_pool
            import json as _json
            pg = get_pg_pool()
            if not pg.available:
                return False
            conn = pg._pool.getconn()
            try:
                conn.autocommit = False
                with conn.cursor() as cur:
                    cur.execute("SELECT data FROM pg_state.sessions WHERE session_id = %s FOR UPDATE", (session_id,))
                    row = cur.fetchone()
                    if not row:
                        conn.rollback()
                        return False
                    data = row[0] if isinstance(row[0], dict) else _json.loads(row[0])
                    update_fn(data)
                    cur.execute(
                        "INSERT INTO pg_state.sessions (session_id, data, updated_at) VALUES (%s, %s::jsonb, NOW()) "
                        "ON CONFLICT (session_id) DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()",
                        (session_id, _json.dumps(data, default=str)),
                    )
                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                logger.warning("PG update failed for session=%s: %s", session_id, e)
                return False
            finally:
                pg._pool.putconn(conn)
        except Exception as e:
            logger.warning("PG pool unavailable for session=%s: %s", session_id, e)
            return False

    def _save_to_pg(self, session_id: str, data: Dict) -> None:
        from tools.postgres import get_pg_pool
        pg = get_pg_pool()
        pg.execute(
            "INSERT INTO pg_state.sessions (session_id, data, updated_at) VALUES (%s, %s::jsonb, NOW()) "
            "ON CONFLICT (session_id) DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()",
            (session_id, json.dumps(data, default=str)),
        )

    def _save_session(self, session_id: str, data: Dict[str, Any]) -> None:
        """Save session data to disk."""
        path = self._get_session_path(session_id)
        fd, tmp_path = tempfile.mkstemp(dir=self.state_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            os.unlink(tmp_path)
            logger.warning("Failed to save session %s", session_id)
            raise

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session state.
        
        Args:
            session_id: Session ID to load
        
        Returns:
            Session data dict or None if not found
        """
        if _DISTRIBUTED:
            try:
                data = self._load_from_pg(session_id)
                if data is not None:
                    self._current_session = session_id
                    return data
            except Exception:
                pass
        path = self._get_session_path(session_id)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            self._current_session = session_id
            logger.info(f"Loaded session: {session_id}")
            return data
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    def update_state(self, updates: Dict[str, Any]) -> bool:
        """Update current session state.
        
        Args:
            updates: Dict of key-value pairs to update
        
        Returns:
            True if successful
        """
        with self._lock:
            session_id = self._current_session
            if _DISTRIBUTED and session_id:
                def _do_update(data):
                    data["state"].update(updates)
                    data["updated_at"] = datetime.utcnow().isoformat()
                if self._update_in_pg(session_id, _do_update):
                    return True
            if not session_id:
                return False
            session = self.load_session(session_id)
            if not session:
                return False
            session["state"].update(updates)
            session["updated_at"] = datetime.utcnow().isoformat()
            self._save_session(session_id, session)
            return True

    def append_history(self, entry: Dict[str, Any]) -> bool:
        """Append an entry to session history.
        
        Args:
            entry: History entry dict
        
        Returns:
            True if successful
        """
        with self._lock:
            session_id = self._current_session
            if _DISTRIBUTED and session_id:
                def _do_update(data):
                    entry["timestamp"] = datetime.utcnow().isoformat()
                    data["history"].append(entry)
                if self._update_in_pg(session_id, _do_update):
                    return True
            if not session_id:
                return False
            session = self.load_session(session_id)
            if not session:
                return False
            entry["timestamp"] = datetime.utcnow().isoformat()
            session["history"].append(entry)
            self._save_session(session_id, session)
            return True

    def add_artifact(self, artifact: Dict[str, Any]) -> bool:
        """Add an artifact to the session.
        
        Args:
            artifact: Artifact dict with keys like path, type, description
        
        Returns:
            True if successful
        """
        if _DISTRIBUTED and self._current_session:
            def _do_update(data):
                artifact["created_at"] = datetime.utcnow().isoformat()
                data["artifacts"].append(artifact)
            if self._update_in_pg(self._current_session, _do_update):
                return True
        with self._lock:
            if not self._current_session:
                return False
            session = self.load_session(self._current_session)
            if not session:
                return False
            artifact["created_at"] = datetime.utcnow().isoformat()
            session["artifacts"].append(artifact)
            self._save_session(self._current_session, session)
            return True

    def list_sessions(self, limit: int = 10, offset: int = 0) -> list[Dict[str, str]]:
        """List recent sessions.
        
        Args:
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip
        
        Returns:
            List of session summaries
        """
        if _DISTRIBUTED:
            try:
                from tools.postgres import get_pg_pool
                pg = get_pg_pool()
                if pg.available:
                    rows = pg.execute(
                        "SELECT data->>'session_id', data->>'created_at', data->>'query', data->>'lane' "
                        "FROM pg_state.sessions ORDER BY (data->>'created_at') DESC LIMIT %s OFFSET %s",
                        (limit, offset),
                    )
                    return [
                        {"session_id": r[0], "created_at": r[1] or "unknown",
                         "query": (r[2] or "")[:50], "lane": r[3] or "unknown"}
                        for r in rows
                    ]
            except Exception:
                pass
        sessions = []
        for entry in os.scandir(self.state_dir):
            if not entry.name.endswith(".json"):
                continue
            try:
                with open(entry.path) as f:
                    data = json.load(f)
                sessions.append({
                    "session_id": data.get("session_id", entry.name[:-5]),
                    "created_at": data.get("created_at", "unknown"),
                    "query": data.get("query", "")[:50],
                    "lane": data.get("lane", "unknown"),
                })
            except Exception:
                logger.warning("Failed to load session file: %s", entry.path)
                continue
        sessions.sort(key=lambda s: s["created_at"], reverse=True)
        return sessions[offset:offset + limit]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.
        
        Args:
            session_id: Session ID to delete
        
        Returns:
            True if deleted
        """
        if _DISTRIBUTED:
            try:
                from tools.postgres import get_pg_pool
                pg = get_pg_pool()
                if pg.available:
                    pg.execute("DELETE FROM pg_state.sessions WHERE session_id = %s", (session_id,))
                    return True
            except Exception:
                pass
        with self._lock:
            path = self._get_session_path(session_id)
            if path.exists():
                path.unlink()
                logger.info(f"Deleted session: {session_id}")
                return True
            return False


_local = threading.local()


def get_state_manager(state_dir: Optional[str] = None) -> StateManager:
    """Get or create the thread-local state manager."""
    if not hasattr(_local, 'manager') or _local.manager is None:
        _local.manager = StateManager(state_dir)
    return _local.manager


def save_state(session_id: str, state: Dict[str, Any]) -> bool:
    """Save state for a session."""
    sm = get_state_manager()
    if not sm._current_session:
        sm._current_session = session_id
    return sm.update_state(state)


def load_state(session_id: str) -> Optional[Dict[str, Any]]:
    """Load state for a session."""
    sm = get_state_manager()
    session = sm.load_session(session_id)
    return session.get("state") if session else None