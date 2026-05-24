"""
Autonomous Scheduler: Intelligent Cron Integration
==================================================

Integrates AGI system with cron for:
- Intelligent task scheduling
- Dynamic task prioritization
- Adaptive scheduling based on success rates
- Resource-aware scheduling
- Continuous autonomous operation
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)


class TaskPriority(str, Enum):
    """Task priority levels."""
    CRITICAL = "critical"  # Must run immediately
    HIGH = "high"  # Run soon
    NORMAL = "normal"  # Regular scheduling
    LOW = "low"  # Background, can defer
    DEFERRED = "deferred"  # Run when resources available


class TaskFrequency(str, Enum):
    """Task frequency patterns."""
    ONCE = "once"  # Run once
    MINUTELY = "minutely"  # Every minute
    HOURLY = "hourly"  # Every hour
    DAILY = "daily"  # Every day
    WEEKLY = "weekly"  # Every week
    MONTHLY = "monthly"  # Every month
    ADAPTIVE = "adaptive"  # Adjust based on success/failure


@dataclass
class ScheduledTask:
    """A task scheduled for autonomous execution."""
    task_id: str
    name: str
    description: str
    goal: str  # The goal for the AGI system
    handler: Callable  # Function to call
    frequency: TaskFrequency
    priority: TaskPriority
    enabled: bool = True
    
    # Scheduling
    cron_expression: Optional[str] = None  # Standard cron
    next_run: float = 0.0
    last_run: Optional[float] = None
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    
    # Statistics
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    average_duration_seconds: float = 0.0
    success_rate: float = 0.0
    
    # Adaptive scheduling
    adaptive_interval_seconds: float = 3600.0  # Default 1 hour
    failure_backoff_multiplier: float = 1.5  # Backoff on failure
    
    # Resource constraints
    max_concurrent: int = 1
    timeout_seconds: float = 300.0
    required_resources: Dict[str, float] = field(default_factory=dict)
    
    created_at: float = field(default_factory=time.time)


class TaskExecutionResult:
    """Result of task execution."""
    
    def __init__(
        self,
        task_id: str,
        success: bool,
        duration_seconds: float,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        self.task_id = task_id
        self.success = success
        self.duration_seconds = duration_seconds
        self.output = output or {}
        self.error = error
        self.timestamp = time.time()


class AutonomousScheduler:
    """
    Intelligent scheduler for autonomous AGI operations.
    
    Features:
    - Cron-based task scheduling
    - Dynamic priority adjustments
    - Adaptive frequency based on success
    - Concurrency control
    - Resource awareness
    """

    def __init__(
        self,
        scheduler_id: str = "autonomous-scheduler",
        state_dir: Optional[Path] = None,
        max_concurrent_tasks: int = 5,
    ):
        self.scheduler_id = scheduler_id
        self.state_dir = Path(state_dir or Path.cwd() / ".autonomous_scheduler")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.max_concurrent_tasks = max_concurrent_tasks
        
        self.tasks: Dict[str, ScheduledTask] = {}
        self.execution_history: List[TaskExecutionResult] = []
        self.running_tasks: set = set()
        
        logger.info(
            "AutonomousScheduler initialized (id=%s, max_concurrent=%d)",
            scheduler_id,
            max_concurrent_tasks,
        )

    def register_task(
        self,
        name: str,
        goal: str,
        handler: Callable,
        frequency: TaskFrequency = TaskFrequency.DAILY,
        priority: TaskPriority = TaskPriority.NORMAL,
        cron_expression: Optional[str] = None,
    ) -> ScheduledTask:
        """Register a new autonomous task."""
        task_id = f"{self.scheduler_id}-task-{len(self.tasks)}"
        
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            description=f"Autonomous task: {goal}",
            goal=goal,
            handler=handler,
            frequency=frequency,
            priority=priority,
            cron_expression=cron_expression,
        )
        
        # Set initial next_run based on frequency
        task.next_run = self._calculate_next_run(task)
        
        self.tasks[task_id] = task
        logger.info("Registered task: %s (frequency=%s, priority=%s)", name, frequency.value, priority.value)
        
        return task

    def get_next_tasks(self, limit: int = 1) -> List[ScheduledTask]:
        """Get next tasks to run based on scheduling and priority."""
        current_time = time.time()
        
        # Filter eligible tasks
        eligible = [
            t for t in self.tasks.values()
            if (
                t.enabled and
                t.next_run <= current_time and
                t.task_id not in self.running_tasks
            )
        ]
        
        # Sort by priority then by next_run
        priority_order = {
            TaskPriority.CRITICAL: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.NORMAL: 2,
            TaskPriority.LOW: 3,
            TaskPriority.DEFERRED: 4,
        }
        
        eligible.sort(key=lambda t: (
            priority_order.get(t.priority, 999),
            t.next_run,
        ))
        
        return eligible[:limit]

    def execute_task(self, task: ScheduledTask) -> TaskExecutionResult:
        """Execute a task and record result."""
        self.running_tasks.add(task.task_id)
        
        start_time = time.time()
        logger.info("Starting task: %s", task.name)
        
        result = None
        try:
            output = task.handler(
                goal=task.goal,
                task_context={
                    "task_id": task.task_id,
                    "run_count": task.run_count + 1,
                    "success_rate": task.success_rate,
                },
            )
            
            duration = time.time() - start_time
            
            result = TaskExecutionResult(
                task_id=task.task_id,
                success=True,
                duration_seconds=duration,
                output=output,
            )
            
            # Update task statistics
            task.run_count += 1
            task.success_count += 1
            task.last_run = time.time()
            task.last_success = time.time()
            task.success_rate = task.success_count / task.run_count
            task.average_duration_seconds = (
                (task.average_duration_seconds * (task.run_count - 1) + duration) /
                task.run_count
            )
            
            # Adjust scheduling for adaptive tasks
            if task.frequency == TaskFrequency.ADAPTIVE:
                self._adjust_adaptive_schedule(task, success=True)
            
            logger.info(
                "Task completed successfully: %s (duration=%.2fs)",
                task.name,
                duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            
            result = TaskExecutionResult(
                task_id=task.task_id,
                success=False,
                duration_seconds=duration,
                error=error_msg,
            )
            
            # Update task statistics
            task.run_count += 1
            task.failure_count += 1
            task.last_run = time.time()
            task.last_failure = time.time()
            task.success_rate = task.success_count / task.run_count
            
            # Backoff on failure
            task.adaptive_interval_seconds *= task.failure_backoff_multiplier
            
            # Adjust scheduling for adaptive tasks
            if task.frequency == TaskFrequency.ADAPTIVE:
                self._adjust_adaptive_schedule(task, success=False)
            
            logger.error(
                "Task failed: %s - %s (duration=%.2fs)",
                task.name,
                error_msg,
                duration,
            )

        finally:
            # Schedule next run
            task.next_run = self._calculate_next_run(task)
            
            # Record execution
            if result:
                self.execution_history.append(result)
            
            self.running_tasks.discard(task.task_id)

        return result

    def _calculate_next_run(self, task: ScheduledTask) -> float:
        """Calculate next run time for a task."""
        current_time = time.time()
        
        if task.frequency == TaskFrequency.ONCE:
            return float('inf')  # Never run again
        elif task.frequency == TaskFrequency.MINUTELY:
            return current_time + 60
        elif task.frequency == TaskFrequency.HOURLY:
            return current_time + 3600
        elif task.frequency == TaskFrequency.DAILY:
            return current_time + 86400
        elif task.frequency == TaskFrequency.WEEKLY:
            return current_time + 604800
        elif task.frequency == TaskFrequency.MONTHLY:
            return current_time + 2592000
        elif task.frequency == TaskFrequency.ADAPTIVE:
            return current_time + task.adaptive_interval_seconds
        else:
            return current_time + 3600

    def _adjust_adaptive_schedule(self, task: ScheduledTask, success: bool) -> None:
        """Adjust scheduling for adaptive frequency tasks."""
        if success:
            # On success, gradually reduce interval
            task.adaptive_interval_seconds *= 0.95
            task.adaptive_interval_seconds = max(
                task.adaptive_interval_seconds,
                60.0,  # Minimum 1 minute
            )
        else:
            # On failure, increase interval (backoff)
            task.adaptive_interval_seconds *= task.failure_backoff_multiplier
            task.adaptive_interval_seconds = min(
                task.adaptive_interval_seconds,
                86400.0,  # Maximum 24 hours
            )

    async def run_scheduler(self, interval_seconds: float = 1.0) -> None:
        """
        Run the scheduler continuously.
        Checks for tasks to run at regular intervals.
        """
        logger.info("Starting autonomous scheduler loop (interval=%.2fs)", interval_seconds)
        
        try:
            while True:
                # Check for tasks to run
                available_slots = self.max_concurrent_tasks - len(self.running_tasks)
                if available_slots > 0:
                    next_tasks = self.get_next_tasks(limit=available_slots)
                    for task in next_tasks:
                        # Execute in non-blocking way
                        asyncio.create_task(self._execute_task_async(task))
                
                await asyncio.sleep(interval_seconds)

        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        except Exception as e:
            logger.error("Scheduler error: %s", e)

    async def _execute_task_async(self, task: ScheduledTask) -> None:
        """Execute task asynchronously."""
        try:
            self.execute_task(task)
        except Exception as e:
            logger.error("Async task execution error: %s", e)

    def run_once(self, max_tasks: int = 5) -> int:
        """Run scheduler once (for testing or batch mode)."""
        tasks_executed = 0
        
        for task in self.get_next_tasks(limit=max_tasks):
            self.execute_task(task)
            tasks_executed += 1
        
        return tasks_executed

    def get_task_status(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Get status of task(s)."""
        if task_id:
            if task_id not in self.tasks:
                return {}
            task = self.tasks[task_id]
            return {
                "task_id": task.task_id,
                "name": task.name,
                "priority": task.priority.value,
                "frequency": task.frequency.value,
                "enabled": task.enabled,
                "run_count": task.run_count,
                "success_count": task.success_count,
                "failure_count": task.failure_count,
                "success_rate": task.success_rate,
                "last_run": task.last_run,
                "last_success": task.last_success,
                "last_failure": task.last_failure,
                "next_run": task.next_run,
                "average_duration": task.average_duration_seconds,
            }
        
        return {
            task_id: {
                "name": task.name,
                "success_rate": task.success_rate,
                "next_run": task.next_run,
                "enabled": task.enabled,
            }
            for task_id, task in self.tasks.items()
        }

    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get overall scheduler status."""
        current_time = time.time()
        overdue_tasks = [t for t in self.tasks.values() if t.next_run <= current_time and t.enabled]
        
        return {
            "scheduler_id": self.scheduler_id,
            "total_tasks": len(self.tasks),
            "enabled_tasks": sum(1 for t in self.tasks.values() if t.enabled),
            "running_tasks": len(self.running_tasks),
            "max_concurrent": self.max_concurrent_tasks,
            "overdue_tasks": len(overdue_tasks),
            "total_executions": len(self.execution_history),
            "uptime_hours": sum(r.duration_seconds for r in self.execution_history) / 3600,
        }

    def save_state(self) -> Path:
        """Save scheduler state to disk."""
        filename = f"scheduler_state_{int(time.time())}.json"
        filepath = self.state_dir / filename
        
        data = {
            "scheduler_id": self.scheduler_id,
            "timestamp": datetime.now().isoformat(),
            "tasks": len(self.tasks),
            "tasks_status": {
                task_id: self.get_task_status(task_id)
                for task_id in list(self.tasks.keys())[:10]  # Last 10
            },
            "scheduler_status": self.get_scheduler_status(),
            "recent_executions": [
                {
                    "task_id": r.task_id,
                    "success": r.success,
                    "duration": r.duration_seconds,
                    "timestamp": r.timestamp,
                }
                for r in self.execution_history[-20:]  # Last 20
            ],
        }
        
        filepath.write_text(json.dumps(data, indent=2, default=str))
        logger.info("Saved scheduler state to %s", filepath)
        
        return filepath
