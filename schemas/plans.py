from __future__ import annotations
from typing import Any, Dict, List, Literal, TypedDict

class PlannerStep(TypedDict, total=False):
    id: str
    action: str
    inputs: Dict[str, Any]
    expected_output: str

class TaskPlan(TypedDict, total=False):
    planner: Literal['karpathy_interface', 'code_planner', 'browser_planner']
    lane: str
    goal: str
    steps: List[PlannerStep]
