"""
Executive Kernel: AGI Executive Layer
=====================================

The Executive Kernel sits above the Deterministic-Brain components and provides:
- Long-term goal management
- Cross-agent coordination
- Financial oversight
- Agenda enforcement
- Autonomous decision making

This is the "AGI-like" executive layer that turns tactical components into
a strategic autonomous system.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from agi.autonomous_core import AutonomousCore, Observation
from agi.probabilistic_agent import ProbabilisticAgent, DecisionStrategy
from agi.deterministic_executor import DeterministicExecutor, ExecutionPlan
from agi.self_learning_loop import SelfLearningLoop
from agi.autonomous_scheduler import AutonomousScheduler, TaskFrequency, TaskPriority

logger = logging.getLogger(__name__)


class ExecutiveGoalStatus(str, Enum):
    """Status of an executive-level goal."""
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutiveGoal:
    """A long-term goal managed by the Executive Kernel."""
    goal_id: str
    description: str
    priority: int  # 1-5 (1 = highest)
    deadline: Optional[datetime]
    status: ExecutiveGoalStatus = ExecutiveGoalStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    subgoals: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "priority": self.priority,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "subgoals": self.subgoals,
            "dependencies": self.dependencies,
        }


@dataclass
class FinancialSnapshot:
    """Snapshot of financial state for oversight."""
    timestamp: float = field(default_factory=time.time)
    cash_balance: float = 0.0
    monthly_inflow: float = 0.0
    monthly_outflow: float = 0.0
    runway_months: float = 0.0
    anomalies: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cash_balance": self.cash_balance,
            "monthly_inflow": self.monthly_inflow,
            "monthly_outflow": self.monthly_outflow,
            "runway_months": self.runway_months,
            "anomalies": self.anomalies,
        }


class ExecutiveKernel:
    """
    The AGI Executive Layer.
    
    Coordinates all Deterministic-Brain components toward long-term goals.
    Maintains the billion-dollar acquisition agenda and ensures autonomous
    execution while staying within legal and safety boundaries.
    """

    def __init__(
        self,
        autonomous_core: AutonomousCore,
        probabilistic_agent: ProbabilisticAgent,
        deterministic_executor: DeterministicExecutor,
        self_learning_loop: SelfLearningLoop,
        autonomous_scheduler: AutonomousScheduler,
    ):
        self.autonomous_core = autonomous_core
        self.probabilistic_agent = probabilistic_agent
        self.deterministic_executor = deterministic_executor
        self.self_learning_loop = self_learning_loop
        self.autonomous_scheduler = autonomous_scheduler
        
        # Executive state
        self.goals: Dict[str, ExecutiveGoal] = {}
        self.financial_snapshots: List[FinancialSnapshot] = []
        self.agenda: List[Dict[str, Any]] = []
        self.blockers: List[Dict[str, Any]] = []
        
        logger.info("Executive Kernel initialized — AGI executive layer active")

    def set_goal(
        self,
        goal_id: str,
        description: str,
        priority: int = 3,
        deadline: Optional[datetime] = None,
        dependencies: List[str] = None,
    ) -> ExecutiveGoal:
        """Set a long-term executive goal."""
        goal = ExecutiveGoal(
            goal_id=goal_id,
            description=description,
            priority=priority,
            deadline=deadline,
            dependencies=dependencies or [],
        )
        self.goals[goal_id] = goal
        logger.info(f"Executive goal set: {goal_id} (priority={priority})")
        return goal

    def update_goal_status(
        self,
        goal_id: str,
        status: ExecutiveGoalStatus,
        message: Optional[str] = None,
    ) -> None:
        """Update the status of an executive goal."""
        if goal_id not in self.goals:
            raise ValueError(f"Goal {goal_id} not found")
        
        goal = self.goals[goal_id]
        goal.status = status
        goal.updated_at = time.time()
        
        if message:
            goal.subgoals.append({
                "timestamp": time.time(),
                "status": status.value,
                "message": message,
            })
        
        logger.info(f"Goal {goal_id} updated to {status.value}: {message or 'no message'}")

    def plan_execution(
        self,
        goal_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Plan execution of an executive goal using the full AGI stack.
        
        Returns: (success, plan_dict)
        """
        if goal_id not in self.goals:
            return False, {"error": "Goal not found"}
        
        goal = self.goals[goal_id]
        
        # Step 1: Observe current state
        self.autonomous_core.observe(Observation(
            observation_type="executive_goal",
            content={
                "goal_id": goal_id,
                "goal": goal.description,
                "priority": goal.priority,
                "context": context or {},
            },
        ))
        
        # Step 2: Reason about solutions
        reasoning_paths = self.autonomous_core.reason(goal.description, context or {})
        
        # Step 3: Select best path using probabilistic agent
        selected_path = self.probabilistic_agent.select_action({
            "goal": goal_id,
            "paths": reasoning_paths,
        })
        
        # Step 4: Create execution plan
        plan = self.deterministic_executor.create_plan(
            goal=goal.description,
            steps=[
                # Convert reasoning path to executable steps
            ],
        )
        
        # Step 5: Record in learning loop
        self.self_learning_loop.record_outcome(
            goal=goal.description,
            success=False,  # Will update after execution
            reward=0.0,
            action_taken=selected_path.action,
        )
        
        self.update_goal_status(goal_id, ExecutiveGoalStatus.PLANNING, "Execution plan generated")
        
        return True, {
            "goal_id": goal_id,
            "plan_id": plan.plan_id,
            "selected_action": selected_path.action,
            "reasoning_paths": len(reasoning_paths),
        }

    def execute_plan(
        self,
        plan_id: str,
        goal_id: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Execute a planned action.
        
        Returns: (success, result_dict)
        """
        # Retrieve plan from executor
        plan = self.deterministic_executor.active_plans.get(plan_id)
        if not plan:
            return False, {"error": "Plan not found"}
        
        # Execute with rollback guarantees
        success, result = self.deterministic_executor.execute(plan)
        
        # Update goal status
        if goal_id and goal_id in self.goals:
            status = ExecutiveGoalStatus.COMPLETED if success else ExecutiveGoalStatus.FAILED
            self.update_goal_status(goal_id, status, result.get("error") or "Completed")
        
        # Record outcome in learning loop
        self.self_learning_loop.record_outcome(
            goal=plan.goal,
            success=success,
            reward=1.0 if success else -1.0,
        )
        
        return success, result

    def monitor_finances(
        self,
        snapshot: FinancialSnapshot,
    ) -> Dict[str, Any]:
        """
        Monitor financial health and flag anomalies.
        
        Returns: analysis_dict
        """
        self.financial_snapshots.append(snapshot)
        
        # Simple anomaly detection
        anomalies = []
        
        if snapshot.cash_balance < 0:
            anomalies.append({
                "type": "negative_balance",
                "severity": "critical",
                "message": f"Cash balance is negative: ${snapshot.cash_balance}",
            })
        
        if snapshot.runway_months < 3:
            anomalies.append({
                "type": "low_runway",
                "severity": "high",
                "message": f"Only {snapshot.runway_months:.1f} months of runway remaining",
            })
        
        if snapshot.monthly_outflow > snapshot.monthly_inflow * 1.5:
            anomalies.append({
                "type": "high_burn",
                "severity": "medium",
                "message": "Burn rate exceeds inflow by 50%+",
            })
        
        snapshot.anomalies = anomalies
        
        if anomalies:
            logger.warning(f"Financial anomalies detected: {len(anomalies)} issues")
            # Could trigger alerts or corrective actions
        
        return {
            "status": "ok" if not anomalies else "warning",
            "anomalies": anomalies,
            "runway_months": snapshot.runway_months,
        }

    def get_status(self) -> Dict[str, Any]:
        """Get overall executive kernel status."""
        return {
            "executive_kernel": {
                "active_goals": len([g for g in self.goals.values() if g.status != ExecutiveGoalStatus.COMPLETED]),
                "completed_goals": len([g for g in self.goals.values() if g.status == ExecutiveGoalStatus.COMPLETED]),
                "blocked_goals": len([g for g in self.goals.values() if g.status == ExecutiveGoalStatus.BLOCKED]),
                "financial_snapshots": len(self.financial_snapshots),
                "current_runway": self.financial_snapshots[-1].runway_months if self.financial_snapshots else 0,
            },
            "autonomous_core": self.autonomous_core.get_status(),
            "probabilistic_agent": self.probabilistic_agent.get_decision_metrics(),
            "deterministic_executor": self.deterministic_executor.get_statistics(),
            "self_learning_loop": self.self_learning_loop.get_learning_status(),
            "autonomous_scheduler": self.autonomous_scheduler.get_scheduler_status(),
        }

    def save_state(self) -> None:
        """Save executive state to disk."""
        # TODO: Implement state persistence
        pass

    def load_state(self) -> None:
        """Load executive state from disk."""
        # TODO: Implement state loading
        pass


# Singleton instance (optional)
_executive_kernel: Optional[ExecutiveKernel] = None


def get_executive_kernel() -> ExecutiveKernel:
    """Get the global Executive Kernel instance."""
    global _executive_kernel
    if _executive_kernel is None:
        raise ValueError("Executive Kernel not initialized")
    return _executive_kernel


def init_executive_kernel(
    autonomous_core: AutonomousCore,
    probabilistic_agent: ProbabilisticAgent,
    deterministic_executor: DeterministicExecutor,
    self_learning_loop: SelfLearningLoop,
    autonomous_scheduler: AutonomousScheduler,
) -> ExecutiveKernel:
    """Initialize the global Executive Kernel."""
    global _executive_kernel
    if _executive_kernel is not None:
        raise ValueError("Executive Kernel already initialized")
    
    _executive_kernel = ExecutiveKernel(
        autonomous_core,
        probabilistic_agent,
        deterministic_executor,
        self_learning_loop,
        autonomous_scheduler,
    )
    
    return _executive_kernel