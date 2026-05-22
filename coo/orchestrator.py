"""COO Brain Orchestrator — ties together state, classifier, and GitHub queue."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
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
        self._executor = None
        self._store = None
        
        # Load recent history from persistent store
        try:
            self._decision_log = self.store.load_log(limit=200)
            logger.info("COO: loaded %d decision cards from store", len(self._decision_log))
        except Exception as e:
            logger.error("COO: failed to load history from store: %s", e)

    @property
    def executor(self):
        if self._executor is None:
            from coo.executor import AutoFixExecutor
            root = Path(os.environ.get("COO_ROOT_DIR", Path(__file__).parent.parent))
            self._executor = AutoFixExecutor(root_dir=root)
        return self._executor

    @property
    def store(self):
        if self._store is None:
            from coo.state import DecisionStore
            self._store = DecisionStore.get_instance()
        return self._store

    def register_product(self, config: ProductConfig) -> None:
        self.portfolio.register_product(config)
        logger.info("COO: registered product '%s' (tier %d)", config.product_id, config.tier)

    def process_event(self, raw_event: Dict[str, Any]) -> Optional[DecisionCard]:
        product_id = raw_event.get("product_id", "")
        if product_id and product_id not in self.portfolio.products:
            logger.warning("COO: unknown product '%s' — skipping", product_id)
            return None

        classification = self.classifier.classify(raw_event)
        logger.info(
            "COO: classified event '%s' as %s (priority %.2f)",
            raw_event.get("event_type", "unknown"),
            classification.zone.value,
            classification.priority_score,
        )

        severity = float(raw_event.get("severity", 0.0))
        telemetry = TelemetryEvent(
            product_id=product_id,
            event_type=raw_event.get("event_type", "unknown"),
            raw_data=raw_event,
            zone=classification.zone,
            severity=severity,
        )

        card = DecisionCard(
            event_id=telemetry.event_id,
            product_id=product_id,
            zone=classification.zone,
            summary=raw_event.get("summary", classification.diagnosis[:80]),
            diagnosis=classification.diagnosis,
            proposed_fix=classification.proposed_fix,
        )

        if classification.zone == TrafficLightZone.GREEN:
            self._handle_green(card, raw_event)
        elif classification.zone == TrafficLightZone.YELLOW:
            self._handle_yellow(card, product_id)
        else:
            self._handle_red(card, product_id)

        # Store in-memory and in SQLite
        self._decision_log.insert(0, card)
        self.store.save_card(card)
        return card

    def handle_issue_closed(self, issue_number: int, outcome: str = "approved") -> bool:
        """Called when a GitHub Issue is closed — triggers execution if approved."""
        for card in self._decision_log:
            if card.github_issue_number == issue_number:
                if card.resolved:
                    return True
                
                card.resolved_ts = __import__("time").time()
                card.outcome = outcome
                self.store.save_card(card)
                
                # Close-to-Execute: If approved, run the executor
                if outcome in ("approved", "merged"):
                    logger.info("COO: issue #%d approved — triggering execution", issue_number)
                    # We use the product_id from the card
                    # For now, we simulate the action routing based on the summary/diagnosis
                    # In a real scenario, this would trigger a specific skill or script
                    exec_result = self.executor.execute("approved_fix", card.product_id, {"card": asdict(card)})
                    self.store.log_execution(card.event_id, "approved_fix", exec_result.get("status"), json.dumps(exec_result))
                
                logger.info(
                    "COO: issue #%d closed with outcome '%s' — marking resolved",
                    issue_number,
                    outcome,
                )
                return True
        logger.warning("COO: no decision card found for issue #%d", issue_number)
        return False

    def get_pending_decisions(self) -> List[DecisionCard]:
        return [c for c in self._decision_log if not c.resolved]

    def get_decision_log(self) -> List[DecisionCard]:
        return list(self._decision_log)

    def get_status(self) -> Dict[str, Any]:
        green = sum(1 for c in self._decision_log if c.zone == TrafficLightZone.GREEN)
        yellow = sum(1 for c in self._decision_log if c.zone == TrafficLightZone.YELLOW)
        red = sum(1 for c in self._decision_log if c.zone == TrafficLightZone.RED)
        pending = sum(1 for c in self._decision_log if not c.resolved)
        resolved = sum(1 for c in self._decision_log if c.resolved)
        products = list(self.portfolio.products.keys())
        return {
            "products": products,
            "decisions_total": len(self._decision_log),
            "zone_breakdown": {"green": green, "yellow": yellow, "red": red},
            "pending": pending,
            "resolved": resolved,
            "constitution": self.constitution.get_summary(),
        }

    def _handle_green(self, card: DecisionCard, raw_event: Dict[str, Any]) -> None:
        logger.info("COO GREEN: auto-executing '%s' on product '%s'", card.event_id, card.product_id)
        event_type = raw_event.get("event_type", "cache_clear")
        result = self.executor.execute(event_type, card.product_id, raw_event.get("details", {}))
        status = result.get("status", "unknown")
        card.outcome = f"auto_executed_{status}"
        card.resolved_ts = __import__("time").time()
        self.store.log_execution(card.event_id, event_type, status, json.dumps(result))
        logger.info("COO GREEN: result=%s", result)

    def _handle_yellow(self, card: DecisionCard, product_id: str) -> None:
        logger.info("COO YELLOW: opening GitHub issue for '%s' on product '%s'", card.event_id, product_id)
        product = self.portfolio.products.get(product_id)
        owner = product.github_owner if product else "ncsound919"
        repo = product.github_repo if product else product_id
        result = self.github_queue.open_issue(card, owner=owner, repo=repo)
        if result is None:
            logger.error("COO: failed to open GitHub issue for '%s'", card.event_id)
            card.outcome = "dispatch_failed"
        else:
            card.outcome = "pending_review"

    def _handle_red(self, card: DecisionCard, product_id: str) -> None:
        logger.warning("COO RED: escalating '%s' on product '%s' — immediate action required", card.event_id, product_id)
        product = self.portfolio.products.get(product_id)
        owner = product.github_owner if product else "ncsound919"
        repo = product.github_repo if product else product_id
        result = self.github_queue.open_issue(card, owner=owner, repo=repo)
        if result is None:
            logger.error("COO: failed to escalate RED event '%s'", card.event_id)
            card.outcome = "escalation_failed"
        else:
            card.outcome = "escalated"


_portfolio_products = [
    ProductConfig(product_id="deterministic-brain", tier=1, name="Deterministic Brain", github_repo="deterministic-brain"),
    ProductConfig(product_id="bbtech", tier=1, name="BB Tech", github_repo="BB-Tech"),
    ProductConfig(product_id="aetherdesk", tier=1, name="AetherDesk", github_repo="Aetherdesk-Call-Center"),
    ProductConfig(product_id="bookbridge", tier=2, name="BookBridge", github_repo="BookBridge-"),
    ProductConfig(product_id="book-synthesis", tier=3, name="Book Synthesis Engine", github_repo="Book-Synthesis-Engine"),
]


def register_portfolio(orchestrator: COOOrchestrator) -> None:
    """Register all known portfolio products into the orchestrator."""
    for product in _portfolio_products:
        orchestrator.register_product(product)


_orchestrator_instance: Optional[COOOrchestrator] = None


def get_orchestrator(
    github_token: str = "",
    github_owner: str = "ncsound919",
    github_repo: str = "deterministic-brain",
) -> COOOrchestrator:
    """Get or create the singleton orchestrator with portfolio pre-registered."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        queue = get_queue(token=github_token, owner=github_owner, repo=github_repo)
        _orchestrator_instance = COOOrchestrator(github_queue=queue)
        register_portfolio(_orchestrator_instance)
    return _orchestrator_instance
