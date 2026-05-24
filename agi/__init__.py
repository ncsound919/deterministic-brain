"""
AGI Autonomous Operating System (AOS)
======================================
Provides AGI-like autonomous reasoning, probabilistic and deterministic actions,
integrated with cron scheduling and self-improvement loops.

Core Components:
- autonomous_core: Main AGI reasoning loop with metacognition
- probabilistic_agent: Uncertainty-aware decision making
- deterministic_executor: Guaranteed execution with rollback
- self_learning_loop: Learning from outcomes and feedback
- autonomous_scheduler: Intelligent cron-based task orchestration
"""

from agi.autonomous_core import AutonomousCore, AutonomousMind
from agi.probabilistic_agent import ProbabilisticAgent, ProbabilisticDecision
from agi.deterministic_executor import DeterministicExecutor, ExecutionPlan
from agi.self_learning_loop import SelfLearningLoop, LearningOutcome
from agi.autonomous_scheduler import AutonomousScheduler, ScheduledTask

__all__ = [
    "AutonomousCore",
    "AutonomousMind",
    "ProbabilisticAgent",
    "ProbabilisticDecision",
    "DeterministicExecutor",
    "ExecutionPlan",
    "SelfLearningLoop",
    "LearningOutcome",
    "AutonomousScheduler",
    "ScheduledTask",
]
