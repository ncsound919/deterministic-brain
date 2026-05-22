"""Session memory — plain dict, no vector store, no LLM."""
from __future__ import annotations
import time
from typing import Dict


def init_state(query: str, task: Dict) -> Dict:
    if isinstance(task, str):
        lane = task
        task_dict = {"task": task}
    else:
        lane = task.get("task", "unknown") if isinstance(task, dict) else "unknown"
        task_dict = task
    import hashlib
    session_id = hashlib.sha256(f"{query}:{lane}".encode()).hexdigest()[:16]
    return {
        "session_id":   session_id,
        "created_at":   time.time(),
        "query":        query,
        "task":         task_dict,
        "lane":         lane,
        "history":      [],
        "retrieved_contexts": [],
        "candidate_artifacts": [],
        "verification_results": [],
        "confidence":   0.0,
        "status":       "pending",
        "working_memory": {},
        "tool_budget":  100,
    }
