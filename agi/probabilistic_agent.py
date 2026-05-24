"""
Probabilistic Agent: Uncertainty-Aware Decision Making
======================================================

Handles probabilistic reasoning with:
- Bayesian decision making under uncertainty
- Multi-armed bandit strategies
- Confidence-based action selection
- Risk management and exploration-exploitation trade-off
"""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class DecisionStrategy(str, Enum):
    """Strategy for probabilistic decision making."""
    EXPLOIT = "exploit"  # Choose best known option
    EXPLORE = "explore"  # Try uncertain options for learning
    BALANCED = "balanced"  # UCB-based balance
    THOMPSON = "thompson"  # Thompson sampling


class ConfidenceLevel(str, Enum):
    """Confidence levels for decisions."""
    VERY_LOW = "very_low"      # < 0.3
    LOW = "low"                # 0.3-0.5
    MEDIUM = "medium"          # 0.5-0.7
    HIGH = "high"              # 0.7-0.85
    VERY_HIGH = "very_high"    # > 0.85


@dataclass
class ProbabilisticDecision:
    """A decision with probabilistic properties."""
    decision_id: str
    action: str
    success_probability: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    risk_level: float  # 0.0 to 1.0
    expected_reward: float
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    last_used: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    
    def get_confidence_level(self) -> ConfidenceLevel:
        """Get confidence level category."""
        if self.confidence < 0.3:
            return ConfidenceLevel.VERY_LOW
        elif self.confidence < 0.5:
            return ConfidenceLevel.LOW
        elif self.confidence < 0.7:
            return ConfidenceLevel.MEDIUM
        elif self.confidence < 0.85:
            return ConfidenceLevel.HIGH
        else:
            return ConfidenceLevel.VERY_HIGH
    
    def update_outcome(self, success: bool, reward: float = 0.0):
        """Update decision statistics after execution."""
        self.attempts += 1
        self.last_used = time.time()
        
        if success:
            self.successes += 1
            self.expected_reward = (self.expected_reward * 0.9) + (reward * 0.1)
            # Increase confidence on success
            self.confidence = min(1.0, self.confidence + 0.05)
        else:
            self.failures += 1
            # Decrease confidence on failure
            self.confidence = max(0.0, self.confidence - 0.1)
        
        # Update success probability based on empirical data
        if self.attempts > 0:
            self.success_probability = self.successes / self.attempts
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['confidence_level'] = self.get_confidence_level().value
        return d


@dataclass
class BayesianBelief:
    """Bayesian belief about a proposition."""
    proposition: str
    prior: float = 0.5  # Prior probability
    likelihood_ratio: float = 1.0  # P(evidence | true) / P(evidence | false)
    evidence_count: int = 0
    posterior: float = field(default=0.5, init=False)
    
    def update(self, evidence: bool, strength: float = 1.0) -> None:
        """Update belief based on evidence."""
        # Simple Bayesian update
        if evidence:
            self.likelihood_ratio *= (1.0 + strength)
        else:
            self.likelihood_ratio /= (1.0 + strength)
        
        self.evidence_count += 1
        self._calculate_posterior()
    
    def _calculate_posterior(self) -> None:
        """Calculate posterior probability."""
        # P(H|E) = P(E|H) * P(H) / [P(E|H) * P(H) + P(E|~H) * P(~H)]
        numerator = self.likelihood_ratio * self.prior
        denominator = numerator + (1.0 - self.prior)
        self.posterior = numerator / denominator if denominator > 0 else 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposition": self.proposition,
            "prior": self.prior,
            "posterior": self.posterior,
            "likelihood_ratio": self.likelihood_ratio,
            "evidence_count": self.evidence_count,
        }


