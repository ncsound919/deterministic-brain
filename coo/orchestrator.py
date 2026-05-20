"""COO Brain Orchestrator — ties together state, classifier, and GitHub queue."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from coo.state import (
    PortfolioState,
    ProductConfig,
    TelemetryEvent,
    TrafficLightZone,
    DecisionCard,
    Constitution,
)
from coo.classifier import EventClassifier, get_classifier
from coo.github_queue import GitHubQueue, get_queue

logger = logging.getLogger(__name__)


class COOOrchestrator:
    """Main orchestrator: ingests events, classifies, dispatches to HITL queue."""

    def __init__(
        self,
        portfolio: Optional[PortfolioState] = None,
        classifier: Optional[EventClassifier] = None,
        github_queue: Optional[GitHubQueue] = None,
        constitution: Optional[Constitution] = None,
    ):
        self.portfolio = portfolio or PortfolioState()
        self.classifier = classifier or get_classifier()
        self.github_queue = github_queue or get_queue()
        self.constitution = constitution or Constitution()
        self._decision_log: List[DecisionCard] = []

    def register_product(self, config: ProductConfig) -> None:
        self.portfolio.register_product(config)
        logger.info("COO: registered product '%s' (tier %d)", config.product_id, config.tier)

    def process_event(self, raw_event: Dict[str, Any]) -> Optional[DecisionCard]:
        """Full pipeline: ingest → classify → dispatch."""
        product_id = raw_event.get("product_id", "")
        if product_id and product_id not in self.portfolio.products:
            logger.warning("COO: unknown product '%s' — skipping", product_id)
            return None

        # Step 1: Classify
        classification = self.classifier.classify(raw_event)
        logger.info(
            "COO: classified event '%s' as %s (priority %.2f)",
            raw_event.get("event_type", "unknown"),
            classification.zone.value,
            classification.priority_score,
        )

        # Step 2: Create telemetry event
        severity = float(raw_event.get("severity", 0.0))
        telemetry = TelemetryEvent(
            product_id=product_id,
            event_type=raw_event.get("event_type", "unknown"),
            raw_data=raw_event,
            zone=classification.zone,
            severity=severity,
        )

        # Step 3: Create decision card
        card = DecisionCard(
            event_id=telemetry.event_id,
            product_id=product_id,
            zone=classification.zone,
            summary=raw_event.get("summary", classification.diagnosis[:80]),
            diagnosis=classification.diagnosis,
            proposed_fix=classification.proposed_fix,
        )

        # Step 4: Route based on zone
        if classification.zone == TrafficLightZone.GREEN:
            self._handle_green(card, raw_event)
        elif classification.zone == TrafficLightZone.YELLOW:
            self._handle_yellow(card)
        else:
            self._handle_red(card)

        self._decision_log.append(card)
        return card

    def handle_issue_closed(self, issue_number: int, outcome: str = "approved") -> bool:
        """Called when a GitHub Issue is closed — marks the decision as resolved."""
        for card in reversed(self._decision_log):
            if card.github_issue_number == issue_number:
                card.resolved_ts = __import__("time").time()
                card.outcome = outcome
                logger.info(
                    "COO: issue #%d closed with outcome '%s' — marking resolved",
                    issue_number,
                    outcome,
                )
                return True
        logger.warning("COO: no decision card found for issue #%d", issue_number)
        return False

    def get_pending_decisions(self) -> List[DecisionCard]:
        """Return all unresolved decisions."""
        return [c for c in self._decision_log if not c.resolved]

    def get_decision_log(self) -> List[DecisionCard]:
        return list(self._decision_log)

    def _handle_green(self, card: DecisionCard, raw_event: Dict[str, Any]) -> None:
        """Auto-execute green-zone events."""
        logger.info("COO GREEN: auto-executing '%s'", card.event_id)
        card.outcome = "auto_executed"
        card.resolved_ts = __import__("time").time()

    def _handle_yellow(self, card: DecisionCard) -> None:
        """Open GitHub Issue for human review."""
        logger.info("COO YELLOW: opening GitHub issue for '%s'", card.event_id)
        result = self.github_queue.open_issue(card)
        if result is None:
            logger.error("COO: failed to open GitHub issue for '%s'", card.event_id)
            card.outcome = "dispatch_failed"
        else:
            card.outcome = "pending_review"

    def _handle_red(self, card: DecisionCard) -> None:
        """Escalate immediately — open issue with RED tag."""
        logger.warning("COO RED: escalating '%s' — immediate action required", card.event_id)
        result = self.github_queue.open_issue(card)
        if result is None:
            logger.error("COO: failed to escalate RED event '%s'", card.event_id)
            card.outcome = "escalation_failed"
        else:
            card.outcome = "escalated"


_orchestrator_instance: Optional[COOOrchestrator] = None


def get_orchestrator(
    github_token: str = "",
    github_owner: str = "ncsound919",
    github_repo: str = "claw-protect",
) -> COOOrchestrator:
    """Get or create the singleton orchestrator."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        queue = GitHubQueue(token=github_token, owner=github_owner, repo=github_repo)
        _orchestrator_instance = COOOrchestrator(github_queue=queue)
    return _orchestrator_instance
