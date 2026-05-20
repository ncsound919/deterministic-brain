"""COO Brain 2-Hour Productivity Run — simulates autonomous operations and measures output."""
from __future__ import annotations

import json
import time
import random
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from coo.state import (
    PortfolioState,
    ProductConfig,
    TrafficLightZone,
    DecisionCard,
    Constitution,
)
from coo.classifier import EventClassifier, get_classifier
from coo.github_queue import GitHubQueue
from coo.orchestrator import COOOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("coo_productivity")


# ── Simulated Event Generators ──────────────────────────────────────────────

EVENT_TEMPLATES = {
    "claw-protect": [
        {"event_type": "build_failure", "severity": 0.3, "error_message": "TypeScript error in AgentFleet.tsx: Property 'trustScore' does not exist on type 'AgentStatus'"},
        {"event_type": "exception", "severity": 0.4, "error_message": "ConnectionError: Redis connection refused on port 6379"},
        {"event_type": "security_alert", "severity": 0.9, "error_message": "Prompt injection detected in user input field — confidence 0.95"},
        {"event_type": "dependency_update", "severity": 0.0, "error_message": "lodash 4.17.21 has known CVE-2021-23337"},
        {"event_type": "cache_clear", "severity": 0.0, "error_message": "Cache bloat detected: 2.3GB exceeds 2GB threshold"},
        {"event_type": "stripe_payment_failed", "severity": 0.5, "error_message": "Invoice payment failed: card_declined for customer cus_xyz"},
        {"event_type": "exception", "severity": 0.2, "error_message": "TypeError: Cannot read properties of null (reading 'modules')"},
    ],
    "openhub": [
        {"event_type": "build_failure", "severity": 0.4, "error_message": "Vite build failed: Could not resolve 'monaco-editor' from src/components/CodeEditor.tsx"},
        {"event_type": "ci_failure", "severity": 0.3, "error_message": "GitHub Actions: test suite failed — 3/47 tests failing"},
        {"event_type": "dependency_update", "severity": 0.0, "error_message": "express 4.18.2 → 4.21.0 available"},
        {"event_type": "exception", "severity": 0.3, "error_message": "SyntaxError: Unexpected token '}' in server.ts line 142"},
        {"event_type": "cache_clear", "severity": 0.0, "error_message": "Node modules cache stale — clearing"},
        {"event_type": "build_failure", "severity": 0.5, "error_message": "tsc --noEmit failed: 12 type errors in pipeline module"},
    ],
    "ul2": [
        {"event_type": "stripe_subscription_canceled", "severity": 0.7, "error_message": "Customer canceled Pro subscription — reason: too_expensive"},
        {"event_type": "exception", "severity": 0.3, "error_message": "FirebaseError: Missing or insufficient permissions on /users/{uid}/profile"},
        {"event_type": "build_failure", "severity": 0.2, "error_message": "Vite chunk optimization warning: main.js exceeds 500KB"},
        {"event_type": "stripe_payment_failed", "severity": 0.5, "error_message": "Payment method expired for 3 Business tier customers"},
    ],
    "aetherdesk": [
        {"event_type": "exception", "severity": 0.6, "error_message": "redis.exceptions.ConnectionError: Connection lost during tenant lookup"},
        {"event_type": "build_failure", "severity": 0.3, "error_message": "Docker build failed: FreeSWITCH package not found in apt"},
    ],
    "bbtech": [
        {"event_type": "exception", "severity": 0.2, "error_message": "ModuleNotFoundError: No module named 'scipy.spatial'"},
        {"event_type": "dependency_update", "severity": 0.0, "error_message": "numpy 1.26 → 2.0 available — breaking changes expected"},
    ],
}


def generate_event(product_id: str) -> Dict[str, Any]:
    """Generate a realistic event for a given product."""
    templates = EVENT_TEMPLATES.get(product_id, [])
    if not templates:
        return None
    template = random.choice(templates)
    return {
        "product_id": product_id,
        "summary": f"{template['event_type'].replace('_', ' ').title()} in {product_id}",
        **template,
    }


