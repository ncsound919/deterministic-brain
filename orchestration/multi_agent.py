"""Multi-Agent Orchestration — coordinate multiple deterministic agents."""
from __future__ import annotations
import os
import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"


@dataclass
class AgentTask:
    """Task assigned to an agent."""
    task_id: str
    agent_id: str
    description: str
    input_data: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    status: AgentStatus = AgentStatus.IDLE
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class Agent:
    """Base class for deterministic agents."""

    def __init__(self, agent_id: str, capabilities: List[str]):
        self.agent_id = agent_id
        self.capabilities = capabilities
        self.status = AgentStatus.IDLE

    def can_handle(self, task_type: str) -> bool:
        """Check if agent can handle this task type."""
        return task_type in self.capabilities

    def execute(self, task: AgentTask) -> Dict[str, Any]:
        """Execute a task. Override in subclasses."""
        raise NotImplementedError


class MultiAgentOrchestrator:
    """Orchestrate multiple agents for parallel/sequential execution."""

    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.tasks: Dict[str, AgentTask] = {}
        self.results: Dict[str, Any] = {}

    def register_agent(self, agent: Agent) -> None:
        """Register an agent with the orchestrator."""
        self.agents[agent.agent_id] = agent
        logger.info(f"Registered agent: {agent.agent_id}")

    def submit_task(self, task_id: str, agent_id: str, description: str,
                    input_data: Dict[str, Any], dependencies: List[str] = None) -> bool:
        """Submit a task for execution.
        
        Args:
            task_id: Unique task identifier
            agent_id: ID of agent to handle this task
            description: Task description
            input_data: Input data for the task
            dependencies: List of task IDs that must complete first
        
        Returns:
            True if task submitted successfully
        """
        if agent_id not in self.agents:
            logger.error(f"Unknown agent: {agent_id}")
            return False
        
        task = AgentTask(
            task_id=task_id,
            agent_id=agent_id,
            description=description,
            input_data=input_data,
            dependencies=dependencies or [],
        )
        self.tasks[task_id] = task
        logger.info(f"Submitted task {task_id} to agent {agent_id}")
        return True

    def _can_run(self, task_id: str) -> bool:
        """Check if a task's dependencies are satisfied."""
        task = self.tasks[task_id]
        for dep_id in task.dependencies:
            dep_task = self.tasks.get(dep_id)
            if not dep_task or dep_task.status != AgentStatus.COMPLETED:
                return False
        return True

    def run_all(self) -> Dict[str, Any]:
        """Execute all submitted tasks respecting dependencies.
        
        Returns:
            Dict mapping task_id to result
        """
        results = {}
        completed = set()
        
        while len(completed) < len(self.tasks):
            ready_tasks = [
                t for t in self.tasks.values()
                if t.task_id not in completed and self._can_run(t.task_id)
            ]
            
            if not ready_tasks:
                for t in self.tasks.values():
                    if t.task_id not in completed and t.status != AgentStatus.FAILED:
                        t.status = AgentStatus.FAILED
                        t.error = "Dependency failed"
                break
            
            for task in ready_tasks:
                agent = self.agents[task.agent_id]
                task.status = AgentStatus.RUNNING
                logger.info(f"Running task {task.task_id} on agent {task.agent_id}")
                
                try:
                    result = agent.execute(task)
                    task.result = result
                    task.status = AgentStatus.COMPLETED
                    results[task.task_id] = result
                    completed.add(task.task_id)
                except Exception as e:
                    task.status = AgentStatus.FAILED
                    task.error = str(e)
                    results[task.task_id] = {"error": e}
                    logger.error(f"Task {task.task_id} failed: {e}")
        
        self.results = results
        return results

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific task."""
        task = self.tasks.get(task_id)
        if not task:
            return None
        return {
            "task_id": task.task_id,
            "agent_id": task.agent_id,
            "status": task.status.value,
            "result": task.result,
            "error": task.error,
        }

    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all tasks and their statuses."""
        return [
            {
                "task_id": t.task_id,
                "agent_id": t.agent_id,
                "status": t.status.value,
                "description": t.description,
            }
            for t in self.tasks.values()
        ]


class ParallelExecutor:
    """Execute tasks in parallel across multiple agents."""

    def __init__(self, max_parallel: int = 4):
        self.max_parallel = max_parallel
        self.orchestrator = MultiAgentOrchestrator()

    def execute_parallel(self, tasks: List[Dict[str, Any]], agents: List[Agent]) -> Dict[str, Any]:
        """Execute tasks in parallel.
        
        Args:
            tasks: List of task dicts with keys: task_id, agent_id, input_data
            agents: List of available agents
        
        Returns:
            Dict of results
        """
        for agent in agents:
            self.orchestrator.register_agent(agent)
        
        for task in tasks:
            self.orchestrator.submit_task(
                task_id=task["task_id"],
                agent_id=task["agent_id"],
                description=task.get("description", ""),
                input_data=task.get("input_data", {}),
                dependencies=task.get("dependencies", []),
            )
        
        return self.orchestrator.run_all()


def create_parallel_workflow(agents: List[Agent], task_specs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create and execute a parallel workflow.
    
    Args:
        agents: List of agents to use
        task_specs: List of task specifications
    
    Returns:
        Workflow results
    """
    executor = ParallelExecutor()
    return executor.execute_parallel(task_specs, agents)