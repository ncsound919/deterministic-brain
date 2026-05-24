"""AGI Autonomous Operating System - REST API Routes"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/agi", tags=["agi"])

class GoalRequest(BaseModel):
    goal: str
    context: Optional[Dict[str, Any]] = None
    use_probabilistic: bool = False

def _get_aos():
    from agi.integration_example import get_shared_agi_os
    import os
    if os.environ.get("NO_AGI_OS") == "1":
        raise HTTPException(status_code=503, detail="AGI OS is disabled (NO_AGI_OS=1)")
    return get_shared_agi_os()

@router.get("/status")
def get_status() -> Dict:
    """Get the full cognitive and operational status of the AGI Mind."""
    aos = _get_aos()
    return aos.get_system_status()

@router.post("/goal")
def inject_goal(req: GoalRequest) -> Dict:
    """Manually inject a goal into the AGI mind."""
    aos = _get_aos()
    # AGI handles goals synchronously right now in handle_goal, so we can return the result immediately.
    # In a more advanced implementation, this might dispatch to the background.
    result = aos.handle_goal(
        goal=req.goal,
        context=req.context or {},
        use_probabilistic=req.use_probabilistic
    )
    return {"status": "ok", "result": result}

@router.get("/beliefs")
def get_beliefs() -> Dict:
    """Get the active Bayesian beliefs (probabilities)."""
    aos = _get_aos()
    return {"beliefs": aos.probabilistic_agent.get_beliefs_status()}

@router.get("/learning")
def get_learning() -> Dict:
    """Get discovered learned patterns and performance trends."""
    aos = _get_aos()
    return aos.learning_loop.get_learning_status()

@router.get("/scheduler")
def get_scheduler() -> Dict:
    """List registered scheduled tasks, execution history, and adaptive intervals."""
    aos = _get_aos()
    status = aos.scheduler.get_scheduler_status()
    tasks = aos.scheduler.get_task_status()
    return {
        "status": status,
        "tasks": tasks,
        "history": [
            {
                "task_id": r.task_id,
                "success": r.success,
                "duration": r.duration_seconds,
                "timestamp": r.timestamp,
                "error": r.error
            } for r in aos.scheduler.execution_history[-50:]
        ]
    }

@router.post("/scheduler/run/{task_id}")
def run_task(task_id: str) -> Dict:
    """Manually force the execution of a scheduled task."""
    aos = _get_aos()
    task = aos.scheduler.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    result = aos.scheduler.execute_task(task)
    return {
        "status": "ok",
        "task_id": task_id,
        "success": result.success,
        "duration": result.duration_seconds,
        "error": result.error
    }

@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    """Serve the AGI visual monitor dashboard."""
    html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ui", "agi_monitor.html")
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Monitor UI not found: {e}")