class ProbabilisticAgent:
    """
    Agent that makes decisions under uncertainty using probability theory.
    
    Implements:
    - Multi-armed bandit algorithms (UCB, Thompson Sampling)
    - Bayesian belief updating
    - Risk-aware action selection
    - Exploration-exploitation balance
    """

    def __init__(
        self,
        agent_id: str = "probabilistic-agent",
        exploration_rate: float = 0.15,
        strategy: DecisionStrategy = DecisionStrategy.BALANCED,
    ):
        self.agent_id = agent_id
        self.exploration_rate = exploration_rate
        self.strategy = strategy
        
        self.decisions: Dict[str, ProbabilisticDecision] = {}
        self.beliefs: Dict[str, BayesianBelief] = {}
        self.decision_history: List[Dict[str, Any]] = []
        
        logger.info(
            "ProbabilisticAgent initialized (id=%s, strategy=%s, explore_rate=%.2f)",
            agent_id,
            strategy.value,
            exploration_rate,
        )

    def register_decision(
        self,
        action: str,
        success_probability: float = 0.5,
        expected_reward: float = 0.0,
        risk_level: float = 0.5,
    ) -> ProbabilisticDecision:
        """Register a possible decision/action."""
        decision_id = f"{self.agent_id}-{action}"
        
        decision = ProbabilisticDecision(
            decision_id=decision_id,
            action=action,
            success_probability=success_probability,
            confidence=0.3,  # Start with low confidence
            risk_level=risk_level,
            expected_reward=expected_reward,
        )
        
        self.decisions[decision_id] = decision
        logger.info("Registered decision: %s (prob=%.2f)", action, success_probability)
        
        return decision

    def select_action(self, context: Optional[Dict[str, Any]] = None) -> ProbabilisticDecision:
        """
        Select best action using current strategy.
        
        Strategies:
        - EXPLOIT: Select action with highest expected reward
        - EXPLORE: Select random action for learning
        - BALANCED: UCB-based selection
        - THOMPSON: Thompson sampling
        """
        context = context or {}
        
        if not self.decisions:
            raise ValueError("No decisions registered")
        
        if self.strategy == DecisionStrategy.EXPLOIT:
            return self._exploit()
        elif self.strategy == DecisionStrategy.EXPLORE:
            return self._explore()
        elif self.strategy == DecisionStrategy.BALANCED:
            return self._balanced_ucb()
        elif self.strategy == DecisionStrategy.THOMPSON:
            return self._thompson_sampling()
        else:
            return self._exploit()

    def _exploit(self) -> ProbabilisticDecision:
        """Exploit: choose action with highest expected value."""
        best_decision = max(
            self.decisions.values(),
            key=lambda d: d.expected_reward * d.confidence,
        )
        return best_decision

    def _explore(self) -> ProbabilisticDecision:
        """Explore: choose random action."""
        return random.choice(list(self.decisions.values()))

    def _balanced_ucb(self) -> ProbabilisticDecision:
        """
        Balanced selection using Upper Confidence Bound (UCB).
        
        UCB = average_reward + c * sqrt(ln(N) / n)
        where N = total trials, n = action trials, c = exploration constant
        """
        total_attempts = sum(d.attempts for d in self.decisions.values())
        
        if total_attempts == 0:
            return random.choice(list(self.decisions.values()))
        
        best_ucb = -float('inf')
        best_decision = None
        
        for decision in self.decisions.values():
            if decision.attempts == 0:
                # Prefer untried actions
                ucb = float('inf')
            else:
                exploitation = decision.expected_reward
                exploration_bonus = 1.414 * (
                    (total_attempts ** 0.5) / decision.attempts
                ) ** 0.5
                ucb = exploitation + exploration_bonus
            
            if ucb > best_ucb:
                best_ucb = ucb
                best_decision = decision
        
        return best_decision

    def _thompson_sampling(self) -> ProbabilisticDecision:
        """
        Thompson Sampling: sample from posterior distribution of each action.
        """
        best_sample = -float('inf')
        best_decision = None
        
        for decision in self.decisions.values():
            # Sample from Beta distribution approximation
            # Using success/failure counts
            alpha = decision.successes + 1
            beta = decision.failures + 1
            
            # Simple approximation: random sample from Beta
            sample = random.betavariate(alpha, beta) if (alpha > 0 or beta > 0) else 0.5
            
            if sample > best_sample:
                best_sample = sample
                best_decision = decision
        
        return best_decision

    def update_belief(self, proposition: str, evidence: bool, strength: float = 1.0) -> None:
        """Update Bayesian belief based on evidence."""
        if proposition not in self.beliefs:
            self.beliefs[proposition] = BayesianBelief(proposition)
        
        self.beliefs[proposition].update(evidence, strength)
        logger.info(
            "Updated belief '%s': posterior=%.3f",
            proposition,
            self.beliefs[proposition].posterior,
        )

    def get_belief_probability(self, proposition: str) -> float:
        """Get current belief probability for a proposition."""
        if proposition not in self.beliefs:
            return 0.5  # Neutral prior
        
        return self.beliefs[proposition].posterior

    def record_outcome(
        self,
        decision: ProbabilisticDecision,
        success: bool,
        reward: float = 0.0,
        feedback: Optional[str] = None,
    ) -> None:
        """Record outcome of decision execution."""
        decision.update_outcome(success, reward)
        
        self.decision_history.append({
            "timestamp": time.time(),
            "decision_id": decision.decision_id,
            "action": decision.action,
            "success": success,
            "reward": reward,
            "confidence_before": decision.confidence,
            "feedback": feedback,
        })
        
        logger.info(
            "Decision outcome: action=%s, success=%s, reward=%.2f, confidence=%.2f",
            decision.action,
            success,
            reward,
            decision.confidence,
        )

    def get_decision_metrics(self) -> Dict[str, Any]:
        """Get metrics about decision making."""
        total_attempts = sum(d.attempts for d in self.decisions.values())
        total_successes = sum(d.successes for d in self.decisions.values())
        
        return {
            "agent_id": self.agent_id,
            "strategy": self.strategy.value,
            "total_decisions_registered": len(self.decisions),
            "total_attempts": total_attempts,
            "total_successes": total_successes,
            "overall_success_rate": (
                total_successes / total_attempts if total_attempts > 0 else 0
            ),
            "average_confidence": (
                sum(d.confidence for d in self.decisions.values()) / len(self.decisions)
                if self.decisions else 0
            ),
            "beliefs_count": len(self.beliefs),
        }

    def get_decision_status(self, decision_id: Optional[str] = None) -> Dict[str, Any]:
        """Get status of decision(s)."""
        if decision_id:
            if decision_id not in self.decisions:
                return {}
            decision = self.decisions[decision_id]
            return decision.to_dict()
        
        return {
            decision_id: decision.to_dict()
            for decision_id, decision in self.decisions.items()
        }

    def get_beliefs_status(self) -> Dict[str, Any]:
        """Get status of all beliefs."""
        return {
            proposition: belief.to_dict()
            for proposition, belief in self.beliefs.items()
        }

    def get_recommended_strategy(self) -> DecisionStrategy:
        """
        Recommend strategy based on current decision quality.
        """
        metrics = self.get_decision_metrics()
        success_rate = metrics.get("overall_success_rate", 0)
        
        if success_rate > 0.8:
            # Exploit well-performing actions
            return DecisionStrategy.EXPLOIT
        elif success_rate < 0.4:
            # Need more exploration
            return DecisionStrategy.EXPLORE
        else:
            # Balanced approach
            return DecisionStrategy.BALANCED

    def export_decisions(self) -> str:
        """Export decision data as JSON."""
        data = {
            "agent_id": self.agent_id,
            "timestamp": datetime.now().isoformat(),
            "strategy": self.strategy.value,
            "decisions": {
                k: v.to_dict() for k, v in self.decisions.items()
            },
            "beliefs": {
                k: v.to_dict() for k, v in self.beliefs.items()
            },
            "metrics": self.get_decision_metrics(),
        }
        return json.dumps(data, indent=2, default=str)