# ── Mock GitHub Queue (no real API calls) ────────────────────────────────────

class MockGitHubQueue(GitHubQueue):
    """GitHub queue that simulates API calls without hitting the network."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._issue_counter = 100
        self._opened_issues: List[Dict] = []

    def open_issue(self, card: DecisionCard) -> DecisionCard | None:
        self._issue_counter += 1
        card.github_issue_number = self._issue_counter
        self._opened_issues.append({
            "number": self._issue_counter,
            "title": f"[{card.zone.value.upper()}] {card.summary}",
            "product_id": card.product_id,
            "zone": card.zone.value,
        })
        return card

    def get_opened_issues(self) -> List[Dict]:
        return list(self._opened_issues)


# ── Productivity Run ─────────────────────────────────────────────────────────

class ProductivityRun:
    """Simulates a 2-hour autonomous COO Brain run and measures output."""

    def __init__(self, duration_minutes: int = 120):
        self.duration_minutes = duration_minutes
        self.portfolio = PortfolioState()
        self.classifier = EventClassifier()
        self.github_queue = MockGitHubQueue(token="mock", owner="ncsound919", repo="claw-protect")
        self.constitution = Constitution()

        self.orchestrator = COOOrchestrator(
            portfolio=self.portfolio,
            classifier=self.classifier,
            github_queue=self.github_queue,
            constitution=self.constitution,
        )

        self._register_products()
        self.metrics = {
            "total_events_processed": 0,
            "green_auto_executed": 0,
            "yellow_issues_opened": 0,
            "red_escalated": 0,
            "skipped_unknown_product": 0,
            "events_by_product": {},
            "events_by_type": {},
            "avg_priority_score": 0.0,
            "total_priority_score": 0.0,
            "start_time": None,
            "end_time": None,
            "elapsed_seconds": 0.0,
            "events_per_minute": 0.0,
            "issues_opened": [],
        }

    def _register_products(self):
        """Register all VentureLab Group products."""
        products = [
            ProductConfig(product_id="claw-protect", tier=1, name="Claw Protect", github_repo="claw-protect"),
            ProductConfig(product_id="openhub", tier=1, name="OpenHub", github_repo="OpenHub-main"),
            ProductConfig(product_id="ul2", tier=2, name="Uplift Lab", github_repo="UL2-main"),
            ProductConfig(product_id="aetherdesk", tier=3, name="AetherDesk", github_repo="Aetherdesk-Call-Center"),
            ProductConfig(product_id="bbtech", tier=3, name="BBTech", github_repo="BB-Tech"),
        ]
        for p in products:
            self.orchestrator.register_product(p)

    def run(self) -> Dict:
        """Execute the productivity simulation."""
        self.metrics["start_time"] = datetime.now(timezone.utc).isoformat()
        start = time.time()

        # Simulate event arrival rate: ~1 event per 3 minutes = ~40 events in 2 hours
        event_interval = self.duration_minutes * 60 / 40  # seconds between events

        logger.info("=" * 60)
        logger.info("COO BRAIN 2-HOUR PRODUCTIVITY RUN")
        logger.info(f"Duration: {self.duration_minutes} minutes")
        logger.info(f"Expected events: ~40 (1 per {event_interval/60:.1f} min)")
        logger.info("=" * 60)

        event_count = 0
        while time.time() - start < self.duration_minutes * 60:
            # Pick a random product (weighted toward Tier 1)
            product_weights = [0.35, 0.30, 0.20, 0.10, 0.05]
            products = list(EVENT_TEMPLATES.keys())
            product_id = random.choices(products, weights=product_weights, k=1)[0]

            event = generate_event(product_id)
            if event is None:
                continue

            event_count += 1
            logger.info(f"\n--- Event #{event_count}: {event['event_type']} ({product_id}) ---")

            card = self.orchestrator.process_event(event)

            self.metrics["total_events_processed"] += 1
            self.metrics["events_by_product"][product_id] = self.metrics["events_by_product"].get(product_id, 0) + 1
            self.metrics["events_by_type"][event["event_type"]] = self.metrics["events_by_type"].get(event["event_type"], 0) + 1

            if card is None:
                self.metrics["skipped_unknown_product"] += 1
                logger.info(f"  → SKIPPED (unknown product)")
            elif card.zone == TrafficLightZone.GREEN:
                self.metrics["green_auto_executed"] += 1
                logger.info(f"  → GREEN: auto-executed ✓")
            elif card.zone == TrafficLightZone.YELLOW:
                self.metrics["yellow_issues_opened"] += 1
                self.metrics["issues_opened"].append({
                    "number": card.github_issue_number,
                    "title": card.summary,
                    "product_id": card.product_id,
                })
                logger.info(f"  → YELLOW: GitHub issue #{card.github_issue_number} opened")
            elif card.zone == TrafficLightZone.RED:
                self.metrics["red_escalated"] += 1
                self.metrics["issues_opened"].append({
                    "number": card.github_issue_number,
                    "title": card.summary,
                    "product_id": card.product_id,
                })
                logger.info(f"  → RED: escalated to #{card.github_issue_number} 🚨")

            # Sleep to simulate real event arrival
            time.sleep(min(event_interval, 2))  # cap at 2s for simulation speed

        end = time.time()
        self.metrics["end_time"] = datetime.now(timezone.utc).isoformat()
        self.metrics["elapsed_seconds"] = round(end - start, 2)
        self.metrics["events_per_minute"] = round(
            self.metrics["total_events_processed"] / (self.metrics["elapsed_seconds"] / 60), 2
        )

        # Calculate average priority
        decisions = self.orchestrator.get_decision_log()
        if decisions:
            total_priority = sum(
                self.classifier.classify({
                    "event_type": d.summary.lower().split()[0],
                    "product_id": d.product_id,
                    "tier": self.portfolio.products.get(d.product_id, ProductConfig(d.product_id, 2, "")).tier,
                }).priority_score
                for d in decisions
            )
            self.metrics["avg_priority_score"] = round(total_priority / len(decisions), 4)

        return self.metrics

    def print_report(self):
        """Print a formatted productivity report."""
        m = self.metrics
        print("\n" + "=" * 60)
        print("COO BRAIN — 2-HOUR PRODUCTIVITY REPORT")
        print("=" * 60)
        print(f"  Duration:          {m['elapsed_seconds']:.1f}s ({m['elapsed_seconds']/60:.1f} min)")
        print(f"  Events Processed:  {m['total_events_processed']}")
        print(f"  Events/min:        {m['events_per_minute']}")
        print(f"  Avg Priority:      {m['avg_priority_score']}")
        print()
        print("  ── Zone Breakdown ──")
        print(f"  🟢 Green (auto):   {m['green_auto_executed']}")
        print(f"  🟡 Yellow (HITL):  {m['yellow_issues_opened']}")
        print(f"  🔴 Red (escalate): {m['red_escalated']}")
        print(f"  ⏭  Skipped:        {m['skipped_unknown_product']}")
        print()
        print("  ── By Product ──")
        for product, count in sorted(m["events_by_product"].items(), key=lambda x: -x[1]):
            bar = "█" * count
            print(f"  {product:20s} {count:3d} {bar}")
        print()
        print("  ── By Event Type ──")
        for etype, count in sorted(m["events_by_type"].items(), key=lambda x: -x[1]):
            print(f"  {etype:30s} {count:3d}")
        print()
        print(f"  ── GitHub Issues Opened: {len(m['issues_opened'])} ──")
        for issue in m["issues_opened"]:
            print(f"    #{issue['number']} [{issue['product_id']}] {issue['title']}")
        print()
        print("=" * 60)


def main():
    """Run the 2-hour productivity simulation."""
    run = ProductivityRun(duration_minutes=120)
    metrics = run.run()
    run.print_report()

    # Save report to file
    report_path = "data/coo_productivity_report.json"
    with open(report_path, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
