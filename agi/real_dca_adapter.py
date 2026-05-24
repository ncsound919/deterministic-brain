from __future__ import annotations
import logging
from typing import Dict, Any, List
from agi.deterministic_executor import DeterministicExecutor, ActionStep, ActionType

logger = logging.getLogger(__name__)

def register_acquisition_tracker_actions(executor: DeterministicExecutor) -> None:
    """Register acquisition tracker auto-update actions into the AGI OS executor."""

    def track_daily_progress_handler(parameters: Dict[str, Any], execution_context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Acquisition tracker: logging daily autonomous progress")
        from acquisition_bridge import AcquisitionBridge
        bridge = AcquisitionBridge()
        bridge.log_autonomous_session({
            "brain_state": parameters.get("brain_state", "autonomous"),
            "tasks_executed": parameters.get("tasks_executed", 0),
            "trends_detected": parameters.get("trends_detected", 0),
            "portfolio_pulse": parameters.get("portfolio_pulse", "stable"),
        })
        return {"success": True, "action": "daily_progress_logged"}

    def track_health_sync_handler(parameters: Dict[str, Any], execution_context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Acquisition tracker: syncing portfolio health")
        from acquisition_bridge import AcquisitionBridge
        bridge = AcquisitionBridge()
        result = bridge.scan_and_sync()
        bridge.update_portfolio_progress(parameters.get("assets", {}))
        return {"success": True, "health": result.get("health"), "action": "health_synced"}

    def track_insight_handler(parameters: Dict[str, Any], execution_context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Acquisition tracker: recording insight")
        from acquisition_bridge import AcquisitionBridge
        bridge = AcquisitionBridge()
        bridge.record_insight(
            signal_type=parameters.get("signal_type", "autonomous"),
            signal=parameters.get("signal", ""),
            implication=parameters.get("implication", ""),
            action=parameters.get("action", "monitor"),
        )
        return {"success": True, "action": "insight_recorded"}

    def track_metrics_refresh_handler(parameters: Dict[str, Any], execution_context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Acquisition tracker: refreshing metrics")
        from acquisition_bridge import AcquisitionBridge
        bridge = AcquisitionBridge()
        bridge.refresh_metrics(parameters.get("scores", {}))
        return {"success": True, "action": "metrics_refreshed"}

    executor.register_action("track_daily_progress", track_daily_progress_handler)
    executor.register_action("track_health_sync", track_health_sync_handler)
    executor.register_action("track_insight", track_insight_handler)
    executor.register_action("track_metrics_refresh", track_metrics_refresh_handler)
    logger.info("Acquisition tracker actions registered into AGI OS DeterministicExecutor.")


def register_real_dca_actions(executor: DeterministicExecutor) -> None:
    """Register actual operational DCA capabilities into the AGI OS executor."""
    
    def run_dca_query_handler(parameters: Dict[str, Any], execution_context: Dict[str, Any]) -> Dict[str, Any]:
        query = parameters.get("query")
        if not query:
            raise ValueError("Query parameter is required")
        logger.info("Executing AGI OS real DCA query: '%s'", query)
        from orchestration.dca_engine import DeterministicCodingAgent
        agent = DeterministicCodingAgent()
        result = agent.handle(query)
        return result
    
    def execute_chain_handler(parameters: Dict[str, Any], execution_context: Dict[str, Any]) -> Dict[str, Any]:
        chain_name = parameters.get("chain_name")
        if not chain_name:
            raise ValueError("Chain name parameter is required")
        logger.info("Executing AGI OS real skill chain: '%s'", chain_name)
        from features.skill_chains_loader import execute_chain
        result = execute_chain(chain_name)
        return result
    
    def run_autodream_handler(parameters: Dict[str, Any], execution_context: Dict[str, Any]) -> Dict[str, Any]:
        dry_run = parameters.get("dry_run", False)
        logger.info("Running AGI OS real autoDream (dry_run=%s)", dry_run)
        from brain.autodream import run_autodream
        result = run_autodream(dry_run=dry_run)
        return result
    
    def system_health_check_handler(parameters: Dict[str, Any], execution_context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing AGI OS system health check...")
        from brain.health_check import run_health_check
        result = run_health_check()
        return {
            "success": result.passed,
            "passed": result.passed,
            "errors": result.errors,
            "warnings": result.warnings,
            "checks_run": len(result.checks)
        }

    executor.register_action("run_dca_query", run_dca_query_handler)
    executor.register_action("execute_chain", execute_chain_handler)
    executor.register_action("run_autodream", run_autodream_handler)
    executor.register_action("system_health_check", system_health_check_handler)
    logger.info("All real DCA actions successfully registered into AGI OS DeterministicExecutor.")


def map_goal_to_steps(goal: str, context: Optional[Dict[str, Any]] = None) -> List[ActionStep]:
    """
    Intelligently inspects a high-level goal and generates the list of 
    concrete ActionSteps to solve it using real system capabilities.
    """
    context = context or {}
    steps = []
    goal_lower = goal.lower()
    
    # 1. Autodream & maintenance
    if "autodream" in goal_lower or "maintenance" in goal_lower or "memory" in goal_lower:
        steps.append(
            ActionStep(
                step_id="step-health-pre",
                action_name="system_health_check",
                action_type=ActionType.IDEMPOTENT,
                parameters={}
            )
        )
        steps.append(
            ActionStep(
                step_id="step-autodream-run",
                action_name="run_autodream",
                action_type=ActionType.TRANSACTIONAL,
                parameters={"dry_run": False}
            )
        )
    
    # 2. System health / Auditing / Self-healing
    elif "health" in goal_lower or "audit" in goal_lower or "heal" in goal_lower:
        steps.append(
            ActionStep(
                step_id="step-health-check",
                action_name="system_health_check",
                action_type=ActionType.IDEMPOTENT,
                parameters={}
            )
        )
        # Follow up by running self-audit skill chain
        steps.append(
            ActionStep(
                step_id="step-self-audit-chain",
                action_name="execute_chain",
                action_type=ActionType.DETERMINISTIC,
                parameters={"chain_name": "system-self-audit"}
            )
        )
    
    # 3. Chains categories (Marketing, Promotion, Networking, SaaS, System)
    elif "marketing" in goal_lower:
        steps.append(
            ActionStep(
                step_id="step-marketing-chain",
                action_name="execute_chain",
                action_type=ActionType.DETERMINISTIC,
                parameters={"chain_name": "marketing-social-campaign"}
            )
        )
    elif "promotion" in goal_lower:
        steps.append(
            ActionStep(
                step_id="step-promotion-chain",
                action_name="execute_chain",
                action_type=ActionType.DETERMINISTIC,
                parameters={"chain_name": "promotion-product-launch"}
            )
        )
    elif "networking" in goal_lower:
        steps.append(
            ActionStep(
                step_id="step-networking-chain",
                action_name="execute_chain",
                action_type=ActionType.DETERMINISTIC,
                parameters={"chain_name": "networking-github-outreach"}
            )
        )
    elif "saas" in goal_lower:
        steps.append(
            ActionStep(
                step_id="step-saas-chain",
                action_name="execute_chain",
                action_type=ActionType.DETERMINISTIC,
                parameters={"chain_name": "saas-fullstack-scaffold"}
            )
        )
    
    # 4. Acquisition tracker goals
    elif "track" in goal_lower or "acquisition" in goal_lower or "progress" in goal_lower or "insight" in goal_lower:
        steps.append(
            ActionStep(
                step_id="step-tracker-daily",
                action_name="track_daily_progress",
                action_type=ActionType.IDEMPOTENT,
                parameters={"brain_state": "autonomous", "tasks_executed": 1}
            )
        )
        steps.append(
            ActionStep(
                step_id="step-tracker-metrics",
                action_name="track_metrics_refresh",
                action_type=ActionType.IDEMPOTENT,
                parameters={}
            )
        )

    # 5. Default: delegate to standard DeterministicCodingAgent handler
    else:
        steps.append(
            ActionStep(
                step_id="step-dca-query",
                action_name="run_dca_query",
                action_type=ActionType.DETERMINISTIC,
                parameters={"query": goal}
            )
        )
        
    return steps
