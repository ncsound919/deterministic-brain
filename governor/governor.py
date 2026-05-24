"""
Deterministic Brain Governor — cross-project task routing and oversight.

This module wraps the DeterministicCodingAgent to serve as the central
governor for all projects in the Billion Business ecosystem. It routes
tasks to the appropriate project/system based on deterministic analysis,
enforces policy gates, and triggers human oversight when confidence
drops below thresholds.

Environment variables:
    OLLAMA_BASE_URL     Base URL for Ollama API (default: http://localhost:11434)
    OLLAMA_MODEL        Ollama model for reasoning tasks (default: deepseek-r1:8b)
    QWEN_MODEL          Qwen model for math/symbolic tasks (default: qwen2.5-math:7b)
    ANTHROPIC_API_KEY   API key for Anthropic Claude (required for Claude provider)
"""

from __future__ import annotations
import os
import json
import logging
import urllib.request
import urllib.error
import socket
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


@dataclass
class GovernorDecision:
    """Result of governor task routing."""
    target_system: str  # openhub, uplift-venture, ul2, aetherdesk, bb-tech
    action: str
    confidence: float
    reasoning: str
    requires_oversight: bool = False
    oversight_mode: str = "shadow"  # shadow, checkpoint, recovery
    selected_provider: str = "claude"
    fallback_reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyGate:
    """Policy enforcement result."""
    allowed: bool
    blocked_by: Optional[str] = None
    reason: str = ""


