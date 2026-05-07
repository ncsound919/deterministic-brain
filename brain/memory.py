"""Session memory — plain dict, no vector store, no LLM."""
from __future__ import annotations
import uuid
import time
from typing import Dict


def init_state(query: str, task: Dict) -> Dict:
    return {
        "session_id":   str(uuid.uuid4()),
        "created_at":   time.time(),
        "query":        query,
        "task":         task,
        "lane":         task.get("task", "unknown"),
        "history":      [],
        "artifacts":    [],
        "audit_results":[],
        "score":        0.0,
        "status":       "pending",
        "final_output": {},
    }
