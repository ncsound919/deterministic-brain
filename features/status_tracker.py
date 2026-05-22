import json
import os
from typing import Dict, Any
from features.sovereign_persistence import get_persistence

class StatusTracker:
    _instance = None
    _lock = None

    def __new__(cls):
        if cls._lock is None:
            import threading
            cls._lock = threading.Lock()
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(StatusTracker, cls).__new__(cls)
                    cls._instance.persistence = get_persistence()
                    
                    # Load initial state or set defaults
                    saved_status = cls._instance.persistence.get_state("system_status")
                    if saved_status:
                        cls._instance.status = saved_status
                    else:
                        cls._instance.status = {
                            "agents": {
                                "draymond": "online",
                                "blackmind": "standby",
                                "omni": "online",
                                "streetcode": "online"
                            },
                            "systems": {
                                "superalgos": "healthy",
                                "benchmarks": "optimal",
                                "content_engine": "ready",
                                "betting_pipeline": "active"
                            },
                            "last_pulse": {}
                        }
                        cls._instance.persistence.set_state("system_status", cls._instance.status)
        return cls._instance

    def _save(self):
        self.persistence.set_state("system_status", self.status)

    def set_agent_status(self, agent_id: str, status: str):
        if "agents" not in self.status:
            self.status["agents"] = {}
        self.status["agents"][agent_id] = status
        if "last_pulse" not in self.status:
            self.status["last_pulse"] = {}
        self.status["last_pulse"][agent_id] = "now"
        self._save()

    def get_agent_status(self, agent_id: str) -> str:
        return self.status.get("agents", {}).get(agent_id, "offline")

    def set_system_status(self, system_id: str, status: str):
        if "systems" not in self.status:
            self.status["systems"] = {}
        self.status["systems"][system_id] = status
        self._save()

    def get_system_status(self, system_id: str) -> str:
        return self.status.get("systems", {}).get(system_id, "unknown")

    def get_all(self) -> Dict[str, Any]:
        return self.status

_TRACKER = None

def get_status_tracker():
    global _TRACKER
    if _TRACKER is None:
        _TRACKER = StatusTracker()
    return _TRACKER
