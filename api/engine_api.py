"""
Lightweight FastAPI server exposing the HybridDeterministicEngine state
to the Aether Dashboard for real-time visualization.
"""
import json
import os
import time
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from loguru import logger

# We lazily import the engine so the module can be used standalone
_engine = None
_results_bank: List[Dict[str, Any]] = []
_event_log: List[Dict[str, Any]] = []
_lock = threading.Lock()

app = FastAPI(title="Aether Engine API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_engine():
    global _engine
    if _engine is None:
        import sys
        # Ensure project root is on path
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from orchestration.hybrid_engine import HybridDeterministicEngine
        _engine = HybridDeterministicEngine()
    return _engine

def record_event(event_type: str, data: dict):
    with _lock:
        _event_log.append({
            "ts": time.time(),
            "type": event_type,
            "data": data
        })
        # Keep last 200 events
        if len(_event_log) > 200:
            _event_log.pop(0)

def record_result(result: dict):
    with _lock:
        _results_bank.append({
            "ts": time.time(),
            "result": result
        })
        if len(_results_bank) > 100:
            _results_bank.pop(0)

# ─── Models ───────────────────────────────────────────────────────
class ProcessRequest(BaseModel):
    query: str

# ─── Routes ───────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "ts": time.time()}

@app.get("/engine/state")
def engine_state():
    """Full engine snapshot for the dashboard."""
    engine = get_engine()

    # Registered intents
    intents = list(engine.intent_router.routes.keys())

    # Registered schemas
    schemas = list(engine.intent_router.routes.keys())

    # Skills imported count
    skill_count = len(intents)

    # Cron queue from .cron_schedule.json
    cron_tasks = []
    cron_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cron_schedule.json")
    if os.path.exists(cron_path):
        try:
            with open(cron_path, "r", encoding="utf-8") as f:
                cron_data = json.load(f)
            for name, task in cron_data.get("tasks", {}).items():
                cron_tasks.append({
                    "id": name,
                    "skill": task.get("skill", "unknown"),
                    "cron": task.get("cron_expr", ""),
                    "enabled": task.get("enabled", False),
                    "description": task.get("description", "")
                })
        except Exception:
            pass

    with _lock:
        events = list(_event_log[-50:])
        results = list(_results_bank[-30:])

    return {
        "ts": time.time(),
        "engine": {
            "name": "HybridDeterministicEngine",
            "confidence_threshold": engine.confidence_router.threshold,
            "skill_count": skill_count,
            "intents": intents,
        },
        "components": [
            {"name": "ConfidenceRouter", "status": "active", "threshold": engine.confidence_router.threshold},
            {"name": "SemanticLayer", "status": "active", "mode": "regex+micro_llm"},
            {"name": "IntentRouter", "status": "active", "routes": len(intents)},
            {"name": "SchemaRegistry", "status": "active", "schemas": len(schemas)},
            {"name": "SkillImporter", "status": "active", "imported": skill_count},
            {"name": "CLI-Anything", "status": "active", "type": "wrapper"},
            {"name": "ContentCreation", "status": "active", "type": "cron-capable"},
            {"name": "KnowledgeSynthesis", "status": "active", "type": "multi-source"},
        ],
        "cron_queue": cron_tasks,
        "events": events,
        "results": results,
    }

@app.post("/engine/process")
def process_input(req: ProcessRequest):
    """Send a query through the HybridDeterministicEngine."""
    engine = get_engine()
    record_event("input", {"query": req.query})

    try:
        result = engine.process_user_input(req.query)
        record_event("output", {"result": result})
        record_result({"query": req.query, **result})
        return {"status": "ok", "result": result}
    except Exception as e:
        err = {"status": "error", "error": str(e)}
        record_event("error", err)
        return err

@app.get("/engine/events")
def get_events():
    with _lock:
        return {"events": list(_event_log[-50:])}

@app.get("/engine/results")
def get_results():
    with _lock:
        return {"results": list(_results_bank[-30:])}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
