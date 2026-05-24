"""
AGI Autonomous Operating System - Integration Example
=====================================================

Demonstrates how to use all components together to create a fully
autonomous AGI system with deterministic and probabilistic reasoning,
integrated with cron-based task scheduling.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from agi.autonomous_core import AutonomousCore, Observation
from agi.probabilistic_agent import ProbabilisticAgent, DecisionStrategy
from agi.deterministic_executor import DeterministicExecutor, ActionStep, ActionType, ExecutionPlan
from agi.self_learning_loop import SelfLearningLoop
from agi.autonomous_scheduler import AutonomousScheduler, TaskFrequency, TaskPriority
from agi.real_dca_adapter import register_real_dca_actions, map_goal_to_steps

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)



class AGIAutonomousOS:
    """
    Integrated AGI Autonomous Operating System.
    
    Combines:
    - AutonomousCore: AGI-like metacognitive reasoning
    - ProbabilisticAgent: Uncertainty-aware decisions
    - DeterministicExecutor: Guaranteed action execution
    - SelfLearningLoop: Continuous improvement
    - AutonomousScheduler: Intelligent cron-based tasking
    """

    def __init__(
        self,
        os_id: str = "agi-aos",
        state_dir: Optional[Path] = None,
    ):
        self.os_id = os_id
        self.state_dir = Path(state_dir or Path.cwd() / ".agi_aos")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.autonomous_core = AutonomousCore(
            mind_id=f"{os_id}-mind",
            state_dir=self.state_dir / "core",
        )
        
        self.probabilistic_agent = ProbabilisticAgent(
            agent_id=f"{os_id}-agent",
            strategy=DecisionStrategy.BALANCED,
        )
        
        self.deterministic_executor = DeterministicExecutor(
            executor_id=f"{os_id}-executor",
            state_dir=self.state_dir / "executor",
        )
        register_real_dca_actions(self.deterministic_executor)
        
        self.learning_loop = SelfLearningLoop(
            learner_id=f"{os_id}-learner",
            state_dir=self.state_dir / "learning",
        )
        
        self.scheduler = AutonomousScheduler(
            scheduler_id=f"{os_id}-scheduler",
            state_dir=self.state_dir / "scheduler",
        )
        
        logger.info("AGI Autonomous OS initialized: %s", os_id)

    def handle_goal(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        use_probabilistic: bool = True,
    ) -> Dict[str, Any]:
        """
        Handle a goal through the full AGI pipeline:
        1. Observe current state
        2. Reason about solutions
        3. Deliberate and select path
        4. Execute deterministically OR probabilistically
        5. Reflect on outcome
        6. Learn from experience
        """
        context = context or {}
        
        # Step 1: Observe
        observation = Observation(
            observation_type="goal_request",
            content={"goal": goal, "context": context},
            confidence=0.7,
            source="goal_handler",
        )
        self.autonomous_core.observe(observation)
        
        # Step 2: Reason
        logger.info("Reasoning about goal: %s", goal)
        reasoning_paths = self.autonomous_core.reason(goal, context)
        
        if not reasoning_paths:
            return {
                "success": False,
                "error": "No valid reasoning paths found",
            }
        
        # Step 3: Deliberate
        logger.info("Deliberating on options")
        selected_path = self.autonomous_core.deliberate()
        
        # Choose execution mode
        if use_probabilistic:
            return self._execute_probabilistic(goal, selected_path, context)
        else:
            return self._execute_deterministic(goal, selected_path, context)

    def _execute_probabilistic(
        self,
        goal: str,
        reasoning_path,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute using probabilistic agent."""
        logger.info("Executing probabilistically for goal: %s", goal)
        
        # Register decision
        decision = self.probabilistic_agent.register_decision(
            action=reasoning_path.description,
            success_probability=reasoning_path.estimated_success_rate,
            risk_level=1.0 if reasoning_path.risk_level == "high" else 0.5,
        )
        
        # Select best action
        selected_action = self.probabilistic_agent.select_action(context)
        
        # Execute actual query via DeterministicCodingAgent
        success = False
        reward = -0.5
        output = {}
        try:
            from orchestration.dca_engine import DeterministicCodingAgent
            agent = DeterministicCodingAgent()
            dca_result = agent.handle(goal)
            success = dca_result.get("status") == "ok"
            reward = 1.0 if success else -0.5
            output = dca_result
        except Exception as e:
            logger.error("Probabilistic action execution failed: %s", e)
            output = {"error": str(e)}
        
        # Record outcome
        self.probabilistic_agent.record_outcome(
            decision=selected_action,
            success=success,
            reward=reward,
            feedback=f"Probabilistic execution: {output.get('status', 'failed')}",
        )
        
        # Reflect and learn
        self.autonomous_core.reflect({
            "success": success,
            "reward": reward,
            "execution_mode": "probabilistic",
            "error": output.get("error") if not success else None
        })
        
        # Record learning
        self.learning_loop.record_outcome(
            goal=goal,
            success=success,
            reward=reward,
            action_taken=selected_action.action,
            context=context,
            confidence_gain=0.1 if success else -0.05,
        )
        
        return {
            "success": success,
            "goal": goal,
            "execution_mode": "probabilistic",
            "action": selected_action.action,
            "reward": reward,
            "output": output
        }

    def _execute_deterministic(
        self,
        goal: str,
        reasoning_path,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute using deterministic executor."""
        logger.info("Executing deterministically for goal: %s", goal)
        
        # Create real execution plan from reasoning path using mapping adapter
        steps = map_goal_to_steps(goal, context)
        plan = self.deterministic_executor.create_plan(goal, steps)
        
        # Execute deterministically
        success, result = self.deterministic_executor.execute(plan)
        
        # Reflect and learn
        self.autonomous_core.reflect({
            "success": success,
            "reward": 1.0 if success else -1.0,
            "execution_mode": "deterministic",
            "error": plan.error if not success else None
        })
        
        # Record learning
        self.learning_loop.record_outcome(
            goal=goal,
            success=success,
            reward=1.0 if success else -1.0,
            context=context,
        )
        
        return {
            "success": success,
            "goal": goal,
            "execution_mode": "deterministic",
            "plan_id": plan.plan_id,
            "result": result,
        }

    def _simulate_action(self, action: str) -> bool:
        """Simulate action execution (replace with real logic)."""
        # Simple simulation: actions with certain keywords succeed
        success_keywords = ["retrieve", "execute", "generate"]
        return any(kw in action.lower() for kw in success_keywords)

    def register_autonomous_task(
        self,
        name: str,
        goal: str,
        frequency: TaskFrequency = TaskFrequency.DAILY,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> None:
        """Register a task for autonomous execution."""
        def task_handler(goal: str, task_context: Dict[str, Any]) -> Dict[str, Any]:
            """Handler function for the task."""
            result = self.handle_goal(goal)
            return result
        
        self.scheduler.register_task(
            name=name,
            goal=goal,
            handler=task_handler,
            frequency=frequency,
            priority=priority,
        )
        
        logger.info("Registered autonomous task: %s", name)

    async def run_autonomous_loop(self) -> None:
        """Run the autonomous OS continuously."""
        logger.info("Starting AGI Autonomous OS loop")
        await self.scheduler.run_scheduler(interval_seconds=1.0)

    def run_once(self, max_tasks: int = 5) -> None:
        """Run scheduler once (for testing)."""
        logger.info("Running autonomous OS once (max %d tasks)", max_tasks)
        self.scheduler.run_once(max_tasks=max_tasks)

    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        return {
            "os_id": self.os_id,
            "autonomous_mind": self.autonomous_core.get_status(),
            "probabilistic_agent": self.probabilistic_agent.get_decision_metrics(),
            "deterministic_executor": self.deterministic_executor.get_statistics(),
            "learning_system": self.learning_loop.get_learning_status(),
            "scheduler": self.scheduler.get_scheduler_status(),
        }

    def save_state(self) -> None:
        """Save complete system state."""
        logger.info("Saving AGI AOS state")
        self.autonomous_core.save_state()
        self.learning_loop.save_state()
        self.scheduler.save_state()
        
        logger.info("State saved to %s", self.state_dir)

    def print_status(self) -> None:
        """Print human-readable status."""
        status = self.get_system_status()
        
        print("\n" + "="*60)
        print("AGI AUTONOMOUS OPERATING SYSTEM STATUS")
        print("="*60)
        
        print(f"\n🧠 AUTONOMOUS MIND:")
        mind = status["autonomous_mind"]
        print(f"   State: {mind['cognition_state']}")
        print(f"   Self-Awareness: {mind['self_awareness_level']:.2%}")
        print(f"   Reasoning Quality: {mind['reasoning_quality']}")
        print(f"   Successes: {mind['success_history_size']}")
        print(f"   Failures: {mind['failure_history_size']}")
        
        print(f"\n🎯 PROBABILISTIC AGENT:")
        agent = status["probabilistic_agent"]
        print(f"   Total Decisions: {agent['total_decisions_registered']}")
        print(f"   Success Rate: {agent['overall_success_rate']:.2%}")
        print(f"   Average Confidence: {agent['average_confidence']:.2%}")
        
        print(f"\n⚙️  DETERMINISTIC EXECUTOR:")
        executor = status["deterministic_executor"]
        print(f"   Total Plans: {executor['total_plans']}")
        print(f"   Success Rate: {executor['success_rate']:.2%}")
        print(f"   Registered Actions: {executor['registered_actions']}")
        
        print(f"\n📚 LEARNING SYSTEM:")
        learning = status["learning_system"]
        print(f"   Patterns Discovered: {learning['patterns_discovered']}")
        print(f"   Performance Trends: {learning['performance_trends_tracked']}")
        print(f"   Strategy Adaptations: {learning['strategy_adaptations']}")
        
        print(f"\n📅 SCHEDULER:")
        scheduler = status["scheduler"]
        print(f"   Total Tasks: {scheduler['total_tasks']}")
        print(f"   Running Tasks: {scheduler['running_tasks']}")
        print(f"   Overdue Tasks: {scheduler['overdue_tasks']}")
        print(f"   Total Executions: {scheduler['total_executions']}")
        
        print("\n" + "="*60 + "\n")


# Example usage
if __name__ == "__main__":
    # Create AGI AOS
    aos = AGIAutonomousOS(os_id="agi-brain-v1")
    
    # Register some autonomous tasks
    aos.register_autonomous_task(
        name="Daily Analysis",
        goal="Analyze system performance and optimize",
        frequency=TaskFrequency.DAILY,
        priority=TaskPriority.HIGH,
    )
    
    aos.register_autonomous_task(
        name="Continuous Learning",
        goal="Review recent outcomes and discover patterns",
        frequency=TaskFrequency.ADAPTIVE,
        priority=TaskPriority.NORMAL,
    )
    
    # Handle a single goal
    logger.info("Testing goal handling")
    result = aos.handle_goal(
        goal="Generate and execute a code improvement plan",
        context={"domain": "testing", "priority": "high"},
    )
    print("Goal result:", result)
    
    # Run scheduler once
    aos.run_once(max_tasks=2)
    
    # Print status
    aos.print_status()
    
    # Save state
    aos.save_state()


# Shared AGI OS Singleton Accessor
_shared_agi_os: Optional[AGIAutonomousOS] = None

def get_shared_agi_os(os_id: str = "agi-brain-v1") -> AGIAutonomousOS:
    global _shared_agi_os
    if _shared_agi_os is None:
        _shared_agi_os = AGIAutonomousOS(os_id=os_id)
        # Register core tasks
        _shared_agi_os.register_autonomous_task(
            name="Daily Analysis",
            goal="Analyze system performance and optimize",
            frequency=TaskFrequency.DAILY,
            priority=TaskPriority.HIGH,
        )
        _shared_agi_os.register_autonomous_task(
            name="Continuous Learning",
            goal="Review recent outcomes and discover patterns",
            frequency=TaskFrequency.ADAPTIVE,
            priority=TaskPriority.NORMAL,
        )
        _shared_agi_os.register_autonomous_task(
            name="Weekly Performance Audit",
            goal="Audit system health and self-heal",
            frequency=TaskFrequency.WEEKLY,
            priority=TaskPriority.HIGH,
        )
        
        # Wire EventBus listeners to trigger AGI auto-learning on EventBus skill success/failure events
        try:
            from orchestration.event_bus import event_bus
            
            def on_skill_success(skill_id: str, latency_ms: int, confidence: float):
                _shared_agi_os.learning_loop.record_outcome(
                    goal=f"Execute skill {skill_id}",
                    success=True,
                    reward=1.0,
                    action_taken=skill_id,
                    confidence_gain=0.05,
                    context={"latency_ms": latency_ms, "confidence": confidence}
                )
                
            def on_skill_failure(skill_id: str, latency_ms: int, confidence: float):
                _shared_agi_os.learning_loop.record_outcome(
                    goal=f"Execute skill {skill_id}",
                    success=False,
                    reward=-1.0,
                    action_taken=skill_id,
                    confidence_gain=-0.1,
                    context={"latency_ms": latency_ms, "confidence": confidence}
                )
                
            event_bus.on("skill_success", on_skill_success)
            event_bus.on("skill_failure", on_skill_failure)
            logger.info("AGI OS Singleton wired to EventBus skill success/failure events.")
        except Exception as eb_err:
            logger.warning("Could not wire AGI OS to EventBus: %s", eb_err)
            
    return _shared_agi_os

