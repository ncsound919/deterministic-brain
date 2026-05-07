"""State Manager — persistent state storage for agent sessions."""
from __future__ import annotations
import os
import json
import hashlib
import logging
from typing import Any, Dict, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STATE_DIR = os.path.expanduser("~/.deterministic-brain/state")


class StateManager:
    """Manages persistent state for agent sessions."""

    def __init__(self, state_dir: Optional[str] = None):
        self.state_dir = state_dir or DEFAULT_STATE_DIR
        os.makedirs(self.state_dir, exist_ok=True)
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
        self._save_session(session_id, session_data)
        self._current_session = session_id
        logger.info(f"Created session: {session_id}")
        return session_id

    def _generate_session_id(self, query: str) -> str:
        """Generate deterministic session ID from query."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        raw = f"{query}:{timestamp}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _save_session(self, session_id: str, data: Dict[str, Any]) -> None:
        """Save session data to disk."""
        path = self._get_session_path(session_id)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session state from disk.
        
        Args:
            session_id: Session ID to load
        
        Returns:
            Session data dict or None if not found
        """
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
        if not self._current_session:
            return False
        session = self.load_session(self._current_session)
        if not session:
            return False
        session["state"].update(updates)
        session["updated_at"] = datetime.utcnow().isoformat()
        self._save_session(self._current_session, session)
        return True

    def append_history(self, entry: Dict[str, Any]) -> bool:
        """Append an entry to session history.
        
        Args:
            entry: History entry dict
        
        Returns:
            True if successful
        """
        if not self._current_session:
            return False
        session = self.load_session(self._current_session)
        if not session:
            return False
        entry["timestamp"] = datetime.utcnow().isoformat()
        session["history"].append(entry)
        self._save_session(self._current_session, session)
        return True

    def add_artifact(self, artifact: Dict[str, Any]) -> bool:
        """Add an artifact to the session.
        
        Args:
            artifact: Artifact dict with keys like path, type, description
        
        Returns:
            True if successful
        """
        if not self._current_session:
            return False
        session = self.load_session(self._current_session)
        if not session:
            return False
        artifact["created_at"] = datetime.utcnow().isoformat()
        session["artifacts"].append(artifact)
        self._save_session(self._current_session, session)
        return True

    def list_sessions(self, limit: int = 10) -> list[Dict[str, str]]:
        """List recent sessions.
        
        Args:
            limit: Maximum number of sessions to return
        
        Returns:
            List of session summaries
        """
        sessions = []
        for path in Path(self.state_dir).glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                sessions.append({
                    "session_id": data.get("session_id", path.stem),
                    "created_at": data.get("created_at", "unknown"),
                    "query": data.get("query", "")[:50],
                    "lane": data.get("lane", "unknown"),
                })
            except Exception:
                continue
        sessions.sort(key=lambda s: s["created_at"], reverse=True)
        return sessions[:limit]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.
        
        Args:
            session_id: Session ID to delete
        
        Returns:
            True if deleted
        """
        path = self._get_session_path(session_id)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted session: {session_id}")
            return True
        return False


_global_state_manager: Optional[StateManager] = None


def get_state_manager(state_dir: Optional[str] = None) -> StateManager:
    """Get or create the global state manager."""
    global _global_state_manager
    if _global_state_manager is None:
        _global_state_manager = StateManager(state_dir)
    return _global_state_manager


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