class ModelRouter:
    """Routes tasks to the optimal AI model provider.

    Ported from Math X's modelRouter.ts (apps/api/src/services/modelRouter.ts).
    Maps task modes to providers:
      - formula/deep-solve  → qwen2.5-math:7b  (symPy specialist via Ollama)
      - scientist/hypothesis/synergy → deepseek-r1:8b  (reasoning via Ollama)
      - default             → claude            (Anthropic SDK)
    """

    MODE_MAP = {
        "deep-solve": {"patterns": ["formula", "equation", "calculate", "derivative", "integral",
                                    "math", "solve", "compute", "algebra", "calculus"]},
        "scientist":  {"patterns": ["research", "hypothesis", "experiment", "analyze", "reason",
                                    "scientist", "archetype", "playbook", "simulation",
                                    "clinical", "bio", "genome"]},
        "synergy":    {"patterns": ["synergy", "cross-project", "integration", "collaboration"]},
    }

    PROVIDER_FOR_MODE = {
        "deep-solve": "qwen",
        "scientist":  "ollama",
        "synergy":    "ollama",
    }

    @staticmethod
    def select_provider(mode: str) -> str:
        """Select the best provider based on the task mode.

        Mirrors Math X's selectProvider(): maps formula/deep-solve to qwen,
        scientist/hypothesis/synergy to ollama, default to claude.
        """
        ollama_available = bool(os.getenv("OLLAMA_BASE_URL", ""))
        mode_lower = mode.lower()

        if mode_lower in ("formula", "deep-solve") and ollama_available:
            return "qwen"
        if mode_lower in ("scientist", "hypothesis", "synergy") and ollama_available:
            return "ollama"
        return "claude"

    @staticmethod
    def check_ollama_health(base_url: str | None = None) -> bool:
        """Check if Ollama is running at the given base URL.

        Mirrors Math X's checkOllamaHealth(). Probes /api/tags with a 2s
        timeout. Returns True if the service responds with HTTP 200.
        """
        url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        try:
            req = urllib.request.Request(f"{url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except (urllib.error.URLError, socket.timeout, OSError):
            return False

    @staticmethod
    def derive_mode_from_task(task: str) -> str:
        """Derive the processing mode from the task description."""
        task_lower = task.lower()

        for mode, config in ModelRouter.MODE_MAP.items():
            if any(p in task_lower for p in config["patterns"]):
                return mode

        return "general"

    @staticmethod
    def get_model_for_provider(provider: str) -> str:
        """Get the model name for a given provider."""
        models = {
            "qwen": os.getenv("QWEN_MODEL", "qwen2.5-math:7b"),
            "ollama": os.getenv("OLLAMA_MODEL", "deepseek-r1:8b"),
            "claude": "claude-sonnet-4-20250514",
        }
        return models.get(provider, "claude")


class ProjectRouter:
    """Routes tasks to the appropriate project based on deterministic analysis."""

    ROUTES = {
        "coding": {
            "patterns": ["code", "function", "class", "component", "api", "endpoint", "build", "deploy", "test"],
            "target": "openhub",
            "action": "pipeline",
        },
        "business_logic": {
            "patterns": ["strategy", "plan", "budget", "revenue", "market", "finance", "marketing", "campaign"],
            "target": "uplift-venture",
            "action": "business_module",
        },
        "community": {
            "patterns": ["community", "member", "feed", "event", "group", "marketplace", "course", "education"],
            "target": "ul2",
            "action": "community_feature",
        },
        "communication": {
            "patterns": ["call", "voice", "agent", "routing", "recording", "sip", "telephony"],
            "target": "aetherdesk",
            "action": "call_center",
        },
        "research": {
            "patterns": ["research", "simulation", "archetype", "playbook", "clinical", "bio", "genome"],
            "target": "bb-tech",
            "action": "research_experiment",
        },
    }

    OVERSIGHT_THRESHOLDS = {
        "openhub": {"confidence": 0.8, "risk_actions": ["deploy", "production_write"]},
        "uplift-venture": {"confidence": 0.7, "risk_actions": ["financial_transaction", "external_api"]},
        "ul2": {"confidence": 0.75, "risk_actions": ["payment", "user_data_export"]},
        "aetherdesk": {"confidence": 0.85, "risk_actions": ["call_recording_access", "agent_config_change"]},
        "bb-tech": {"confidence": 0.9, "risk_actions": ["clinical_output", "patient_facing"]},
    }

    def route(self, task: str, context: Optional[Dict] = None) -> GovernorDecision:
        """Route a task to the appropriate project system."""
        task_lower = task.lower()
        context = context or {}

        best_match = None
        best_score = 0

        for route_name, route_config in self.ROUTES.items():
            score = sum(1 for p in route_config["patterns"] if p in task_lower)
            if score > best_score:
                best_score = score
                best_match = route_config

        if best_match and best_score > 0:
            target = best_match["target"]
            action = best_match["action"]
            confidence = min(0.95, 0.5 + (best_score * 0.1))

            oversight_config = self.OVERSIGHT_THRESHOLDS.get(target, {})
            requires_oversight = confidence < oversight_config.get("confidence", 0.8)

            risk_actions = oversight_config.get("risk_actions", [])
            for ra in risk_actions:
                if ra in task_lower:
                    requires_oversight = True
                    confidence = max(0.1, confidence - 0.2)

            # Select the best AI provider for this task type
            mode = ModelRouter.derive_mode_from_task(task)
            selected_provider = ModelRouter.select_provider(mode)
            fallback_reason = ""

            if selected_provider in ("qwen", "ollama"):
                base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
                if not ModelRouter.check_ollama_health(base_url):
                    fallback_reason = f"Ollama unreachable at {base_url}, fell back to Claude"
                    selected_provider = "claude"

            return GovernorDecision(
                target_system=target,
                action=action,
                confidence=confidence,
                reasoning=f"Matched route '{route_name}' with score {best_score}",
                requires_oversight=requires_oversight,
                oversight_mode="checkpoint" if requires_oversight else "shadow",
                selected_provider=selected_provider,
                fallback_reason=fallback_reason,
                metadata={
                    "route_name": best_match,
                    "match_score": best_score,
                    "mode": mode,
                    "model": ModelRouter.get_model_for_provider(selected_provider),
                },
            )

        return GovernorDecision(
            target_system="uplift-venture",
            action="general",
            confidence=0.3,
            reasoning="No specific route matched, defaulting to uplift-venture",
            requires_oversight=True,
            oversight_mode="checkpoint",
            selected_provider="claude",
            fallback_reason="",
            metadata={"mode": "general", "model": "claude-sonnet-4-20250514"},
        )


class PolicyEngine:
    """Enforces cross-project policy gates."""

    DEFAULT_POLICIES = {
        "budget_gate": {
            "description": "Block actions exceeding financial threshold",
            "threshold": 500,
            "applies_to": ["uplift-venture", "ul2", "aetherdesk"],
        },
        "production_guard": {
            "description": "Require human approval for production changes",
            "applies_to": ["openhub"],
        },
        "data_privacy": {
            "description": "Block actions that expose PII without approval",
            "applies_to": ["openhub", "uplift-venture", "ul2", "aetherdesk"],
        },
        "clinical_guard": {
            "description": "All clinical outputs require human review",
            "applies_to": ["bb-tech"],
        },
    }

    def evaluate(self, decision: GovernorDecision, context: Dict) -> PolicyGate:
        """Evaluate a decision against all applicable policies."""
        target = decision.target_system

        for policy_name, policy_config in self.DEFAULT_POLICIES.items():
            if target not in policy_config.get("applies_to", []):
                continue

            if policy_name == "budget_gate":
                amount = context.get("amount", 0)
                if amount > policy_config.get("threshold", 500):
                    return PolicyGate(
                        allowed=False,
                        blocked_by=policy_name,
                        reason=f"Amount ${amount} exceeds ${policy_config['threshold']} threshold",
                    )

            if policy_name == "clinical_guard":
                return PolicyGate(
                    allowed=False,
                    blocked_by=policy_name,
                    reason="Clinical outputs require human review",
                )

            if policy_name == "production_guard":
                if "production" in context.get("environment", "").lower():
                    return PolicyGate(
                        allowed=False,
                        blocked_by=policy_name,
                        reason="Production changes require human approval",
                    )

        return PolicyGate(allowed=True)


class DeterministicGovernor:
    """
    Central governor for the Billion Business ecosystem.

    Uses Deterministic-Brain's MoE Router for task classification,
    routes to the appropriate project system, and enforces policy gates
    with human oversight triggers.
    """

    def __init__(self, skills_root: str = "skill_packs"):
        self.router = ProjectRouter()
        self.policy_engine = PolicyEngine()
        self.adapters: Dict[str, BaseAdapter] = {}

        try:
            from orchestration.dca_engine import DeterministicCodingAgent
            self.dca = DeterministicCodingAgent(skills_root=skills_root)
            self.dca_available = True
        except Exception as e:
            logger.warning("DCA engine not available: %s", e)
            self.dca = None
            self.dca_available = False

    def register_adapter(self, target: str, adapter: BaseAdapter) -> None:
        """Register an adapter for a governor target system."""
        self.adapters[target] = adapter

    def get_adapter(self, target: str) -> Optional[BaseAdapter]:
        return self.adapters.get(target)

    def handle(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Main entry point: route task, check policies, trigger oversight.

        Returns a structured decision with execution guidance.
        """
        context = context or {}

        decision = self.router.route(task, context)
        policy_result = self.policy_engine.evaluate(decision, context)

        if not policy_result.allowed:
            return {
                "status": "blocked",
                "blocked_by": policy_result.blocked_by,
                "reason": policy_result.reason,
                "decision": {
                    "target_system": decision.target_system,
                    "action": decision.action,
                    "confidence": decision.confidence,
                    "selected_provider": decision.selected_provider,
                    "fallback_reason": decision.fallback_reason,
                },
            }

        if decision.requires_oversight:
            return {
                "status": "awaiting_oversight",
                "oversight_mode": decision.oversight_mode,
                "decision": {
                    "target_system": decision.target_system,
                    "action": decision.action,
                    "confidence": decision.confidence,
                    "reasoning": decision.reasoning,
                    "selected_provider": decision.selected_provider,
                    "fallback_reason": decision.fallback_reason,
                },
                "oversight_payload": {
                    "action": decision.action,
                    "agent": "deterministic-governor",
                    "reason": decision.reasoning,
                    "confidence": decision.confidence,
                    "risk": "high" if decision.confidence < 0.5 else "medium" if decision.confidence < 0.7 else "low",
                    "target_system": decision.target_system,
                },
            }

        if self.dca_available:
            try:
                result = self.dca.handle(task)
                return {
                    "status": "executed",
                    "decision": {
                        "target_system": decision.target_system,
                        "action": decision.action,
                        "confidence": decision.confidence,
                        "selected_provider": decision.selected_provider,
                        "fallback_reason": decision.fallback_reason,
                    },
                    "execution_result": result,
                }
            except Exception as e:
                return {
                    "status": "error",
                    "error": str(e),
                    "decision": {
                        "target_system": decision.target_system,
                        "action": decision.action,
                        "confidence": decision.confidence,
                        "selected_provider": decision.selected_provider,
                        "fallback_reason": decision.fallback_reason,
                    },
                }

        return {
            "status": "routed",
            "decision": {
                "target_system": decision.target_system,
                "action": decision.action,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
                "selected_provider": decision.selected_provider,
                "fallback_reason": decision.fallback_reason,
            },
            "next_step": f"Execute {decision.action} on {decision.target_system}",
        }

    def get_system_status(self) -> Dict[str, Any]:
        """Get status of all managed systems."""
        return {
            "governor": "active",
            "dca_engine": "available" if self.dca_available else "unavailable",
            "policies": len(self.policy_engine.DEFAULT_POLICIES),
            "routes": len(self.router.ROUTES),
            "systems": list(self.router.ROUTES.keys()),
        }


def get_governor() -> DeterministicGovernor:
    """Get or create the singleton governor instance."""
    if not hasattr(get_governor, "_instance"):
        get_governor._instance = DeterministicGovernor()
    return get_governor._instance
