"""Seed logging and replay for reproducibility in deterministic dialogue."""
from __future__ import annotations
import os
import json
import hashlib
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_LOG_DIR = os.path.expanduser("~/.deterministic-brain/dialogue_logs")


@dataclass
class DialogueEvent:
    """A single event in the dialogue pipeline."""
    timestamp: str
    layer: str
    event_type: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    seed: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DialogueSession:
    """Complete dialogue session log."""
    session_id: str
    start_time: str
    end_time: Optional[str] = None
    seed: Optional[int] = None
    events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SeededRandom:
    """Seeded random number generator for reproducible randomness."""

    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        self._rng = self._create_rng(seed)

    def _create_rng(self, seed: Optional[int]):
        """Create random generator with seed."""
        import random
        rng = random.Random(seed)
        return rng

    def randint(self, a: int, b: int) -> int:
        """Return random integer in range [a, b]."""
        return self._rng.randint(a, b)

    def choice(self, seq: list) -> Any:
        """Return random choice from sequence."""
        return self._rng.choice(seq)

    def shuffle(self, seq: list) -> list:
        """Shuffle sequence in place."""
        self._rng.shuffle(seq)
        return seq

    def random(self) -> float:
        """Return random float in [0, 1)."""
        return self._rng.random()


class ReproducibilityManager:
    """Manages seed logging and replay for deterministic dialogue."""

    def __init__(self, log_dir: Optional[str] = None):
        self.log_dir = log_dir or DEFAULT_LOG_DIR
        os.makedirs(self.log_dir, exist_ok=True)
        self._current_session: Optional[DialogueSession] = None
        self._seed: Optional[int] = None

    def start_session(self, seed: Optional[int] = None) -> str:
        """Start a new session with optional seed."""
        import uuid
        session_id = hashlib.sha256(f"{datetime.utcnow().isoformat()}{seed}".encode()).hexdigest()[:16]
        
        self._seed = seed
        self._current_session = DialogueSession(
            session_id=session_id,
            start_time=datetime.utcnow().isoformat(),
            seed=seed,
        )
        logger.info(f"Started dialogue session: {session_id} with seed: {seed}")
        return session_id

    def log_event(self, layer: str, event_type: str,
                  input_data: Dict[str, Any], output_data: Dict[str, Any]) -> None:
        """Log an event to the current session."""
        if not self._current_session:
            logger.warning("No active session to log event to")
            return

        event = DialogueEvent(
            timestamp=datetime.utcnow().isoformat(),
            layer=layer,
            event_type=event_type,
            input_data=input_data,
            output_data=output_data,
            seed=self._seed,
        )
        self._current_session.events.append(event.to_dict())

    def end_session(self) -> Optional[str]:
        """End the current session and save to disk."""
        if not self._current_session:
            return None

        self._current_session.end_time = datetime.utcnow().isoformat()

        path = os.path.join(self.log_dir, f"{self._current_session.session_id}.json")
        with open(path, "w") as f:
            json.dump(self._current_session.to_dict(), f, indent=2)

        session_id = self._current_session.session_id
        logger.info(f"Saved dialogue session: {session_id}")
        self._current_session = None
        return session_id

    def load_session(self, session_id: str) -> Optional[DialogueSession]:
        """Load a session from disk."""
        path = os.path.join(self.log_dir, f"{session_id}.json")
        if not os.path.exists(path):
            return None

        with open(path) as f:
            data = json.load(f)
        
        session = DialogueSession(
            session_id=data["session_id"],
            start_time=data["start_time"],
            end_time=data.get("end_time"),
            seed=data.get("seed"),
            events=data.get("events", []),
        )
        return session

    def replay(self, session_id: str) -> List[Dict[str, Any]]:
        """Replay a session and return ordered events."""
        session = self.load_session(session_id)
        if not session:
            return []
        
        return session.events

    def list_sessions(self, limit: int = 10) -> List[Dict[str, str]]:
        """List recent sessions."""
        sessions = []
        for path in Path(self.log_dir).glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                sessions.append({
                    "session_id": data.get("session_id", path.stem),
                    "start_time": data.get("start_time", ""),
                    "seed": data.get("seed"),
                    "event_count": len(data.get("events", [])),
                })
            except Exception:
                continue
        
        sessions.sort(key=lambda s: s["start_time"], reverse=True)
        return sessions[:limit]


_global_manager: Optional[ReproducibilityManager] = None


def get_reproducibility_manager() -> ReproducibilityManager:
    """Get or create global reproducibility manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = ReproducibilityManager()
    return _global_manager


def start_dialogue_session(seed: Optional[int] = None) -> str:
    """Start a new dialogue session."""
    manager = get_reproducibility_manager()
    return manager.start_session(seed)


def log_dialogue_event(layer: str, event_type: str,
                       input_data: Dict[str, Any], output_data: Dict[str, Any]) -> None:
    """Log a dialogue event."""
    manager = get_reproducibility_manager()
    manager.log_event(layer, event_type, input_data, output_data)


def end_dialogue_session() -> Optional[str]:
    """End current dialogue session."""
    manager = get_reproducibility_manager()
    return manager.end_session()


def replay_session(session_id: str) -> List[Dict[str, Any]]:
    """Replay a session."""
    manager = get_reproducibility_manager()
    return manager.replay(session_id)