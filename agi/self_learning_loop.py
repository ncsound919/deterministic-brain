"""
Self-Learning Loop: Continuous Improvement
==========================================

Enables the AGI system to learn from outcomes:
- Pattern recognition from successes/failures
- Strategy adaptation
- Meta-learning (learning how to learn)
- Knowledge consolidation
- Performance trend analysis
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class LearningOutcome:
    """Result of a learning episode."""
    episode_id: str
    timestamp: float
    goal: str
    success: bool
    reward: float
    confidence_gain: float  # How much confidence improved
    pattern_discovered: Optional[str] = None
    action_taken: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LearnedPattern:
    """A learned pattern from experience."""
    pattern_id: str
    pattern_name: str
    description: str
    conditions: Dict[str, Any]  # When this pattern applies
    actions: List[str]  # Actions that work
    success_rate: float
    confidence: float
    discovered_at: float
    occurrence_count: int = 0
    success_count: int = 0
    last_used: Optional[float] = None
    related_patterns: List[str] = field(default_factory=list)


@dataclass
class PerformanceTrend:
    """Performance trend analysis."""
    metric_name: str
    values: List[float]  # Time-series values
    timestamps: List[float]
    trend_direction: str  # "improving", "declining", "stable"
    trend_magnitude: float  # How fast (per unit time)
    forecast_value: Optional[float] = None  # Next predicted value


class SelfLearningLoop:
    """
    Self-improving learning system that:
    - Discovers patterns from experiences
    - Adapts strategies based on outcomes
    - Consolidates knowledge
    - Analyzes performance trends
    """

    def __init__(
        self,
        learner_id: str = "self-learner",
        state_dir: Optional[Path] = None,
        memory_window_days: int = 30,
    ):
        self.learner_id = learner_id
        self.state_dir = Path(state_dir or Path.cwd() / ".self_learning")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.memory_window = timedelta(days=memory_window_days)
        
        self.outcomes: List[LearningOutcome] = []
        self.patterns: Dict[str, LearnedPattern] = {}
        self.performance_trends: Dict[str, PerformanceTrend] = {}
        self.strategy_adaptations: List[Dict[str, Any]] = []
        
        logger.info("SelfLearningLoop initialized (id=%s)", learner_id)

    def record_outcome(
        self,
        goal: str,
        success: bool,
        reward: float,
        action_taken: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        confidence_gain: float = 0.0,
    ) -> LearningOutcome:
        """Record an outcome for learning."""
        episode_id = f"{self.learner_id}-ep-{len(self.outcomes)}"
        
        outcome = LearningOutcome(
            episode_id=episode_id,
            timestamp=time.time(),
            goal=goal,
            success=success,
            reward=reward,
            action_taken=action_taken,
            context=context or {},
            confidence_gain=confidence_gain,
        )
        
        self.outcomes.append(outcome)
        
        # Trigger learning
        self._learn_from_outcome(outcome)
        
        logger.info(
            "Recorded outcome: goal=%s, success=%s, reward=%.2f",
            goal,
            success,
            reward,
        )
        
        return outcome

    def _learn_from_outcome(self, outcome: LearningOutcome) -> None:
        """Learn from a single outcome."""
        # Pattern discovery
        if outcome.success:
            self._discover_pattern(outcome)
        
        # Update performance metrics
        self._update_performance_metrics(outcome)
        
        # Strategy adaptation
        self._adapt_strategy(outcome)

    def _discover_pattern(self, outcome: LearningOutcome) -> None:
        """Discover patterns from successful outcomes."""
        # Create pattern signature
        pattern_sig = self._create_pattern_signature(outcome)
        
        if pattern_sig in self.patterns:
            # Reinforce existing pattern
            pattern = self.patterns[pattern_sig]
            pattern.occurrence_count += 1
            pattern.success_count += 1
            pattern.last_used = time.time()
            pattern.success_rate = pattern.success_count / pattern.occurrence_count
            pattern.confidence = min(1.0, pattern.confidence + 0.05)
        else:
            # Discover new pattern
            pattern_id = f"{self.learner_id}-pat-{len(self.patterns)}"
            pattern = LearnedPattern(
                pattern_id=pattern_id,
                pattern_name=f"Pattern for {outcome.goal}",
                description=self._generate_pattern_description(outcome),
                conditions=outcome.context.copy(),
                actions=([outcome.action_taken] if outcome.action_taken else []),
                success_rate=1.0,
                confidence=0.3,
                discovered_at=time.time(),
                occurrence_count=1,
                success_count=1,
                last_used=time.time(),
            )
            
            self.patterns[pattern_sig] = pattern
            logger.info("Discovered new pattern: %s", pattern.pattern_name)

    def _create_pattern_signature(self, outcome: LearningOutcome) -> str:
        """Create a pattern signature from outcome."""
        # Simplified: use goal + primary context
        return f"{outcome.goal}:{outcome.action_taken or 'default'}"

    def _generate_pattern_description(self, outcome: LearningOutcome) -> str:
        """Generate natural language description of pattern."""
        return (
            f"When goal is '{outcome.goal}' "
            f"with reward {outcome.reward:.2f}, "
            f"action '{outcome.action_taken}' succeeds"
        )

    def _update_performance_metrics(self, outcome: LearningOutcome) -> None:
        """Update performance trend tracking."""
        metric_key = f"{outcome.goal}_success_rate"
        
        if metric_key not in self.performance_trends:
            self.performance_trends[metric_key] = PerformanceTrend(
                metric_name=metric_key,
                values=[],
                timestamps=[],
                trend_direction="stable",
                trend_magnitude=0.0,
            )
        
        trend = self.performance_trends[metric_key]
        success_val = 1.0 if outcome.success else 0.0
        
        trend.values.append(success_val)
        trend.timestamps.append(outcome.timestamp)
        
        # Keep only recent values
        cutoff_time = time.time() - self.memory_window.total_seconds()
        while trend.timestamps and trend.timestamps[0] < cutoff_time:
            trend.timestamps.pop(0)
            trend.values.pop(0)
        
        # Analyze trend
        self._analyze_trend(trend)

    def _analyze_trend(self, trend: PerformanceTrend) -> None:
        """Analyze performance trend."""
        if len(trend.values) < 2:
            return
        
        # Simple trend: compare first half vs second half
        mid = len(trend.values) // 2
        first_half_avg = sum(trend.values[:mid]) / mid
        second_half_avg = sum(trend.values[mid:]) / len(trend.values[mid:])
        
        improvement = second_half_avg - first_half_avg
        
        if improvement > 0.05:
            trend.trend_direction = "improving"
            trend.trend_magnitude = improvement
        elif improvement < -0.05:
            trend.trend_direction = "declining"
            trend.trend_magnitude = abs(improvement)
        else:
            trend.trend_direction = "stable"
            trend.trend_magnitude = 0.0
        
        # Simple forecast: last value + trend
        if trend.values:
            trend.forecast_value = trend.values[-1] + trend.trend_magnitude

    def _adapt_strategy(self, outcome: LearningOutcome) -> None:
        """Adapt strategy based on outcome."""
        recent_outcomes = [
            o for o in self.outcomes[-20:]
            if o.goal == outcome.goal
        ]
        
        if len(recent_outcomes) < 5:
            return
        
        success_rate = sum(1 for o in recent_outcomes if o.success) / len(recent_outcomes)
        
        adaptation = None
        
        if success_rate > 0.8:
            # Exploit successful strategy more
            adaptation = {
                "timestamp": time.time(),
                "type": "exploit",
                "goal": outcome.goal,
                "reason": f"High success rate: {success_rate:.2f}",
                "recommended_action": "Increase exploitation of successful patterns",
            }
        elif success_rate < 0.3:
            # Need more exploration
            adaptation = {
                "timestamp": time.time(),
                "type": "explore",
                "goal": outcome.goal,
                "reason": f"Low success rate: {success_rate:.2f}",
                "recommended_action": "Increase exploration of new strategies",
            }
        
        if adaptation:
            self.strategy_adaptations.append(adaptation)
            logger.info("Strategy adaptation: %s", adaptation["recommended_action"])

    def get_best_patterns(self, limit: int = 10) -> List[LearnedPattern]:
        """Get best performing patterns."""
        sorted_patterns = sorted(
            self.patterns.values(),
            key=lambda p: p.success_rate * p.confidence,
            reverse=True,
        )
        return sorted_patterns[:limit]

    def get_pattern_recommendations(self, goal: str) -> List[LearnedPattern]:
        """Get pattern recommendations for a goal."""
        matching_patterns = [
            p for p in self.patterns.values()
            if goal in p.description or any(goal in a for a in p.actions)
        ]
        return sorted(
            matching_patterns,
            key=lambda p: p.success_rate * p.confidence,
            reverse=True,
        )

    def get_performance_analysis(self, goal: str) -> Dict[str, Any]:
        """Analyze performance for a goal."""
        goal_outcomes = [o for o in self.outcomes if o.goal == goal]
        
        if not goal_outcomes:
            return {"goal": goal, "status": "no_data"}
        
        successful = sum(1 for o in goal_outcomes if o.success)
        total = len(goal_outcomes)
        success_rate = successful / total
        avg_reward = sum(o.reward for o in goal_outcomes) / total
        
        return {
            "goal": goal,
            "total_attempts": total,
            "successes": successful,
            "success_rate": success_rate,
            "average_reward": avg_reward,
            "best_reward": max(o.reward for o in goal_outcomes),
            "worst_reward": min(o.reward for o in goal_outcomes),
        }

    def get_learning_status(self) -> Dict[str, Any]:
        """Get overall learning status."""
        return {
            "learner_id": self.learner_id,
            "total_outcomes_recorded": len(self.outcomes),
            "patterns_discovered": len(self.patterns),
            "performance_trends_tracked": len(self.performance_trends),
            "strategy_adaptations": len(self.strategy_adaptations),
            "best_patterns": [p.pattern_name for p in self.get_best_patterns(5)],
            "improving_metrics": [
                name for name, trend in self.performance_trends.items()
                if trend.trend_direction == "improving"
            ],
            "declining_metrics": [
                name for name, trend in self.performance_trends.items()
                if trend.trend_direction == "declining"
            ],
        }

    def export_learning_data(self) -> str:
        """Export all learning data as JSON."""
        data = {
            "learner_id": self.learner_id,
            "timestamp": datetime.now().isoformat(),
            "outcomes_count": len(self.outcomes),
            "patterns": [
                {
                    "pattern_name": p.pattern_name,
                    "success_rate": p.success_rate,
                    "confidence": p.confidence,
                    "occurrence_count": p.occurrence_count,
                }
                for p in self.patterns.values()
            ],
            "performance_trends": {
                name: {
                    "trend_direction": trend.trend_direction,
                    "trend_magnitude": trend.trend_magnitude,
                    "forecast": trend.forecast_value,
                }
                for name, trend in self.performance_trends.items()
            },
            "adaptations": self.strategy_adaptations[-10:],  # Last 10
        }
        return json.dumps(data, indent=2, default=str)

    def save_state(self) -> Path:
        """Save learning state to disk."""
        filename = f"learning_state_{int(time.time())}.json"
        filepath = self.state_dir / filename
        
        filepath.write_text(self.export_learning_data())
        logger.info("Saved learning state to %s", filepath)
        
        return filepath
