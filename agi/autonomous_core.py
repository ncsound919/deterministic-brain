"""
Autonomous Core: AGI-like Metacognitive Reasoning Loop
=======================================================

The core reasoning engine that mimics AGI behavior through:
1. Observation -> understanding the current state
2. Reasoning -> developing multiple solution paths
3. Deliberation -> evaluating options probabilistically
4. Action -> executing determined plan
5. Reflection -> learning from outcome
6. Meta-reasoning -> improving reasoning process itself
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class CognitionState(str, Enum):
    """Cognitive states of the autonomous mind."""
    IDLE = "idle"
    OBSERVING = "observing"
    REASONING = "reasoning"
    DELIBERATING = "deliberating"
    ACTING = "acting"
    REFLECTING = "reflecting"
    META_REASONING = "meta_reasoning"
    LEARNING = "learning"


class ReasoningQuality(str, Enum):
    """Quality of reasoning process."""
    POOR = "poor"  # Low confidence, limited exploration
    FAIR = "fair"  # Moderate confidence, some exploration
    GOOD = "good"  # High confidence, well explored
    EXCELLENT = "excellent"  # Very high confidence, well validated


@dataclass
class Observation:
    """Represents a state observation."""
    timestamp: float = field(default_factory=time.time)
    observation_type: str = ""
    content: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['timestamp'] = self.timestamp
        return d


@dataclass
class ReasoningPath:
    """A potential solution path discovered during reasoning."""
    path_id: str
    description: str
    required_actions: List[str]
    estimated_success_rate: float  # 0.0 to 1.0
    risk_level: str  # low, medium, high
    resource_cost: float
    reasoning_depth: int  # how many steps ahead considered
    supporting_evidence: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AutonomousMind:
    """State of the autonomous mind."""
    mind_id: str
    cognition_state: CognitionState = CognitionState.IDLE
    current_observation: Optional[Observation] = None
    reasoning_paths: List[ReasoningPath] = field(default_factory=list)
    selected_path: Optional[ReasoningPath] = None
    current_goal: Optional[str] = None
    active_plan: Optional[Dict[str, Any]] = None
    
    # Metacognition
    reasoning_quality: ReasoningQuality = ReasoningQuality.FAIR
    self_awareness_level: float = 0.5  # 0.0 to 1.0
    goal_coherence: float = 1.0  # how well goals align
    uncertainty_level: float = 0.5  # epistemic uncertainty
    
    # Learning state
    success_history: List[Dict[str, Any]] = field(default_factory=list)
    failure_history: List[Dict[str, Any]] = field(default_factory=list)
    learned_patterns: Dict[str, Any] = field(default_factory=dict)
    
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)


class AutonomousCore:
    """
    The AGI-like autonomous reasoning core.
    
    Implements the cognitive loop:
    Observe → Reason → Deliberate → Act → Reflect → Meta-Reason → Learn
    """

    def __init__(
        self,
        mind_id: str = "default-mind",
        reasoning_depth: int = 5,
        max_reasoning_paths: int = 10,
        state_dir: Optional[Path] = None,
    ):
        self.mind_id = mind_id
        self.reasoning_depth = reasoning_depth
        self.max_reasoning_paths = max_reasoning_paths
        self.state_dir = Path(state_dir or Path.cwd() / ".autonomous_core")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.mind = AutonomousMind(mind_id=mind_id)
        self._history = []
        self._reasoning_cache = {}
        
        logger.info("AutonomousCore initialized (mind_id=%s, depth=%d)", mind_id, reasoning_depth)

    def observe(self, observation: Observation) -> None:
        """
        Step 1: Observe the current state.
        Updates mind with new observation and context.
        """
        self.mind.cognition_state = CognitionState.OBSERVING
        self.mind.current_observation = observation
        
        logger.info(
            "Observing: type=%s, confidence=%.2f, source=%s",
            observation.observation_type,
            observation.confidence,
            observation.source,
        )

    def reason(self, goal: str, context: Optional[Dict[str, Any]] = None) -> List[ReasoningPath]:
        """
        Step 2: Reason about multiple solution paths.
        Uses depth-first exploration with branching.
        """
        self.mind.cognition_state = CognitionState.REASONING
        self.mind.current_goal = goal
        context = context or {}
        
        logger.info("Beginning reasoning process for goal: %s", goal)
        
        reasoning_paths = self._explore_reasoning_space(goal, context)
        
        # Rank by estimated success rate
        reasoning_paths.sort(key=lambda p: p.estimated_success_rate, reverse=True)
        self.mind.reasoning_paths = reasoning_paths[:self.max_reasoning_paths]
        
        # Update reasoning quality based on exploration
        self.mind.reasoning_quality = self._assess_reasoning_quality(reasoning_paths)
        
        logger.info(
            "Reasoning complete: found %d paths, quality=%s",
            len(reasoning_paths),
            self.mind.reasoning_quality.value,
        )
        
        return self.mind.reasoning_paths

    def _explore_reasoning_space(
        self,
        goal: str,
        context: Dict[str, Any],
        depth: int = 0,
        parent_evidence: Optional[List[str]] = None,
    ) -> List[ReasoningPath]:
        """
        Recursively explore reasoning space.
        Mimics human reasoning by expanding possibilities.
        """
        parent_evidence = parent_evidence or []
        paths = []

        if depth >= self.reasoning_depth:
            return paths

        # Generate potential actions/steps
        action_options = self._generate_action_options(goal, context, depth)

        for action_idx, action in enumerate(action_options):
            path_id = f"{self.mind_id}-path-{depth}-{action_idx}"
            
            # Estimate success
            success_rate = self._estimate_success(action, context, parent_evidence)
            risk = self._assess_risk(action, context)
            cost = self._estimate_cost(action, context)
            
            # Generate evidence for this path
            supporting_evidence = parent_evidence + [f"{depth}: {action['description']}"]
            
            path = ReasoningPath(
                path_id=path_id,
                description=action["description"],
                required_actions=action.get("steps", [action["description"]]),
                estimated_success_rate=success_rate,
                risk_level=risk,
                resource_cost=cost,
                reasoning_depth=depth,
                supporting_evidence=supporting_evidence,
            )
            paths.append(path)
            
            # Recursive exploration for promising paths
            if success_rate > 0.4 and depth < self.reasoning_depth - 1:
                sub_context = context.copy()
                sub_context["prior_action"] = action
                subpaths = self._explore_reasoning_space(
                    goal,
                    sub_context,
                    depth + 1,
                    supporting_evidence,
                )
                paths.extend(subpaths)

        return paths

    def _generate_action_options(
        self,
        goal: str,
        context: Dict[str, Any],
        depth: int,
    ) -> List[Dict[str, Any]]:
        """Generate possible actions at this reasoning level."""
        # This would integrate with your skill registry in real implementation
        options = [
            {
                "description": f"Direct approach: execute skill for '{goal}'",
                "steps": ["lookup_skill", "validate_preconditions", "execute"],
                "type": "direct",
            },
            {
                "description": f"Decompose goal '{goal}' into sub-goals",
                "steps": ["analyze_goal", "identify_subgoals", "create_plan"],
                "type": "decomposition",
            },
            {
                "description": f"Search for analogous solutions",
                "steps": ["search_history", "find_analogs", "adapt_solution"],
                "type": "analogy",
            },
        ]
        
        if depth > 0:
            options.append({
                "description": f"Backtrack and retry with different approach",
                "steps": ["analyze_failure", "adjust_parameters", "retry"],
                "type": "backtrack",
            })
        
        return options

    def _estimate_success(
        self,
        action: Dict[str, Any],
        context: Dict[str, Any],
        evidence: List[str],
    ) -> float:
        """Estimate probability of success for an action."""
        base_success = 0.6
        
        # Adjust based on action type
        action_type = action.get("type", "unknown")
        if action_type == "direct":
            base_success = 0.7
        elif action_type == "decomposition":
            base_success = 0.6
        elif action_type == "analogy":
            base_success = 0.55
        
        # Adjust based on context
        if context.get("prior_failures"):
            base_success *= 0.8
        
        if context.get("prior_successes"):
            base_success *= 1.1
        
        # Cap at [0, 1]
        return min(max(base_success, 0.0), 1.0)

    def _assess_risk(self, action: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Assess risk level of an action."""
        action_type = action.get("type", "unknown")
        
        if action_type == "direct":
            return "low"
        elif action_type == "decomposition":
            return "medium"
        elif action_type == "analogy":
            return "medium"
        else:
            return "high"

    def _estimate_cost(self, action: Dict[str, Any], context: Dict[str, Any]) -> float:
        """Estimate computational/resource cost."""
        action_type = action.get("type", "unknown")
        base_cost = 1.0
        
        if action_type == "direct":
            base_cost = 1.0
        elif action_type == "decomposition":
            base_cost = 3.0
        elif action_type == "analogy":
            base_cost = 2.5
        
        return base_cost

    def _assess_reasoning_quality(self, paths: List[ReasoningPath]) -> ReasoningQuality:
        """Assess quality of reasoning process."""
        if not paths:
            return ReasoningQuality.POOR
        
        avg_success = sum(p.estimated_success_rate for p in paths) / len(paths)
        avg_depth = sum(p.reasoning_depth for p in paths) / len(paths)
        
        if avg_success > 0.7 and avg_depth > 3:
            return ReasoningQuality.EXCELLENT
        elif avg_success > 0.6 and avg_depth > 2:
            return ReasoningQuality.GOOD
        elif avg_success > 0.5:
            return ReasoningQuality.FAIR
        else:
            return ReasoningQuality.POOR

    def deliberate(self) -> ReasoningPath:
        """
        Step 3: Deliberate - select best path.
        Uses multi-criteria decision making.
        """
        self.mind.cognition_state = CognitionState.DELIBERATING
        
        if not self.mind.reasoning_paths:
            raise ValueError("No reasoning paths to deliberate over")
        
        # Score each path: (success_rate * 0.5) + (low_cost * 0.3) + (low_risk * 0.2)
        scored_paths = []
        for path in self.mind.reasoning_paths:
            risk_score = 1.0 if path.risk_level == "low" else (0.6 if path.risk_level == "medium" else 0.2)
            cost_score = 1.0 - min(path.resource_cost / 10.0, 1.0)
            
            total_score = (
                path.estimated_success_rate * 0.5 +
                cost_score * 0.3 +
                risk_score * 0.2
            )
            scored_paths.append((total_score, path))
        
        scored_paths.sort(key=lambda x: x[0], reverse=True)
        selected = scored_paths[0][1]
        
        self.mind.selected_path = selected
        self.mind.uncertainty_level = 1.0 - selected.estimated_success_rate
        
        logger.info(
            "Deliberation complete: selected path '%s' (success=%.2f, risk=%s)",
            selected.path_id,
            selected.estimated_success_rate,
            selected.risk_level,
        )
        
        return selected

    def reflect(self, outcome: Dict[str, Any]) -> None:
        """
        Step 5: Reflect on action outcome.
        Updates mind state and prepares for learning.
        """
        self.mind.cognition_state = CognitionState.REFLECTING
        
        success = outcome.get("success", False)
        reward = outcome.get("reward", 0.0)
        
        if success:
            self.mind.success_history.append({
                "timestamp": time.time(),
                "path_id": self.mind.selected_path.path_id if self.mind.selected_path else None,
                "goal": self.mind.current_goal,
                "outcome": outcome,
                "reward": reward,
            })
        else:
            self.mind.failure_history.append({
                "timestamp": time.time(),
                "path_id": self.mind.selected_path.path_id if self.mind.selected_path else None,
                "goal": self.mind.current_goal,
                "outcome": outcome,
            })
        
        logger.info(
            "Reflection: success=%s, reward=%.2f, total_successes=%d",
            success,
            reward,
            len(self.mind.success_history),
        )

    def meta_reason(self) -> Dict[str, Any]:
        """
        Step 6: Meta-reasoning - improve reasoning process itself.
        Analyzes reasoning effectiveness and adjusts approach.
        """
        self.mind.cognition_state = CognitionState.META_REASONING
        
        insights = {}
        
        # Analyze success patterns
        if self.mind.success_history:
            success_rates = {}
            for success in self.mind.success_history[-10:]:
                path_id = success.get("path_id", "unknown")
                success_rates[path_id] = success_rates.get(path_id, 0) + 1
            
            insights["successful_paths"] = success_rates
        
        # Analyze failure patterns
        if self.mind.failure_history:
            failure_types = {}
            for failure in self.mind.failure_history[-10:]:
                error = failure.get("outcome", {}).get("error", "unknown")
                failure_types[error] = failure_types.get(error, 0) + 1
            
            insights["failure_patterns"] = failure_types
        
        # Update self-awareness
        total_attempts = len(self.mind.success_history) + len(self.mind.failure_history)
        if total_attempts > 0:
            success_rate = len(self.mind.success_history) / total_attempts
            self.mind.self_awareness_level = min(0.95, 0.5 + success_rate * 0.4)
        
        # Adjust reasoning depth if needed
        if self.mind.reasoning_quality == ReasoningQuality.POOR:
            self.reasoning_depth = min(self.reasoning_depth + 1, 10)
            logger.info("Increasing reasoning depth to %d due to poor quality", self.reasoning_depth)
        
        logger.info("Meta-reasoning insights: %s", json.dumps(insights, default=str))
        
        return insights

    def learn(self, pattern: str, evidence: Dict[str, Any]) -> None:
        """
        Step 7: Learn - encode successful patterns.
        Updates learned_patterns for future use.
        """
        self.mind.cognition_state = CognitionState.LEARNING
        
        self.mind.learned_patterns[pattern] = {
            "learned_at": time.time(),
            "evidence": evidence,
            "confidence": evidence.get("confidence", 0.5),
            "success_count": evidence.get("success_count", 0),
        }
        
        logger.info("Learned pattern: %s (confidence=%.2f)", pattern, evidence.get("confidence", 0.5))

    def save_state(self) -> Path:
        """Save mind state to disk for persistence."""
        state_file = self.state_dir / f"mind_state_{int(time.time())}.json"
        
        state = {
            "mind_id": self.mind_id,
            "cognition_state": self.mind.cognition_state.value,
            "current_goal": self.mind.current_goal,
            "reasoning_quality": self.mind.reasoning_quality.value,
            "self_awareness_level": self.mind.self_awareness_level,
            "success_count": len(self.mind.success_history),
            "failure_count": len(self.mind.failure_history),
            "learned_patterns": list(self.mind.learned_patterns.keys()),
            "timestamp": datetime.now().isoformat(),
        }
        
        state_file.write_text(json.dumps(state, indent=2))
        logger.info("Saved mind state to %s", state_file)
        
        return state_file

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the autonomous mind."""
        return {
            "mind_id": self.mind_id,
            "cognition_state": self.mind.cognition_state.value,
            "current_goal": self.mind.current_goal,
            "reasoning_quality": self.mind.reasoning_quality.value,
            "self_awareness_level": self.mind.self_awareness_level,
            "uncertainty_level": self.mind.uncertainty_level,
            "success_history_size": len(self.mind.success_history),
            "failure_history_size": len(self.mind.failure_history),
            "learned_patterns_count": len(self.mind.learned_patterns),
            "active_reasoning_paths": len(self.mind.reasoning_paths),
        }
