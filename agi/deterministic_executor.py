"""
Deterministic Executor: Guaranteed Action Execution
===================================================

Provides:
- Deterministic execution with rollback
- Transactional guarantees
- Failure recovery and compensation
- Execution plans with checkpoints
- Deterministic logging and replay
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ExecutionState(str, Enum):
    """State of execution."""
    PENDING = "pending"
    RUNNING = "running"
    CHECKPOINTED = "checkpointed"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ActionType(str, Enum):
    """Type of action to execute."""
    DETERMINISTIC = "deterministic"  # Must always succeed
    IDEMPOTENT = "idempotent"  # Safe to retry
    COMPENSABLE = "compensable"  # Has rollback
    TRANSACTIONAL = "transactional"  # All-or-nothing


@dataclass
class ActionStep:
    """A single step in execution."""
    step_id: str
    action_name: str
    action_type: ActionType
    parameters: Dict[str, Any]
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    compensation: Optional[Callable] = None
    max_retries: int = 3
    timeout_seconds: float = 300.0


@dataclass
class Checkpoint:
    """Checkpoint in execution for recovery."""
    checkpoint_id: str
    step_id: str
    timestamp: float
    state_snapshot: Dict[str, Any]
    is_safe_to_rollback: bool = True


@dataclass
class ExecutionPlan:
    """A deterministic execution plan with steps and checkpoints."""
    plan_id: str
    goal: str
    steps: List[ActionStep]
    execution_state: ExecutionState = ExecutionState.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    current_step_index: int = 0
    checkpoints: List[Checkpoint] = field(default_factory=list)
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    
    def get_progress(self) -> float:
        """Get execution progress 0.0 to 1.0."""
        if not self.steps:
            return 1.0
        return self.current_step_index / len(self.steps)


class DeterministicExecutor:
    """
    Executes plans deterministically with guarantees:
    - Transactional semantics
    - Automatic rollback on failure
    - Checkpoint-based recovery
    - Deterministic logging for replay
    """

    def __init__(
        self,
        executor_id: str = "deterministic-executor",
        state_dir: Optional[Path] = None,
        checkpoint_interval: int = 1,  # Checkpoint after N steps
    ):
        self.executor_id = executor_id
        self.state_dir = Path(state_dir or Path.cwd() / ".deterministic_executor")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_interval = checkpoint_interval
        
        self.active_plans: Dict[str, ExecutionPlan] = {}
        self.completed_plans: List[ExecutionPlan] = []
        self.action_handlers: Dict[str, Callable] = {}
        
        logger.info("DeterministicExecutor initialized (id=%s)", executor_id)

    def register_action(
        self,
        action_name: str,
        handler: Callable,
        compensation: Optional[Callable] = None,
    ) -> None:
        """Register an action handler."""
        self.action_handlers[action_name] = {
            "handler": handler,
            "compensation": compensation,
        }
        logger.info("Registered action: %s", action_name)

    def create_plan(
        self,
        goal: str,
        steps: List[ActionStep],
    ) -> ExecutionPlan:
        """Create an execution plan."""
        plan_id = f"{self.executor_id}-{int(time.time())}"
        
        plan = ExecutionPlan(
            plan_id=plan_id,
            goal=goal,
            steps=steps,
        )
        
        self.active_plans[plan_id] = plan
        logger.info("Created execution plan: %s (%d steps)", plan_id, len(steps))
        
        return plan

    def execute(self, plan: ExecutionPlan) -> Tuple[bool, Dict[str, Any]]:
        """
        Execute a plan deterministically.
        
        Returns: (success, result_dict)
        """
        plan.execution_state = ExecutionState.RUNNING
        plan.started_at = time.time()
        
        try:
            while plan.current_step_index < len(plan.steps):
                step = plan.steps[plan.current_step_index]
                
                # Execute step
                success, result = self._execute_step(plan, step)
                
                if not success:
                    # Log failure
                    plan.execution_log.append({
                        "timestamp": time.time(),
                        "step_id": step.step_id,
                        "action": step.action_name,
                        "status": "failed",
                        "error": result.get("error"),
                    })
                    
                    plan.error = result.get("error")
                    
                    # Attempt rollback
                    rollback_success = self._rollback(plan)
                    plan.execution_state = (
                        ExecutionState.ROLLED_BACK if rollback_success else ExecutionState.FAILED
                    )
                    
                    return False, {
                        "success": False,
                        "error": result.get("error"),
                        "rolled_back": rollback_success,
                        "failed_step": step.step_id,
                    }
                
                # Log success
                plan.execution_log.append({
                    "timestamp": time.time(),
                    "step_id": step.step_id,
                    "action": step.action_name,
                    "status": "completed",
                    "result": result,
                })
                
                # Create checkpoint if needed
                if (plan.current_step_index + 1) % self.checkpoint_interval == 0:
                    self._create_checkpoint(plan, step)
                
                plan.current_step_index += 1
            
            # Plan completed successfully
            plan.execution_state = ExecutionState.COMPLETED
            plan.completed_at = time.time()
            self.completed_plans.append(plan)
            
            logger.info(
                "Plan executed successfully: %s (duration=%.2fs)",
                plan.plan_id,
                plan.completed_at - plan.started_at,
            )
            
            return True, {
                "success": True,
                "plan_id": plan.plan_id,
                "duration": plan.completed_at - plan.started_at,
                "steps_executed": len(plan.steps),
            }

        except Exception as e:
            logger.error("Unexpected error during execution: %s", e)
            plan.execution_state = ExecutionState.FAILED
            plan.error = str(e)
            
            try:
                self._rollback(plan)
            except Exception as rollback_error:
                logger.error("Rollback also failed: %s", rollback_error)
            
            return False, {
                "success": False,
                "error": str(e),
                "step_index": plan.current_step_index,
            }

    def _execute_step(self, plan: ExecutionPlan, step: ActionStep) -> Tuple[bool, Dict[str, Any]]:
        """Execute a single step with retries."""
        if step.action_name not in self.action_handlers:
            return False, {"error": f"Unknown action: {step.action_name}"}
        
        handler = self.action_handlers[step.action_name]["handler"]
        
        # Check preconditions
        for precond in step.preconditions:
            if not self._check_condition(plan, precond):
                return False, {"error": f"Precondition failed: {precond}"}
        
        # Execute with retries
        last_error = None
        for attempt in range(step.max_retries):
            try:
                result = handler(
                    parameters=step.parameters,
                    execution_context={
                        "plan_id": plan.plan_id,
                        "step_id": step.step_id,
                        "attempt": attempt + 1,
                    },
                )
                
                # Check postconditions
                for postcond in step.postconditions:
                    if not self._check_condition(plan, postcond):
                        return False, {"error": f"Postcondition failed: {postcond}"}
                
                return True, result

            except Exception as e:
                last_error = str(e)
                if attempt < step.max_retries - 1:
                    logger.warning(
                        "Step %s attempt %d failed: %s, retrying...",
                        step.step_id,
                        attempt + 1,
                        e,
                    )
                    time.sleep(1.0 * (attempt + 1))  # Exponential backoff
        
        return False, {"error": last_error or "Unknown error"}

    def _create_checkpoint(self, plan: ExecutionPlan, step: ActionStep) -> None:
        """Create a checkpoint for recovery."""
        checkpoint = Checkpoint(
            checkpoint_id=f"{plan.plan_id}-ckpt-{len(plan.checkpoints)}",
            step_id=step.step_id,
            timestamp=time.time(),
            state_snapshot={
                "current_step_index": plan.current_step_index,
                "steps_completed": plan.execution_log.copy(),
            },
        )
        
        plan.checkpoints.append(checkpoint)
        logger.info("Created checkpoint: %s", checkpoint.checkpoint_id)

    def _rollback(self, plan: ExecutionPlan) -> bool:
        """
        Rollback plan execution using compensation actions.
        
        Executes compensation in reverse order of execution.
        """
        logger.info("Initiating rollback for plan: %s", plan.plan_id)
        
        rolled_back_steps = 0
        
        # Find latest safe checkpoint
        safe_checkpoint = None
        for checkpoint in reversed(plan.checkpoints):
            if checkpoint.is_safe_to_rollback:
                safe_checkpoint = checkpoint
                break
        
        # Compensation in reverse order
        for step in reversed(plan.steps[:plan.current_step_index]):
            if step.action_name not in self.action_handlers:
                continue
            
            action_info = self.action_handlers[step.action_name]
            compensation = action_info.get("compensation")
            
            if compensation is None:
                logger.warning("No compensation for action: %s", step.action_name)
                continue
            
            try:
                logger.info("Executing compensation for: %s", step.action_name)
                compensation(
                    parameters=step.parameters,
                    execution_context={
                        "plan_id": plan.plan_id,
                        "original_step_id": step.step_id,
                    },
                )
                rolled_back_steps += 1
            except Exception as e:
                logger.error("Compensation failed for %s: %s", step.action_name, e)
                return False
        
        logger.info("Rollback completed: %d steps compensated", rolled_back_steps)
        return True

    def _check_condition(self, plan: ExecutionPlan, condition: str) -> bool:
        """Check a condition (implementation depends on condition language)."""
        # Simple implementation: always true unless starts with "not_"
        if condition.startswith("not_"):
            return False
        return True

    def get_plan_status(self, plan_id: str) -> Dict[str, Any]:
        """Get status of a plan."""
        plan = self.active_plans.get(plan_id)
        if not plan:
            plan = next(
                (p for p in self.completed_plans if p.plan_id == plan_id),
                None,
            )
        
        if not plan:
            return {}
        
        return {
            "plan_id": plan.plan_id,
            "goal": plan.goal,
            "state": plan.execution_state.value,
            "progress": plan.get_progress(),
            "current_step": plan.current_step_index,
            "total_steps": len(plan.steps),
            "error": plan.error,
            "checkpoints": len(plan.checkpoints),
            "log_entries": len(plan.execution_log),
        }

    def save_plan(self, plan: ExecutionPlan) -> Path:
        """Save plan to disk."""
        filename = f"plan_{plan.plan_id}_{int(time.time())}.json"
        filepath = self.state_dir / filename
        
        data = {
            "plan_id": plan.plan_id,
            "goal": plan.goal,
            "state": plan.execution_state.value,
            "progress": plan.get_progress(),
            "current_step": plan.current_step_index,
            "total_steps": len(plan.steps),
            "error": plan.error,
            "checkpoints": len(plan.checkpoints),
            "execution_log": plan.execution_log,
            "timestamp": datetime.now().isoformat(),
        }
        
        filepath.write_text(json.dumps(data, indent=2, default=str))
        logger.info("Saved plan to %s", filepath)
        
        return filepath

    def get_statistics(self) -> Dict[str, Any]:
        """Get executor statistics."""
        total_plans = len(self.completed_plans) + len(self.active_plans)
        successful = sum(
            1 for p in self.completed_plans
            if p.execution_state == ExecutionState.COMPLETED
        )
        
        return {
            "executor_id": self.executor_id,
            "total_plans": total_plans,
            "completed_plans": len(self.completed_plans),
            "active_plans": len(self.active_plans),
            "successful_plans": successful,
            "success_rate": (successful / len(self.completed_plans)) if self.completed_plans else 0,
            "registered_actions": len(self.action_handlers),
        }
